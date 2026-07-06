"""Download verse-segmented Quran audio from everyayah.com and convert to 16kHz WAV.

URL format: ``https://everyayah.com/data/<ReciterFolder>/<SSSAAA>.mp3`` where
``SSS`` is the 3-digit surah and ``AAA`` the 3-digit ayah. One MP3 per verse.

Features:
  * concurrent download (ThreadPoolExecutor) with a polite QPS rate limiter
  * resume: skip if WAV exists; convert from MP3 if only the MP3 is present
  * atomic writes (.part -> rename) + MD5 sidecar for integrity
  * MP3 -> 16 kHz mono WAV via ffmpeg (librosa fallback)
  * 404-tolerant (some reciters omit the basmala) — logged, not fatal
  * per-reciter manifest.jsonl: {surah, ayah, path, duration, md5, sample_rate}
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

EVERYAYAH_BASE = "https://everyayah.com/data"
_CHUNK = 1 << 14  # 16 KiB download chunks


@dataclass
class DownloadResult:
    surah: int
    ayah: int
    ok: bool
    status: str  # "cached" | "downloaded" | "converted" | "missing" | "error"
    path: str | None = None
    duration: float = 0.0
    md5: str | None = None
    error: str | None = None


def audio_url(reciter_folder: str, surah: int, ayah: int) -> str:
    return f"{EVERYAYAH_BASE}/{reciter_folder}/{surah:03d}{ayah:03d}.mp3"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

class _RateLimiter:
    """Thread-safe token spacing — keeps us under `qps` requests/second."""

    def __init__(self, qps: float):
        self._interval = 1.0 / qps if qps and qps > 0 else 0.0
        self._lock = threading.Lock()
        self._next = 0.0

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next - now
            self._next = max(now, self._next) + self._interval
        if wait > 0:
            time.sleep(wait)


def _md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def _probe_duration(path: Path) -> float:
    """Duration in seconds via ffprobe; falls back to soundfile then librosa."""
    try:
        import subprocess

        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, check=True,
        )
        return float(out.stdout.strip())
    except Exception:
        pass
    try:
        import soundfile as sf

        info = sf.info(str(path))
        return info.frames / info.samplerate
    except Exception:
        pass
    import librosa

    return float(librosa.get_duration(path=str(path)))


def _convert_to_wav(mp3: Path, wav: Path, sample_rate: int) -> None:
    """MP3 -> mono WAV at `sample_rate` via ffmpeg (librosa fallback)."""
    try:
        import subprocess

        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3),
             "-ar", str(sample_rate), "-ac", "1", "-sample_fmt", "s16", str(wav)],
            check=True,
        )
        return
    except Exception:
        if wav.exists():
            wav.unlink()
    # fallback: librosa + soundfile
    import librosa
    import soundfile as sf

    y, _ = librosa.load(str(mp3), sr=sample_rate, mono=True)
    sf.write(str(wav), y, sample_rate)


# ---------------------------------------------------------------------------
# single-ayah download
# ---------------------------------------------------------------------------

def download_one(
    reciter_folder: str,
    surah: int,
    ayah: int,
    out_dir: Path,
    sample_rate: int = 16000,
    keep_mp3: bool = False,
    convert: bool = True,
    retries: int = 4,
    timeout: float = 30.0,
    limiter: _RateLimiter | None = None,
) -> DownloadResult:
    stem = f"{surah:03d}{ayah:03d}"
    wav_path = out_dir / f"{stem}.wav"
    mp3_path = out_dir / f"{stem}.mp3"
    md5_path = out_dir / f"{stem}.md5"

    # 1. already fully processed
    if convert and wav_path.exists():
        return DownloadResult(surah, ayah, ok=True, status="cached",
                              path=str(wav_path), duration=_probe_duration(wav_path),
                              md5=md5_path.read_text().strip() if md5_path.exists() else None)
    if not convert and mp3_path.exists():
        return DownloadResult(surah, ayah, ok=True, status="cached", path=str(mp3_path),
                              duration=_probe_duration(mp3_path),
                              md5=_md5_file(mp3_path) if md5_path.exists() else None)

    # 2. need the MP3 — fetch if not present
    if not mp3_path.exists():
        url = audio_url(reciter_folder, surah, ayah)
        last_err: str | None = None
        for attempt in range(retries):
            if limiter is not None:
                limiter.acquire()
            try:
                resp = requests.get(url, timeout=timeout, stream=True)
                if resp.status_code == 404:
                    return DownloadResult(surah, ayah, ok=False, status="missing",
                                          error="HTTP 404")
                resp.raise_for_status()
                part = mp3_path.with_suffix(".mp3.part")
                h = hashlib.md5()
                with part.open("wb") as fh:
                    for chunk in resp.iter_content(_CHUNK):
                        if chunk:
                            fh.write(chunk)
                            h.update(chunk)
                part.replace(mp3_path)
                md5_path.write_text(h.hexdigest())
                last_err = None
                break
            except (requests.RequestException, OSError) as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                time.sleep(0.5 * (2 ** attempt))  # 0.5, 1, 2, 4 s
        else:
            return DownloadResult(surah, ayah, ok=False, status="error", error=last_err)

    md5 = md5_path.read_text().strip() if md5_path.exists() else _md5_file(mp3_path)

    # 3. convert to WAV
    if convert:
        try:
            _convert_to_wav(mp3_path, wav_path, sample_rate)
        except Exception as exc:
            return DownloadResult(surah, ayah, ok=False, status="error",
                                  error=f"convert failed: {exc}")
        if not keep_mp3:
            mp3_path.unlink(missing_ok=True)
        result_path, duration = wav_path, _probe_duration(wav_path)
        status = "downloaded"
    else:
        result_path, duration = mp3_path, _probe_duration(mp3_path)
        status = "downloaded"

    return DownloadResult(surah, ayah, ok=True, status=status, path=str(result_path),
                          duration=duration, md5=md5)


# ---------------------------------------------------------------------------
# batch driver
# ---------------------------------------------------------------------------

def download_audio(
    reciter_folder: str,
    ayah_keys: list[tuple[int, int]],
    audio_dir: str | Path,
    sample_rate: int = 16000,
    max_workers: int = 8,
    rate_limit_qps: float = 20.0,
    keep_mp3: bool = False,
    convert: bool = True,
    retries: int = 4,
    progress: bool = True,
) -> list[DownloadResult]:
    """Download + convert every (surah, ayah) for one reciter.

    Writes ``<audio_dir>/<reciter_folder>/manifest.jsonl``."""
    out_dir = Path(audio_dir) / reciter_folder
    out_dir.mkdir(parents=True, exist_ok=True)
    limiter = _RateLimiter(rate_limit_qps)
    results: list[DownloadResult] = [None] * len(ayah_keys)  # type: ignore[list-item]

    try:
        from tqdm import tqdm
        bar = tqdm(total=len(ayah_keys), desc=reciter_folder, disable=not progress)
    except ImportError:
        bar = None

    def _work(idx_key: tuple[int, tuple[int, int]]) -> tuple[int, DownloadResult]:
        idx, (surah, ayah) = idx_key
        return idx, download_one(reciter_folder, surah, ayah, out_dir, sample_rate,
                                 keep_mp3, convert, retries, limiter=limiter)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_work, (i, k)): i for i, k in enumerate(ayah_keys)}
        for fut in as_completed(futures):
            idx, res = fut.result()
            results[idx] = res
            if bar:
                bar.update(1)
                if not res.ok and res.status == "error":
                    bar.write(f"  ERROR {res.surah}:{res.ayah} — {res.error}")
    if bar:
        bar.close()

    # persist manifest — MERGE with existing so partial downloads accumulate
    # (downloading surah A then surah B must not erase A's entries).
    manifest = out_dir / "manifest.jsonl"
    existing: dict[tuple[int, int], dict] = {}
    if manifest.exists():
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                existing[(r["surah"], r["ayah"])] = r
    for r in results:
        existing[(r.surah, r.ayah)] = asdict(r)
    with manifest.open("w", encoding="utf-8") as fh:
        for key in sorted(existing):
            fh.write(json.dumps(existing[key], ensure_ascii=False) + "\n")

    return results


def summarize(results: list[DownloadResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts
