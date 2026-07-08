"""Smoke tests: config defaults + YAML loading work. No heavy deps required."""

from __future__ import annotations

from pathlib import Path

from quran_asr.config import Config


def test_defaults():
    c = Config()
    assert c.data.sample_rate == 16000
    assert c.training.learning_rate == 3.0e-4
    assert c.data.split.strategy == "by_surah"
    assert c.data.split.test_surahs == [78, 93, 110]


def test_load_tiny_yaml(configs_dir: Path):
    c = Config.from_yaml(configs_dir / "tiny.yaml")
    assert c.run_name == "tiny_local"
    assert c.data.surahs == [1, 112, 113, 114]
    assert c.data.split.test_surahs == [114]
    assert c.training.fp16 is False  # MPS: fp16 off


def test_load_base_yaml(configs_dir: Path):
    c = Config.from_yaml(configs_dir / "base.yaml")
    assert c.run_name == "husary_mujawwad_local_3050_v1"
    assert c.data.reciters[0] == "Husary_128kbps_Mujawwad"
    assert c.training.fp16 is True
    assert c.model.base == "facebook/wav2vec2-large-xlsr-53"


def test_load_local_3050_manual_training_yaml(configs_dir: Path):
    c = Config.from_yaml(configs_dir / "local_3050.yaml")
    assert c.data.split.val_surahs == [88, 89, 90, 91, 92, 94, 95, 96, 97, 98, 99, 100]
    assert c.data.split.test_surahs == [78, 79, 80, 81, 82, 93, 109, 110, 112, 113, 114]
    assert c.model.apply_spec_augment is False
    assert c.training.warmup_ratio == 0.03
    assert c.training.encoder_trainable_layers == 0
    assert c.training.encoder_learning_rate == 1.0e-5
    assert c.training.head_learning_rate == 1.0e-3
    assert c.training.blank_logit_bias_init == -2.0
    assert c.training.auto_stage is True
    assert c.training.bootstrap_min_epochs == 3
    assert c.training.bootstrap_empty_threshold == 0.2
    assert c.training.bootstrap_max_epochs == 4
    assert c.training.bootstrap_head_learning_rate == 7.0e-4
    assert c.training.bootstrap_blank_logit_bias_init == -2.0
    assert c.training.finetune_encoder_trainable_layers == 1
    assert c.training.finetune_encoder_learning_rate == 5.0e-7
    assert c.training.finetune_head_learning_rate == 3.0e-4
    assert c.training.best_metric == "wer_plain"
    assert c.training.resume_from == "latest"
    assert c.logging.output_dir == "data/artifacts/checkpoints/local_3050_small"
