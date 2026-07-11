from __future__ import annotations

import hashlib
from pathlib import Path

from api.settings import settings


def parts_dir(upload_id: str) -> Path:
    path = settings.uploads_dir / upload_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def part_path(upload_id: str, index: int) -> Path:
    return parts_dir(upload_id) / f"part_{index:05d}"


def write_part(upload_id: str, index: int, data: bytes) -> None:
    part_path(upload_id, index).write_bytes(data)


def list_part_indices(upload_id: str) -> list[int]:
    directory = settings.uploads_dir / upload_id
    if not directory.exists():
        return []
    indices: list[int] = []
    for entry in directory.iterdir():
        try:
            indices.append(int(entry.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return sorted(indices)


def assemble(upload_id: str, dest: Path) -> int:
    """Concatenate parts in index order into ``dest``; return total bytes."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with dest.open("wb") as out:
        for index in list_part_indices(upload_id):
            data = part_path(upload_id, index).read_bytes()
            out.write(data)
            total += len(data)
    return total


def remove(upload_id: str) -> None:
    directory = settings.uploads_dir / upload_id
    if not directory.exists():
        return
    for entry in directory.iterdir():
        try:
            entry.unlink()
        except OSError:
            continue
    try:
        directory.rmdir()
    except OSError:
        pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()
