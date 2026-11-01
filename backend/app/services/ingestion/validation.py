"""Upload validation: size, extension, MIME sniffing via magic bytes.

Security posture:
  * server-generated storage keys (never client-supplied paths);
  * extension allow-list plus magic-byte verification for PDF and DOCX;
  * hard size ceiling from settings.
"""
from __future__ import annotations

import zipfile
from dataclasses import dataclass

from app.core.exceptions import ValidationFailedError

ALLOWED_EXTENSIONS = {".txt", ".csv", ".pdf", ".docx", ".md"}
_MIME_BY_EXT = {
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@dataclass(frozen=True)
class FileSpec:
    extension: str
    mime_type: str
    size: int


def _normalize_filename(raw: str | None) -> str:
    """Return a safe filename substring: split path parts, strip unsafe chars."""
    if not raw:
        return "untitled"
    # Take only the final path component regardless of Windows/Unix separators.
    name = raw.replace("\\", "/").split("/")[-1]
    name = name.strip().strip(".")
    name = "".join(ch for ch in name if ch.isalnum() or ch in "._- ")
    return (name[:200] or "untitled").strip()


def validate_upload(
    *, filename: str | None, content: bytes, max_upload_mb: int
) -> FileSpec:
    safe_name = _normalize_filename(filename)
    lowered = safe_name.lower()
    ext = next((e for e in ALLOWED_EXTENSIONS if lowered.endswith(e)), None)
    if ext is None:
        raise ValidationFailedError(
            f"Unsupported file extension. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )
    size = len(content)
    max_bytes = max_upload_mb * 1024 * 1024
    if size == 0:
        raise ValidationFailedError("Uploaded file is empty.")
    if size > max_bytes:
        raise ValidationFailedError(
            f"Uploaded file exceeds the {max_upload_mb} MiB limit (got {size} bytes)."
        )
    _verify_magic_bytes(ext, content)
    return FileSpec(extension=ext, mime_type=_MIME_BY_EXT[ext], size=size)


def _verify_magic_bytes(ext: str, content: bytes) -> None:
    if ext == ".pdf":
        if not content.startswith(b"%PDF-"):
            raise ValidationFailedError("File does not look like a valid PDF (bad magic bytes).")
    elif ext == ".docx":
        if not zipfile.is_zipfile(
            __import__("io").BytesIO(content)
        ):
            raise ValidationFailedError("File does not look like a valid DOCX (not a valid OOXML zip).")
    # .txt/.csv/.md: no binary magic; decode check happens during extraction.
