"""quran_asr — wav2vec2 Quran recitation ASR + word/diacritics-level correction.

Package layout:
  data_pipeline/  download audio (everyayah) + diacritized text (quran.com), build HF dataset
  tokenizer/      diacritics-aware CTC vocab + Wav2Vec2Processor
  training/       config-driven training entrypoint (shared by CLI + Colab notebook)
  alignment/      CTC forced alignment + word-level Corrector (4-status)
  evaluation/     WER/CER (diacritized & plain) + error-detection metrics
"""

__version__ = "0.1.0"
