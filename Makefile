PYTHON ?= uv run python
CONFIG ?= configs/tiny.yaml

.PHONY: help setup download build vocab train eval align-demo test lint clean

help:           ## show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

setup:          ## create venv and install deps (uv sync)
	uv sync

preflight:      ## cloud pre-flight checks (GPU, ffmpeg, deps, HF token, disk)
	uv run python scripts/cloud_preflight.py

download:       ## fetch audio (everyayah) + diacritized text (quran.com)
	uv run python scripts/download.py --config $(CONFIG)

build:          ## assemble HF dataset from raw audio + text
	uv run python scripts/build.py --config $(CONFIG)

vocab:          ## build diacritics-aware CTC vocab.json
	uv run python scripts/build_vocab.py --config $(CONFIG)

train:          ## train (tiny config by default; cloud uses base.yaml + notebook)
	uv run python scripts/train.py --config $(CONFIG)

eval:           ## run evaluation harness
	uv run python scripts/evaluate.py --config $(CONFIG)

align-demo:     ## run the corrector on a sample wav
	uv run python scripts/correct.py --audio data/raw/audio/sample.wav --text "$(REF)"

test:           ## run pytest
	uv run pytest

lint:           ## ruff check + format
	uv run ruff check .
	uv run ruff format --check .

clean:          ## remove caches and build artifacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache build dist *.egg-info
