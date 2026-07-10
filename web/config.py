from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = Path(__file__).resolve().parent

MODEL_DIR = PROJECT_ROOT / "external" / "zipformer_p-quran"

MODEL_PATH = MODEL_DIR / "quran_phoneme_zipformer.int8.onnx"
TOKENS_PATH = MODEL_DIR / "tokens.txt"
PHONEME_MAP_PATH = MODEL_DIR / "quran_text2phoneme.json"
QURAN_TEXT_PATH = (
    MODEL_DIR
    / "data"
    / "reference"
    / "quran_verses_uthmani.json"
)

RESULTS_PATH = WEB_DIR / "data" / "test_results.jsonl"
FEEDBACK_PATH = WEB_DIR / "data" / "feedback.jsonl"

QARI_AUDIO_DIR = (
    PROJECT_ROOT
    / "data"
    / "raw"
    / "audio"
    / "Minshawy_Murattal_128kbps"
)

SAMPLE_RATE = 16_000


def validate_required_files() -> None:
    required_files = [
        MODEL_PATH,
        TOKENS_PATH,
        PHONEME_MAP_PATH,
        QURAN_TEXT_PATH,
    ]

    for path in required_files:
        if not path.exists():
            raise FileNotFoundError(f"File tidak ditemukan: {path}")