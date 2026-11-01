"""Source endpoints: upload (multipart or manual text), list, versions, text."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import ConflictError, NotFoundError, PermissionDeniedError
from app.core.permissions import CurrentUser, require_workspace_member, resolve_case
from app.database import get_db
from app.domain.schemas import (
    EvidenceSpanRead,
    SourceManualText,
    SourceRead,
    SourceVersionRead,
)
from app.models.evidence import EvidenceSpan
from app.models.source import Source, SourceVersion
from app.models.user import User
from app.schemas.common import ok, page_meta
from app.services import audit
from app.services.ingestion import service as ingestion_service

router = APIRouter(tags=["sources"])


@router.post("/cases/{case_id}/sources", status_code=201)
async def upload_source(
    case_id: str,
    file: UploadFile | None = File(default=None),
    title: str | None = Form(default=None),
    source_type: str = Form(default="other"),
    source_origin: str = Form(default="unknown"),
    source_author: str | None = Form(default=None),
    authority_label: str = Form(default="unknown"),
    sensitivity_level: str = Form(default="internal"),
    source_date: str | None = Form(default=None),
    captured_at: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    case = resolve_case(db, user, case_id, min_role="editor")
    if file is None:
        raise NotFoundError("No file provided; attach multipart 'file'.")
    content = await file.read()
    meta = {
        "source_type": source_type,
        "source_origin": source_origin,
        "source_author": source_author,
        "authority_label": authority_label,
        "sensitivity_level": sensitivity_level,
        "source_date": source_date,
        "captured_at": captured_at,
    }
    try:
        source = ingestion_service.ingest_file(
            db,
            workspace_id=case.workspace_id,
            case_id=case.id,
            filename=file.filename,
            content=content,
            uploaded_by=user.id,
            meta=meta,
        )
    except ConflictError:
        raise
    except PermissionError as exc:
        raise PermissionDeniedError(str(exc)) from exc
    _audit_created(db, source, user)
    data = _read_source(db, source).model_dump(mode="json")
    if title:
        data["title"] = title
    return ok(data, "Source ingested.", status_code=201)


@router.post("/cases/{case_id}/sources/text", status_code=201)
def create_manual_source(
    case_id: str,
    payload: SourceManualText,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    case = resolve_case(db, user, case_id, min_role="editor")
    meta = payload.meta.model_dump()
    source = ingestion_service.ingest_manual_text(
        db,
        workspace_id=case.workspace_id,
        case_id=case.id,
        text=payload.text,
        uploaded_by=user.id,
        title=meta.get("title") or "Manual report",
        meta=meta,
    )
    _audit_created(db, source, user)
    return ok(_read_source(db, source).model_dump(mode="json"), "Manual report stored.", status_code=201)


@router.get("/cases/{case_id}/sources")
def list_sources(
    case_id: str,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    case = resolve_case(db, user, case_id)
    q = (
        db.query(Source)
        .filter(Source.case_id == case.id)
        .order_by(Source.created_at.desc())
    )
    total = q.count()
    rows = q.offset(max(offset, 0)).limit(min(max(limit, 1), 200)).all()
    data = [_read_source(db, s).model_dump(mode="json") for s in rows]
    return ok(data, meta=page_meta(total, min(max(limit, 1), 200), max(offset, 0)))


@router.get("/sources/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    source = _authorized_source(db, user, source_id)
    version = latest_version(db, source)
    text = version.extracted_text if version else None
    truncated = bool(text and len(text) > 40_000)
    data = _read_source(db, source, with_text=text[:40_000] if truncated else text, truncated=truncated)
    return ok(data.model_dump(mode="json"))


@router.get("/sources/{source_id}/versions")
def list_versions(source_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    source = _authorized_source(db, user, source_id)
    rows = (
        db.query(SourceVersion)
        .filter(SourceVersion.source_id == source.id)
        .order_by(SourceVersion.version_number.desc())
        .all()
    )
    return ok(
        [
            SourceVersionRead(
                id=v.id,
                source_id=v.source_id,
                version_number=v.version_number,
                content_sha256=v.content_sha256,
                extraction_method=v.extraction_method,
                extraction_status=v.extraction_status,
                created_at=v.created_at,
            ).model_dump(mode="json")
            for v in rows
        ]
    )


@router.get("/sources/{source_id}/versions/{version_id}/spans")
def list_spans(
    source_id: str, version_id: str, db: Session = Depends(get_db), user: User = CurrentUser
):
    source = _authorized_source(db, user, source_id)
    version = (
        db.query(SourceVersion)
        .filter(SourceVersion.source_id == source.id, SourceVersion.id == version_id)
        .first()
    )
    if version is None:
        raise NotFoundError(f"Version {version_id} not found for this source.")
    spans = (
        db.query(EvidenceSpan)
        .filter(EvidenceSpan.source_version_id == version.id)
        .order_by(EvidenceSpan.start_char.asc())
        .all()
    )
    return ok(
        [
            EvidenceSpanRead(
                id=sp.id,
                page_number=sp.page_number,
                start_char=sp.start_char,
                end_char=sp.end_char,
                exact_quote=sp.exact_quote,
                paragraph_index=sp.paragraph_index,
                section_heading=sp.section_heading,
            ).model_dump(mode="json")
            for sp in spans
        ]
    )


def latest_version(db: Session, source: Source) -> SourceVersion | None:
    return (
        db.query(SourceVersion)
        .filter(SourceVersion.source_id == source.id)
        .order_by(SourceVersion.version_number.desc())
        .first()
    )


def _authorized_source(db: Session, user: User, source_id: str) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise NotFoundError(f"Source {source_id} not found.")
    require_workspace_member(source.workspace_id, user, db, min_role="viewer")
    return source


def _read_source(
    db: Session,
    source: Source,
    *,
    with_text: str | None = None,
    truncated: bool = False,
) -> SourceRead:
    from app.domain.schemas import SourceWithText

    version_count = db.query(SourceVersion).filter(SourceVersion.source_id == source.id).count()
    span_count = (
        db.query(EvidenceSpan)
        .join(SourceVersion, EvidenceSpan.source_version_id == SourceVersion.id)
        .filter(SourceVersion.source_id == source.id)
        .count()
    )
    base = dict(
        id=source.id,
        workspace_id=source.workspace_id,
        case_id=source.case_id,
        source_type=source.source_type,
        title=source.title,
        original_filename=source.original_filename,
        mime_type=source.mime_type,
        file_size=source.file_size,
        sha256=source.sha256,
        source_origin=source.source_origin,
        source_author=source.source_author,
        authority_label=source.authority_label,
        sensitivity_level=source.sensitivity_level,
        source_date=source.source_date,
        captured_at=source.captured_at,
        ingestion_status=source.ingestion_status,
        version_count=version_count,
        span_count=span_count,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )
    if with_text is not None or truncated:
        return SourceWithText(**base, text=with_text, text_truncated=truncated)
    return SourceRead(**base)


def _audit_created(db: Session, source: Source, user: User) -> None:
    audit.record_event(
        db,
        workspace_id=source.workspace_id,
        actor_id=user.id,
        entity_type="source",
        entity_id=source.id,
        action="created",
        after_state={
            "source_type": source.source_type,
            "ingestion_status": source.ingestion_status,
            "sha256": source.sha256,
        },
    )


def max_upload_mb_config() -> int:
    return get_settings().max_upload_mb
