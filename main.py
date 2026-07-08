"""Interactive launcher for local Quran ASR workflows."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from quran_asr.launcher import (  # noqa: E402
    DEFAULT_HF_MODEL,
    LOCAL_BEST_MODEL,
    LOCAL_LATEST_MODEL,
    SurahChoice,
    build_live_infer_command,
    build_train_command,
    filter_surahs,
    load_surah_choices,
)


def main() -> int:
    print("Quran ASR Launcher")
    while True:
        print("\nPilih workflow:")
        print("1. Live ASR dari mic")
        print("2. Rekam mic sekali lalu infer")
        print("3. Infer dari file audio")
        print("4. Train local manual fresh")
        print("5. Resume train local manual")
        print("0. Exit")
        choice = input("> ").strip()

        if choice == "0":
            return 0
        if choice == "1":
            return _run_inference(mode="live")
        if choice == "2":
            return _run_inference(mode="record")
        if choice == "3":
            return _run_inference(mode="audio")
        if choice == "4":
            return _run_command(build_train_command(resume=False))
        if choice == "5":
            return _run_command(build_train_command(resume=True))
        print("Pilihan tidak valid.")


def _run_inference(mode: str) -> int:
    model = _select_model()
    surah, ayah = _select_reference()
    device = _prompt("Device", default="auto")
    kwargs: dict[str, object] = {
        "model": model,
        "surah": surah,
        "ayah": ayah,
        "device": device,
    }

    if mode == "audio":
        kwargs["audio"] = _prompt("Audio path", required=True)
    elif mode == "record":
        kwargs["record_seconds"] = float(_prompt("Record seconds", default="5"))
    elif mode == "live":
        kwargs["live"] = True
        kwargs["chunk_seconds"] = float(_prompt("Chunk seconds", default="4"))
    else:
        raise ValueError(f"unknown inference mode: {mode}")

    return _run_command(build_live_infer_command(**kwargs))  # type: ignore[arg-type]


def _select_model() -> str:
    print("\nPilih model:")
    print(f"1. HF default ({DEFAULT_HF_MODEL})")
    print(f"2. Local best ({LOCAL_BEST_MODEL})")
    print(f"3. Local latest ({LOCAL_LATEST_MODEL})")
    print("4. Custom path / HF id")
    choice = _prompt("Model", default="1")
    if choice == "1":
        return DEFAULT_HF_MODEL
    if choice == "2":
        return LOCAL_BEST_MODEL
    if choice == "3":
        return LOCAL_LATEST_MODEL
    if choice == "4":
        return _prompt("Custom model", required=True)
    print("Pilihan model tidak valid, pakai HF default.")
    return DEFAULT_HF_MODEL


def _select_reference() -> tuple[int, int]:
    choices = load_surah_choices()
    surah = _select_surah(choices)
    ayah = int(_prompt(f"Ayat 1-{surah.ayah_count}", default="1"))
    while ayah < 1 or ayah > surah.ayah_count:
        print(f"Ayat harus 1 sampai {surah.ayah_count}.")
        ayah = int(_prompt(f"Ayat 1-{surah.ayah_count}", default="1"))
    return surah.number, ayah


def _select_surah(choices: list[SurahChoice]) -> SurahChoice:
    while True:
        print("\nPilih surat. Ketik nomor surat, atau /nama untuk filter.")
        _print_surahs(choices)
        raw = _prompt("Surat", default="94")
        query = raw[1:] if raw.startswith("/") else raw
        matches = filter_surahs(choices, query)
        if len(matches) == 1:
            selected = matches[0]
            print(f"Selected: {selected.number}. {selected.name} ({selected.ayah_count} ayat)")
            return selected
        if matches:
            _print_surahs(matches)
            raw = _prompt("Pilih nomor dari hasil filter", required=True)
            matches = filter_surahs(matches, raw)
            if len(matches) == 1:
                return matches[0]
        print("Surat tidak ditemukan.")


def _print_surahs(choices: list[SurahChoice]) -> None:
    for choice in choices:
        print(f"{choice.number:>3}. {choice.name:<18} ({choice.ayah_count:>3})")


def _prompt(label: str, default: str | None = None, required: bool = False) -> str:
    suffix = f" [{default}]" if default is not None else ""
    while True:
        value = input(f"{label}{suffix}: ").strip()
        if value:
            return value
        if default is not None:
            return default
        if not required:
            return ""
        print("Input wajib diisi.")


def _run_command(cmd: list[str]) -> int:
    print("\nRunning:")
    print(" ".join(cmd))
    return subprocess.run(cmd, cwd=PROJECT_ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
