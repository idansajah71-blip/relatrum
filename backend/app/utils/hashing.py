"""Hashing utilities: SHA-256 for content identity and deduplication."""
from __future__ import annotations

import hashlib
from pathlib import Path

_BLOCK = 1024 * 1024  # 1 MiB read blocks; bounded memory on large uploads


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(_BLOCK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()
