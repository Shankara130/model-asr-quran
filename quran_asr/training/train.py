"""Config-driven training entrypoint — shared by the CLI and the Colab notebook.

Auto-detects device (cuda -> mps -> cpu). fp16 is only enabled on CUDA (MPS fp16
is limited). Freezes the CNN feature encoder (standard for low-resource CTC
fine-tuning). A ``max_steps`` arg lets you smoke-test the full pipeline locally
without a full epoch.
"""

from __future__ import annotations

import os
from pathlib import Path

# CTC loss (aten::_ctc_loss) is not implemented for MPS on Apple Silicon.
# Fall back to CPU for that op so local M1 dev works. Harmless on CUDA (cloud).
os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

import torch

from quran_asr.config import Config


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def preprocess_dataset(processor, sample_rate: int):
    def fn(batch):
        audio = batch["audio"]
        batch["input_values"] = processor(audio["array"], sampling_rate=sample_rate).input_values[0]
        batch["labels"] = processor.tokenizer(batch["text"]).input_ids
        return batch
    return fn


def build_model(cfg: Config, processor):
    from transformers import Wav2Vec2ForCTC

    model = Wav2Vec2ForCTC.from_pretrained(
        cfg.model.base,
        pad_token_id=processor.tokenizer.pad_token_id,
        vocab_size=len(processor.tokenizer),
        ctc_loss_reduction="mean",
    )
    model.freeze_feature_encoder()  # keep the CNN front-end fixed (small data)
    if cfg.model.apply_spec_augment:
        model.config.apply_spec_augment = True
        model.config.mask_time_prob = cfg.training.masking_time_prob
    return model


def train(
    cfg: Config,
    epochs: float | None = None,
    max_steps: int | None = None,
    output_dir: str | Path | None = None,
    resume: bool = False,
):
    from datasets import load_from_disk
    from transformers import Trainer, TrainingArguments

    from quran_asr.tokenizer.processor import build_processor
    from quran_asr.training.collator import DataCollatorCTCWithPadding
    from quran_asr.training.metrics import make_compute_metrics

    device = get_device()
    print(f"[train] device={device} base={cfg.model.base}", flush=True)

    processor = build_processor(cfg.model.vocab_path, cfg.data.sample_rate)
    dd = load_from_disk(cfg.data.processed_dir)
    dd = dd.map(preprocess_dataset(processor, cfg.data.sample_rate),
                remove_columns=dd["train"].column_names, desc="preprocess")
    model = build_model(cfg, processor)

    use_fp16 = cfg.training.fp16 and torch.cuda.is_available()
    out = str(output_dir or cfg.logging.output_dir)
    hub_repo = cfg.logging.hub_repo
    args = TrainingArguments(
        output_dir=out,
        per_device_train_batch_size=cfg.training.per_device_train_batch_size,
        per_device_eval_batch_size=cfg.training.per_device_eval_batch_size,
        gradient_accumulation_steps=cfg.training.gradient_accumulation_steps,
        learning_rate=cfg.training.learning_rate,
        warmup_ratio=cfg.training.warmup_ratio,
        weight_decay=cfg.training.weight_decay,
        num_train_epochs=epochs if epochs is not None else cfg.training.epochs,
        max_steps=max_steps if max_steps is not None else -1,
        gradient_checkpointing=cfg.training.gradient_checkpointing,
        fp16=use_fp16,
        eval_strategy="steps",
        eval_steps=cfg.training.eval_steps,
        save_steps=cfg.training.save_steps,
        logging_steps=max(cfg.training.eval_steps, 1),
        save_total_limit=3,
        seed=cfg.seed,
        report_to=[],
        disable_tqdm=False,
        # Push to HF Hub mid+post training (survives Colab disconnects). Requires
        # huggingface_hub login + logging.hub_repo set in the config.
        push_to_hub=bool(hub_repo),
        hub_model_id=hub_repo,
        hub_private_repo=False,
        hub_strategy="checkpoint",
    )
    collator = DataCollatorCTCWithPadding(processor=processor)
    trainer = Trainer(
        model=model,
        args=args,
        train_dataset=dd["train"],
        eval_dataset=dd.get("validation"),
        data_collator=collator,
        compute_metrics=make_compute_metrics(processor),
    )

    resume_from = out if resume and Path(out).exists() and any(Path(out).iterdir()) else None
    trainer.train(resume_from_checkpoint=resume_from)

    final = Path(out) / "final"
    trainer.save_model(str(final))
    processor.save_pretrained(str(final))
    print(f"[train] saved final model + processor to {final}", flush=True)

    if hub_repo:
        trainer.push_to_hub()           # model + training state
        processor.push_to_hub(hub_repo)  # tokenizer + feature extractor
        print(f"[train] pushed model + processor to HF Hub: {hub_repo}", flush=True)

    return trainer, processor
