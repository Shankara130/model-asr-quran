"""Audio downloader tests: pure unit (URL/summary) + network-gated integration."""

from __future__ import annotations

import os

import pytest

from quran_asr.data_pipeline.download_audio import (
    DownloadResult,
    audio_url,
    download_one,
    summarize,
)


def test_audio_url_format():
    assert audio_url("Husary_128kbps_Mujawwad", 1, 1) == (
        "https://everyayah.com/data/Husary_128kbps_Mujawwad/001001.mp3"
    )
    assert audio_url("X", 114, 6) == "https://everyayah.com/data/X/114006.mp3"


def test_summarize_counts():
    rs = [
        DownloadResult(1, 1, True, "downloaded"),
        DownloadResult(1, 2, True, "cached"),
        DownloadResult(1, 3, False, "missing"),
    ]
    assert summarize(rs) == {"downloaded": 1, "cached": 1, "missing": 1}


_RUN_NETWORK = bool(os.environ.get("RUN_NETWORK_TESTS"))
network = pytest.mark.skipif(not _RUN_NETWORK, reason="set RUN_NETWORK_TESTS=1 to run")


@network
def test_download_convert_and_cache(tmp_path):
    import soundfile as sf

    # fresh dir → downloads + converts
    r1 = download_one("Husary_128kbps_Mujawwad", 1, 1, tmp_path, sample_rate=16000)
    assert r1.ok and r1.status in ("downloaded", "cached")
    assert r1.duration > 0
    info = sf.info(r1.path)
    assert info.samplerate == 16000 and info.channels == 1

    # second call → cached, no re-download
    r2 = download_one("Husary_128kbps_Mujawwad", 1, 1, tmp_path, sample_rate=16000)
    assert r2.status == "cached"
