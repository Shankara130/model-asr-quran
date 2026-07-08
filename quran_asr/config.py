"""Configuration: dataclasses + YAML loader shared by the CLI scripts and the
Colab/Kaggle notebook. A single :class:`Config` drives every stage so there is
no logic fork between local and cloud runs."""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_type_hints

import yaml


@dataclass
class SplitConfig:
    """Anti-memorization split policy.

    The Quran is a fixed closed vocabulary, so a random per-ayah split lets the
    model memorize fixed verses. ``by_surah`` holds out whole surahs; once there
    are >=2 reciters, ``by_reciter`` adds a cross-speaker lens.
    """

    strategy: Literal["by_surah", "by_reciter"] = "by_surah"
    test_surahs: list[int] = field(default_factory=lambda: [78, 93, 110])
    val_surahs: list[int] = field(default_factory=lambda: [94, 109])
    val_frac_within_train: float = 0.05
    test_reciter: str | None = None


@dataclass
class DataConfig:
    reciters: list[str] = field(default_factory=lambda: ["Husary_128kbps_Mujawwad"])
    audio_dir: str = "data/raw/audio"
    text_path: str = "data/raw/text/quran_uthmani.json"
    processed_dir: str = "data/processed"
    sample_rate: int = 16000
    surahs: list[int] | Literal["all"] = "all"
    max_duration_sec: float = 60.0
    split: SplitConfig = field(default_factory=SplitConfig)


@dataclass
class ModelConfig:
    base: str = "facebook/wav2vec2-large-xlsr-53"
    vocab_path: str = "data/artifacts/vocab.json"
    freeze_feature_encoder_steps: int = 0
    apply_spec_augment: bool = True


@dataclass
class TrainingConfig:
    epochs: int = 30
    per_device_train_batch_size: int = 2
    per_device_eval_batch_size: int = 4
    gradient_accumulation_steps: int = 8
    learning_rate: float = 3.0e-4
    warmup_ratio: float = 0.1
    weight_decay: float = 0.0
    gradient_checkpointing: bool = True
    fp16: bool = True
    masking_time_prob: float = 0.05
    eval_steps: int = 500
    save_steps: int = 500
    early_stopping_patience: int = 5
    encoder_trainable_layers: int = 0
    encoder_learning_rate: float | None = None
    head_learning_rate: float | None = None
    max_grad_norm: float = 0.5
    best_metric: Literal["eval_loss", "wer", "cer", "wer_plain", "cer_plain"] = "wer_plain"
    greater_is_better: bool = False
    resume_from: Literal["best", "latest", "none"] = "latest"
    eval_decode_samples: int = 0
    blank_logit_bias_init: float = 0.0
    auto_stage: bool = False
    bootstrap_min_epochs: int = 3
    bootstrap_max_epochs: int = 4
    bootstrap_empty_threshold: float = 0.2
    bootstrap_encoder_trainable_layers: int = 0
    bootstrap_encoder_learning_rate: float = 1.0e-5
    bootstrap_head_learning_rate: float = 1.0e-3
    bootstrap_blank_logit_bias_init: float = -2.0
    bootstrap_apply_spec_augment: bool = False
    finetune_encoder_trainable_layers: int = 2
    finetune_encoder_learning_rate: float = 5.0e-7
    finetune_head_learning_rate: float = 3.0e-4
    finetune_apply_spec_augment: bool = False


@dataclass
class LoggingConfig:
    hub_repo: str | None = None
    output_dir: str = "data/artifacts/checkpoints"


@dataclass
class Config:
    run_name: str = "run"
    seed: int = 42
    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        return _coerce(cls, data)  # type: ignore[return-value]

    @classmethod
    def from_yaml(cls, path: str | Path) -> Config:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        return cls.from_dict(data)


def _coerce(cls: Any, value: Any) -> Any:
    """Recursively build a dataclass instance from a (possibly nested) dict.

    Only descends when ``value`` is a dict and ``cls`` is a dataclass; lists and
    scalars pass through unchanged."""
    if dataclasses.is_dataclass(cls) and isinstance(value, dict):
        hints = get_type_hints(cls)
        kwargs: dict[str, Any] = {}
        for f in dataclasses.fields(cls):
            if f.name in value:
                kwargs[f.name] = _coerce(hints.get(f.name, f.type), value[f.name])
        return cls(**kwargs)
    return value
