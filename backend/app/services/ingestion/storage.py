"""File storage: bytes land under server-generated keys; client input never joins paths."""
from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings

_SAFE_COMPONENT_RE = re.compile(r"^[a-f0-9-]{8,}$")
_SAFE_KEY_RE = re.compile(r"^[a-f0-9-]{8,}/[a-f0-9-]{8,}\.[a-zA-Z0-9]{1,10}$")


def storage_root() -> Path:
    settings = get_settings()
    root = settings.storage_path
    return root


def build_object_key(workspace_id: str, source_id: str, extension: str) -> tuple[str, Path]:
    """Generate a deterministic-safe storage key: workspace/source.ext.

    All components are verified: ids are our own UUID strings (hex + dash only)
    and the extension comes from the allow-list parser. Produces key + path.
    """
    if not _SAFE_COMPONENT_RE.match(workspace_id) or not _SAFE_COMPONENT_RE.match(source_id):
        raise ValueError("Malformed storage key components.")
    ext = extension if extension.startswith(".") else f".{extension}"
    key = f"{workspace_id}/{source_id}{ext}"
    if not _SAFE_KEY_RE.match(key):
        raise ValueError("Refusing nonconforming storage key.")
    return key, storage_root() / key


def write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write-then-rename keeps partial files from becoming readable state.
    temp = path.with_suffix(path.suffix + ".partial")
    with open(temp, "wb") as handle:
        handle.write(content)
    temp.replace(path)


def read_bytes(storage_key: str) -> bytes:
    """Storage lookup API: absolutely no traversal; keys must match our format."""
    if not _SAFE_KEY_RE.match(storage_key):
        raise ValueError("Invalid storage key.")
    path = storage_root() / storage_key
    if not path.is_file():
        raise FileNotFoundError(f"Stored object not found: key exists in DB but file missing.")
    with open(path, "rb") as handle:
        return handle.read()
