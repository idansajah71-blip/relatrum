"""Ingestion orchestrator: validate -> store -> extract -> version -> spans.

Failure policy:
  * storage write failure rolls back cleanly (no Source row without bytes);
  * extraction failure still records the Source + version with
    extraction_status=failed so users can see what was attempted (never retried
    silently, original files are immutable).
"""
from __future__ import annotations

import secrets

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, ValidationFailedError
from app.domain.enums import ExtractionStatus, IngestionStatus
from app.models.source import Source, SourceVersion
from app.services.ingestion import extractors
from app.services.ingestion import provenance as _p
from app.services.ingestion import storage as _s
from app.services.ingestion import validation as _v
from app.utils.hashing import sha256_bytes, sha256_text


def ingest_file(
    db: Session,
    *,
    workspace_id: str,
    case_id: str,
    filename: str | None,
    content: bytes,
    uploaded_by: str,
    meta: dict,
) -> Source:
    spec = _v.validate_upload(
        filename=filename, content=content, max_upload_mb=_max_upload_mb()
    )
    file_hash = sha256_bytes(content)
    duplicate = _find_duplicate(db, workspace_id, file_hash)
    if duplicate is not None:
        raise ConflictError(
            "Duplicate upload: an identical file already exists in this "
            f"workspace (source id {duplicate.id}).",
            details={"existing_source_id": duplicate.id},
        )

    source = Source(
        workspace_id=workspace_id,
        case_id=case_id,
        source_type=meta.get("source_type") or "other",
        title=(meta.get("title") or _v._normalize_filename(filename) or "Untitled source")[:300],
        original_filename=_v._normalize_filename(filename),
        mime_type=spec.mime_type,
        file_size=spec.size,
        sha256=file_hash,
        source_origin=meta.get("source_origin") or "unknown",
        source_author=meta.get("source_author"),
        authority_label=meta.get("authority_label") or "unknown",
        sensitivity_level=meta.get("sensitivity_level") or "internal",
        source_date=meta.get("source_date"),
        captured_at=meta.get("captured_at"),
        ingestion_status=IngestionStatus.pending.value,
        created_by=uploaded_by,
    )
    db.add(source)
    db.flush()

    storage_key, storage_path = _s.build_object_key(workspace_id, source.id, spec.extension)
    _s.write_bytes(storage_path, content)
    source.storage_key = storage_key

    result = _run_extraction(storage_key, spec.extension)
    version = _persist_version(db, source, content, result)
    source.ingestion_status = (
        IngestionStatus.extracted.value
        if result.text
        else IngestionStatus.extraction_failed.value
    )
    db.add(version)
    db.commit()
    return source


def ingest_manual_text(
    db: Session,
    *,
    workspace_id: str,
    case_id: str,
    text: str,
    uploaded_by: str,
    title: str,
    meta: dict,
) -> Source:
    if not text.strip():
        raise ValidationFailedError("Manual report text is empty.")
    text_hash = sha256_text(text)
    duplicate = _find_duplicate(db, workspace_id, text_hash)
    if duplicate is not None:
        raise ConflictError(
            "Duplicate text report: identical content already exists in this "
            f"workspace (source id {duplicate.id}).",
            details={"existing_source_id": duplicate.id},
        )

    source = Source(
        workspace_id=workspace_id,
        case_id=case_id,
        source_type=meta.get("source_type") or "observation",
        title=(title or "Manual report")[:300],
        mime_type="text/plain",
        file_size=len(text.encode("utf-8")),
        sha256=text_hash,
        source_origin=meta.get("source_origin") or "user_provided",
        source_author=meta.get("source_author"),
        authority_label=meta.get("authority_label") or "user_provided",
        sensitivity_level=meta.get("sensitivity_level") or "internal",
        source_date=meta.get("source_date"),
        captured_at=meta.get("captured_at"),
        ingestion_status=IngestionStatus.pending.value,
        created_by=uploaded_by,
    )
    db.add(source)
    db.flush()

    from app.services.ingestion.extractors import ExtractionResult

    result = ExtractionResult(
        text=text,
        method="manual_entry",
        metadata={"manual": True},
    )
    version = _persist_version(db, source, None, result)
    source.ingestion_status = IngestionStatus.extracted.value
    db.add(version)
    db.commit()
    return source


def _run_extraction(storage_key: str, extension: str) -> "object":
    from app.services.ingestion.extractors import ExtractionResult

    try:
        content = _s.read_bytes(storage_key)
        return extractors.extract_text(extension, content)
    except ValidationFailedError:
        raise
    except Exception as exc:  # unexpected extractor crash still leaves a trace
        return ExtractionResult(
            text="",
            method=f"{extension}_failed",
            metadata={"error": f"extraction failed: {exc}"},
        )


def _persist_version(db: Session, source: Source, content: bytes | None, result) -> SourceVersion:
    from sqlalchemy import select

    next_number = (
        db.scalar(select(SourceVersion.version_number).where(SourceVersion.source_id == source.id)) or 0
    ) + 1
    version = SourceVersion(
        source_id=source.id,
        version_number=next_number,
        content_sha256=sha256_text(result.text) if result.text else None,
        extracted_text=result.text if result.text else None,
        extraction_method=result.method,
        extraction_status=(
            ExtractionStatus.success.value
            if result.text
            else ExtractionStatus.failed.value
        ),
        extraction_metadata=result.metadata,
    )
    if result.text:
        version.spans = _p.compute_spans(
            extracted_text=result.text,
            source_version_id=version.id,
            page_start_offsets=result.metadata.get("page_start_offsets"),
        )
    return version


def _find_duplicate(db: Session, workspace_id: str, content_hash: str) -> Source | None:
    from sqlalchemy import select

    return db.scalar(
        select(Source).where(
            Source.workspace_id == workspace_id,
            Source.sha256 == content_hash,
        )
    )


def _max_upload_mb() -> int:
    from app.config import get_settings

    return get_settings().max_upload_mb


def _nonce() -> str:
    return secrets.token_hex(8)
