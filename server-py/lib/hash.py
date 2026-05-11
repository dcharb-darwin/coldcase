"""SHA-256 helpers."""

from __future__ import annotations

import hashlib


def hash_text(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: str, *, chunk_size: int = 1024 * 1024) -> tuple[str, int]:
    """Return (sha256_hex, byte_count)."""
    h = hashlib.sha256()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(chunk_size):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size
