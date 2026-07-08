"""Manual low-VRAM wav2vec2 CTC trainer.

This keeps the notebook thin while preserving the practical controls needed on
small local GPUs: partial encoder unfreezing, parameter-group learning rates,
metric-based checkpoint selection, and resumable optimizer/scheduler state.
"""

from __future__ import annotations

import json
import math
import os
import random
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jiwer
import torch
from torch.nn.utils import clip_grad_norm_
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

from quran_asr.audio_io import load_audio
from quran_asr.config import Config
from quran_asr.data_pipeline.normalize import normalize, strip_diacritics
from quran_asr.tokenizer.processor import build_processor
from quran_asr.training.collator import DataCollatorCTCWithPadding
from quran_asr.training.metrics import decode_labels_no_collapse

_RESET = "\033[0m"
_DIM = "\033[2m"
_RED = "\033[31m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_MAGENTA = "\033[35m"


@dataclass(frozen=True)
class ManualTrainResult:
    output_dir: Path
    best_dir: Path
    final_dir: Path
    best_metric: str
    best_score: float
    history: dict[str, list[Any]]


def train_manual(
    cfg: Config,
    output_dir: str | Path | None = None,
    resume: bool = True,
    max_epochs: int | None = None,
) -> ManualTrainResult:
    """Train with a custom CTC loop suitable for constrained local CUDA GPUs."""
    from datasets import load_from_disk
    from transformers import Wav2Vec2ForCTC, get_linear_schedule_with_warmup

    _seed_everything(cfg.seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    out = Path(output_dir or cfg.logging.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stage = "bootstrap" if cfg.training.auto_stage else "manual"
    _apply_stage_config(cfg, stage)

    processor = build_processor(cfg.model.vocab_path, cfg.data.sample_rate)
    dataset = load_from_disk(cfg.data.processed_dir)
    prepared = dataset.map(
        _preprocess_batch(processor, cfg.data.sample_rate),
        remove_columns=dataset["train"].column_names,
        desc="preprocess",
    )

    collator = DataCollatorCTCWithPadding(processor=processor)
    train_loader = DataLoader(
        prepared["train"],
        batch_size=cfg.training.per_device_train_batch_size,
        shuffle=True,
        collate_fn=collator,
    )
    eval_split = "validation" if "validation" in prepared else "test"
    eval_loader = DataLoader(
        prepared[eval_split],
        batch_size=cfg.training.per_device_eval_batch_size,
        shuffle=False,
        collate_fn=collator,
    )

    model = Wav2Vec2ForCTC.from_pretrained(
        cfg.model.base,
        vocab_size=len(processor.tokenizer),
        ctc_loss_reduction="mean",
        pad_token_id=processor.tokenizer.pad_token_id,
        ignore_mismatched_sizes=True,
        ctc_zero_infinity=True,
    )
    _configure_model_runtime(model, processor, cfg)

    trainable_groups = configure_trainable_parameters(model, cfg)
    model.to(device)

    epochs = int(max_epochs or cfg.training.epochs)
    grad_accum = max(int(cfg.training.gradient_accumulation_steps), 1)
    optimizer, scheduler = _build_optimizer_and_scheduler(
        trainable_groups,
        cfg,
        len(train_loader),
        grad_accum,
        epochs,
        get_linear_schedule_with_warmup,
    )

    state = _load_resume_state(out, cfg.training.resume_from, resume)
    start_epoch = 0
    global_step = 0
    best_score = _initial_best(cfg.training.greater_is_better)
    history = _empty_history()
    epochs_without_improvement = 0

    if state is not None:
        resume_dir, payload = state
        stage = str(payload.get("stage", stage))
        _apply_stage_config(cfg, stage)
        model = Wav2Vec2ForCTC.from_pretrained(str(resume_dir)).to(device)
        _configure_model_runtime(model, processor, cfg)
        trainable_groups = configure_trainable_parameters(model, cfg)
        optimizer, scheduler = _build_optimizer_and_scheduler(
            trainable_groups,
            cfg,
            len(train_loader),
            grad_accum,
            epochs,
            get_linear_schedule_with_warmup,
        )
        optimizer.load_state_dict(payload["optimizer"])
        scheduler.load_state_dict(payload["scheduler"])
        start_epoch = int(payload["epoch"]) + 1
        global_step = int(payload["global_step"])
        best_score = float(payload["best_score"])
        history = _load_history(resume_dir)
        epochs_without_improvement = int(payload.get("epochs_without_improvement", 0))
        print(f"Resuming from: {resume_dir}")
        print(f"Start epoch: {start_epoch + 1}")
        print(f"Global step: {global_step}")
        print(f"Stage: {stage}")
        print(f"Best {cfg.training.best_metric}: {best_score}")
    else:
        _apply_blank_logit_bias_init(model, processor, cfg.training.blank_logit_bias_init)
        print("No resume checkpoint found. Starting fresh.")

    trainable_parameters = [p for group in trainable_groups for p in group["params"]]
    print_trainable_summary(model, cfg)
    print(_format_epoch_header())

    for epoch in range(start_epoch, epochs):
        train_loss, global_step = _train_one_epoch(
            model=model,
            loader=train_loader,
            optimizer=optimizer,
            scheduler=scheduler,
            device=device,
            grad_accum=grad_accum,
            max_grad_norm=cfg.training.max_grad_norm,
            trainable_parameters=trainable_parameters,
            global_step=global_step,
            epoch=epoch,
            epochs=epochs,
        )
        metrics = _evaluate(model, eval_loader, processor, device)
        score = float(metrics[cfg.training.best_metric])
        improved = _is_better(score, best_score, cfg.training.greater_is_better)

        row = {
            "epoch": epoch + 1,
            "stage": stage,
            "global_step": global_step,
            "train_loss": train_loss,
            **metrics,
        }
        _append_history(history, row)
        print(_format_epoch_summary(row, cfg.training.best_metric, improved))
        _print_decode_health(metrics["empty_pred_rate"])

        if improved:
            best_score = score
            epochs_without_improvement = 0
            _save_training_state(
                out / "best",
                model,
                processor,
                optimizer,
                scheduler,
                epoch,
                global_step,
                best_score,
                cfg.training.best_metric,
                epochs_without_improvement,
                history,
                stage,
            )
            print(_color(f"New best checkpoint saved: {out / 'best'}", _GREEN))
        else:
            epochs_without_improvement += 1
            print(_color(f"No improvement for {epochs_without_improvement} epoch(s).", _YELLOW))

        _save_training_state(
            out / "latest",
            model,
            processor,
            optimizer,
            scheduler,
            epoch,
            global_step,
            best_score,
            cfg.training.best_metric,
            epochs_without_improvement,
            history,
            stage,
        )

        if _should_switch_to_finetune(cfg, stage, epoch + 1, metrics):
            stage = "finetune"
            _apply_stage_config(cfg, stage)
            _configure_model_runtime(model, processor, cfg)
            trainable_groups = configure_trainable_parameters(model, cfg)
            trainable_parameters = [p for group in trainable_groups for p in group["params"]]
            optimizer, scheduler = _build_optimizer_and_scheduler(
                trainable_groups,
                cfg,
                len(train_loader),
                grad_accum,
                epochs,
                get_linear_schedule_with_warmup,
            )
            epochs_without_improvement = 0
            print(_color("[stage] switching to finetune", _GREEN))
            print_trainable_summary(model, cfg)
            print(_format_epoch_header())

        if epochs_without_improvement >= cfg.training.early_stopping_patience:
            print("Early stopping triggered.")
            break

    final_dir = out / "final"
    _write_final_from_best(out, final_dir, model, processor, history)
    _write_history_files(out, history)

    return ManualTrainResult(
        output_dir=out,
        best_dir=out / "best",
        final_dir=final_dir,
        best_metric=cfg.training.best_metric,
        best_score=best_score,
        history=history,
    )


def configure_trainable_parameters(model: Any, cfg: Config) -> list[dict[str, Any]]:
    """Freeze feature encoder and all but the last N transformer encoder layers."""
    model.freeze_feature_encoder()
    for param in model.parameters():
        param.requires_grad = False

    n_layers = max(int(cfg.training.encoder_trainable_layers), 0)
    encoder_layers = list(model.wav2vec2.encoder.layers)
    encoder_params: list[torch.nn.Parameter] = []
    if n_layers:
        for layer in encoder_layers[-n_layers:]:
            for param in layer.parameters():
                param.requires_grad = True
                encoder_params.append(param)

    head_params: list[torch.nn.Parameter] = []
    for param in model.lm_head.parameters():
        param.requires_grad = True
        head_params.append(param)

    base_lr = float(cfg.training.learning_rate)
    encoder_lr = float(cfg.training.encoder_learning_rate or base_lr)
    head_lr = float(cfg.training.head_learning_rate or base_lr)
    groups: list[dict[str, Any]] = []
    if encoder_params:
        groups.append({"params": encoder_params, "lr": encoder_lr, "name": "encoder"})
    groups.append({"params": head_params, "lr": head_lr, "name": "lm_head"})
    return groups


def _apply_stage_config(cfg: Config, stage: str) -> None:
    if not cfg.training.auto_stage:
        return
    if stage == "bootstrap":
        cfg.training.encoder_trainable_layers = cfg.training.bootstrap_encoder_trainable_layers
        cfg.training.encoder_learning_rate = cfg.training.bootstrap_encoder_learning_rate
        cfg.training.head_learning_rate = cfg.training.bootstrap_head_learning_rate
        cfg.training.blank_logit_bias_init = cfg.training.bootstrap_blank_logit_bias_init
        cfg.model.apply_spec_augment = cfg.training.bootstrap_apply_spec_augment
    elif stage == "finetune":
        cfg.training.encoder_trainable_layers = cfg.training.finetune_encoder_trainable_layers
        cfg.training.encoder_learning_rate = cfg.training.finetune_encoder_learning_rate
        cfg.training.head_learning_rate = cfg.training.finetune_head_learning_rate
        cfg.training.blank_logit_bias_init = 0.0
        cfg.model.apply_spec_augment = cfg.training.finetune_apply_spec_augment
    else:
        raise ValueError(f"unknown training stage: {stage}")


def _configure_model_runtime(model: Any, processor: Any, cfg: Config) -> None:
    model.config.ctc_zero_infinity = True
    model.config.pad_token_id = processor.tokenizer.pad_token_id
    model.config.apply_spec_augment = cfg.model.apply_spec_augment
    model.config.mask_time_prob = cfg.training.masking_time_prob
    if cfg.training.gradient_checkpointing:
        model.gradient_checkpointing_enable()


def _build_optimizer_and_scheduler(
    groups: list[dict[str, Any]],
    cfg: Config,
    train_loader_len: int,
    grad_accum: int,
    epochs: int,
    scheduler_factory: Any,
) -> tuple[torch.optim.AdamW, Any]:
    optimizer = _build_optimizer(groups, cfg)
    updates_per_epoch = math.ceil(train_loader_len / grad_accum)
    total_updates = max(epochs * updates_per_epoch, 1)
    warmup_steps = int(total_updates * cfg.training.warmup_ratio)
    scheduler = scheduler_factory(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=total_updates,
    )
    return optimizer, scheduler


def _should_switch_to_finetune(
    cfg: Config,
    stage: str,
    epoch: int,
    metrics: dict[str, float],
) -> bool:
    if not cfg.training.auto_stage or stage != "bootstrap":
        return False
    min_reached = epoch >= cfg.training.bootstrap_min_epochs
    empty_ready = (
        min_reached
        and metrics["empty_pred_rate"] <= cfg.training.bootstrap_empty_threshold
    )
    epoch_limit = epoch >= cfg.training.bootstrap_max_epochs
    return empty_ready or epoch_limit


def print_trainable_summary(model: Any, cfg: Config) -> None:
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    print("Model:", cfg.model.base)
    print("Trainable encoder layers:", cfg.training.encoder_trainable_layers)
    print("Trainable params:", trainable)
    print("Total params:", total)
    print("Trainable ratio:", round(trainable / total * 100, 4), "%")


def _apply_blank_logit_bias_init(model: Any, processor: Any, bias: float) -> None:
    """Lower the initial CTC blank logit to reduce early all-blank collapse."""
    if bias == 0:
        return
    blank_id = processor.tokenizer.pad_token_id
    if blank_id is None or model.lm_head.bias is None:
        return
    with torch.no_grad():
        model.lm_head.bias[blank_id] += bias
    print(_color(f"Initial blank logit bias adjusted by {bias:+.2f}", _YELLOW))


def _preprocess_batch(processor: Any, sample_rate: int):
    def fn(batch: dict[str, Any]) -> dict[str, Any]:
        audio, sr = load_audio(batch["audio_path"], sample_rate)
        batch["input_values"] = processor(audio, sampling_rate=sr).input_values[0]
        batch["labels"] = processor.tokenizer(normalize(batch["text"])).input_ids
        return batch

    return fn


def _build_optimizer(groups: list[dict[str, Any]], cfg: Config) -> torch.optim.AdamW:
    return torch.optim.AdamW(
        groups,
        weight_decay=float(cfg.training.weight_decay),
        foreach=False,
    )


def _train_one_epoch(
    model: Any,
    loader: DataLoader,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    device: torch.device,
    grad_accum: int,
    max_grad_norm: float,
    trainable_parameters: list[torch.nn.Parameter],
    global_step: int,
    epoch: int,
    epochs: int,
) -> tuple[float, int]:
    model.train()
    optimizer.zero_grad(set_to_none=True)
    total_loss = 0.0
    valid_steps = 0
    progress = tqdm(loader, desc=_color(f"Epoch {epoch + 1}/{epochs}", _CYAN), colour="cyan")
    for step, batch in enumerate(progress):
        batch = {k: v.to(device) for k, v in batch.items()}
        outputs = model(**batch)
        loss = outputs.loss / grad_accum
        if not torch.isfinite(loss):
            print(f"Non-finite loss detected at batch {step}: {loss.item()}")
            optimizer.zero_grad(set_to_none=True)
            continue
        loss.backward()
        total_loss += loss.item() * grad_accum
        valid_steps += 1
        if (step + 1) % grad_accum == 0 or (step + 1) == len(loader):
            clip_grad_norm_(trainable_parameters, max_grad_norm)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            global_step += 1
            progress.set_postfix(
                {
                    _color("loss", _CYAN): round(total_loss / max(valid_steps, 1), 4),
                    _color("step", _MAGENTA): global_step,
                }
            )
    return total_loss / max(valid_steps, 1), global_step


def _evaluate(
    model: Any,
    loader: DataLoader,
    processor: Any,
    device: torch.device,
) -> dict[str, float]:
    model.eval()
    total_loss = 0.0
    valid_steps = 0
    refs: list[str] = []
    hyps: list[str] = []
    with torch.no_grad():
        for batch in tqdm(loader, desc=_color("Evaluating", _MAGENTA), colour="magenta"):
            batch = {k: v.to(device) for k, v in batch.items()}
            outputs = model(**batch)
            if torch.isfinite(outputs.loss):
                total_loss += outputs.loss.item()
                valid_steps += 1
            pred_ids = torch.argmax(outputs.logits, dim=-1)
            hyps.extend(processor.batch_decode(pred_ids))
            labels = batch["labels"].detach().cpu().tolist()
            refs.extend(decode_labels_no_collapse(row, processor) for row in labels)

    refs_plain = [strip_diacritics(r) for r in refs]
    hyps_plain = [strip_diacritics(h) for h in hyps]
    empty_pred_rate = _empty_prediction_rate(hyps)
    return {
        "eval_loss": total_loss / max(valid_steps, 1),
        "wer": float(jiwer.wer(refs, hyps)),
        "cer": float(jiwer.cer(refs, hyps)),
        "wer_plain": float(jiwer.wer(refs_plain, hyps_plain)),
        "cer_plain": float(jiwer.cer(refs_plain, hyps_plain)),
        "empty_pred_rate": empty_pred_rate,
    }


def _save_training_state(
    path: Path,
    model: Any,
    processor: Any,
    optimizer: torch.optim.Optimizer,
    scheduler: Any,
    epoch: int,
    global_step: int,
    best_score: float,
    best_metric: str,
    epochs_without_improvement: int,
    history: dict[str, list[Any]],
    stage: str,
) -> None:
    path.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(path)
    processor.save_pretrained(path)
    torch.save(
        {
            "epoch": epoch,
            "global_step": global_step,
            "best_score": best_score,
            "best_metric": best_metric,
            "epochs_without_improvement": epochs_without_improvement,
            "stage": stage,
            "optimizer": optimizer.state_dict(),
            "scheduler": scheduler.state_dict(),
        },
        path / "training_state.pt",
    )
    _write_json(path / "training_history.json", history)
    print(f"Saved training state to: {path}")


def _load_resume_state(out: Path, mode: str, resume: bool) -> tuple[Path, dict[str, Any]] | None:
    if not resume or mode == "none":
        return None
    for name in [mode, "latest", "best"]:
        path = out / name
        state_path = path / "training_state.pt"
        if state_path.exists():
            return path, torch.load(state_path, map_location="cpu")
    return None


def _write_final_from_best(
    out: Path,
    final_dir: Path,
    model: Any,
    processor: Any,
    history: dict[str, list[Any]],
) -> None:
    best_dir = out / "best"
    if best_dir.exists():
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.copytree(best_dir, final_dir)
    else:
        final_dir.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(final_dir)
        processor.save_pretrained(final_dir)
    _write_json(final_dir / "training_history.json", history)
    print(f"Final checkpoint: {final_dir}")


def _write_history_files(out: Path, history: dict[str, list[Any]]) -> None:
    _write_json(out / "training_history.json", history)
    try:
        import pandas as pd

        pd.DataFrame(history).to_csv(out / "training_history.csv", index=False)
    except Exception as exc:  # noqa: BLE001
        print(f"Skipping CSV history export: {exc}")


def _empty_history() -> dict[str, list[Any]]:
    return {
        "epoch": [],
        "stage": [],
        "global_step": [],
        "train_loss": [],
        "eval_loss": [],
        "wer": [],
        "cer": [],
        "wer_plain": [],
        "cer_plain": [],
        "empty_pred_rate": [],
    }


def _load_history(path: Path) -> dict[str, list[Any]]:
    history_path = path / "training_history.json"
    if not history_path.exists():
        return _empty_history()
    loaded = json.loads(history_path.read_text(encoding="utf-8"))
    history = _empty_history()
    n_rows = max((len(v) for v in loaded.values() if isinstance(v, list)), default=0)
    for key in history:
        values = list(loaded.get(key, []))
        if len(values) < n_rows:
            fill_value = "unknown" if key == "stage" else 0.0
            values.extend([fill_value] * (n_rows - len(values)))
        history[key] = values
    return history


def _append_history(history: dict[str, list[Any]], row: dict[str, Any]) -> None:
    for key in _empty_history():
        history.setdefault(key, []).append(row[key])


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _initial_best(greater_is_better: bool) -> float:
    return -float("inf") if greater_is_better else float("inf")


def _is_better(score: float, best_score: float, greater_is_better: bool) -> bool:
    return score > best_score if greater_is_better else score < best_score


def _format_epoch_header() -> str:
    return _color(
        (
            f"{'epoch':>5} {'stage':>9} {'step':>6} {'train':>9} {'eval':>9} "
            f"{'WERp':>7} {'CERp':>7} {'WERd':>7} {'CERd':>7} "
            f"{'empty':>7} {'best':>5}"
        ),
        _DIM,
    )


def _format_epoch_summary(row: dict[str, Any], best_metric: str, improved: bool) -> str:
    best_mark = "*" if improved else "-"
    line = (
        f"{int(row['epoch']):>5} {str(row['stage']):>9} {int(row['global_step']):>6} "
        f"{row['train_loss']:>9.4f} {row['eval_loss']:>9.4f} "
        f"{row['wer_plain']:>7.3f} {row['cer_plain']:>7.3f} "
        f"{row['wer']:>7.3f} {row['cer']:>7.3f} "
        f"{row['empty_pred_rate']:>7.1%} {best_mark:>5} "
        f"{_color(best_metric, _DIM)}"
    )
    if row["empty_pred_rate"] >= 0.5 or row["wer_plain"] >= 1.0:
        return _color(line, _RED)
    if improved:
        return _color(line, _GREEN)
    return _color(line, _YELLOW)


def _print_decode_health(empty_pred_rate: float) -> None:
    if empty_pred_rate >= 0.5:
        print(_color(f"[WARN] empty/harakat-only decode rate: {empty_pred_rate:.1%}", _RED))
    elif empty_pred_rate > 0:
        print(_color(f"[WARN] empty/harakat-only decode rate: {empty_pred_rate:.1%}", _YELLOW))


def _empty_prediction_rate(hyps: list[str]) -> float:
    if not hyps:
        return 0.0
    n_empty = sum(1 for hyp in hyps if not strip_diacritics(hyp).strip())
    return n_empty / len(hyps)


def _color(text: str, color: str) -> str:
    if os.environ.get("NO_COLOR"):
        return text
    return f"{color}{text}{_RESET}"


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
