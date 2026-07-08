from quran_asr.launcher import (
    DEFAULT_HF_MODEL,
    LOCAL_CONFIG,
    build_live_infer_command,
    build_train_command,
    filter_surahs,
    load_surah_choices,
)


def test_load_surah_choices_from_uthmani_dataset():
    choices = load_surah_choices()
    assert choices[0].number == 1
    assert choices[0].name == "Al-Fatihah"
    assert choices[0].ayah_count == 7
    assert choices[93].number == 94
    assert choices[93].name == "Ash-Sharh"
    assert choices[93].ayah_count == 8
    assert choices[-1].number == 114


def test_filter_surahs_by_number_or_name():
    choices = load_surah_choices()
    assert [s.number for s in filter_surahs(choices, "94")] == [94]
    assert [s.number for s in filter_surahs(choices, "sharh")] == [94]


def test_build_live_audio_command():
    cmd = build_live_infer_command(
        model=DEFAULT_HF_MODEL,
        audio="sample.wav",
        surah=94,
        ayah=1,
        device="cpu",
    )
    assert cmd[1:] == [
        "scripts/live_infer_asr.py",
        "--model",
        DEFAULT_HF_MODEL,
        "--surah",
        "94",
        "--ayah",
        "1",
        "--device",
        "cpu",
        "--audio",
        "sample.wav",
    ]


def test_build_live_mic_command():
    cmd = build_live_infer_command(
        model=DEFAULT_HF_MODEL,
        live=True,
        chunk_seconds=4,
        surah=94,
        ayah=1,
    )
    assert "--live" in cmd
    assert cmd[-2:] == ["--chunk-seconds", "4"]


def test_build_train_commands():
    fresh = build_train_command(resume=False)
    resume = build_train_command(resume=True)
    assert fresh[1:] == ["scripts/train_manual.py", "--config", LOCAL_CONFIG, "--no-resume"]
    assert resume[1:] == ["scripts/train_manual.py", "--config", LOCAL_CONFIG]
