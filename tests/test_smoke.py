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
    assert c.run_name == "husary_mujawwad_v1"
    assert c.data.reciters[0] == "Husary_128kbps_Mujawwad"
    assert c.training.fp16 is True
    assert c.model.base == "facebook/wav2vec2-large-xlsr-53"
