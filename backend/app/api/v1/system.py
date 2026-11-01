"""System information endpoint."""
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import engine, get_db
from app.schemas.common import Envelope
from typing import Any, Dict

router = APIRouter()


@router.get("/system/info", operation_id="system_info", response_model=Envelope)
def system_info(db: Session = Depends(get_db)) -> Dict[str, Any]:
    settings = get_settings()
    db_backend = engine.url.get_backend_name() if engine is not None else "uninitialized"
    tables: int = 0
    try:
        if db_backend == "sqlite":
            tables = db.execute(
                text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            ).scalar_one()
    except Exception:
        tables = 0
    return Envelope(
        message="RELATRUM backend operational.",
        data={
            "name": settings.app_name,
            "version": settings.app_version,
            "app_env": settings.app_env,
            "pipeline_version": settings.pipeline_version,
            "prompt_version": settings.prompt_version,
            "ai_provider": settings.ai_provider,
            "ai_provider_mode": (
                "deterministic_mock" if settings.ai_provider == "mock" else "external_llm"
            ),
            "database_backend": db_backend,
            "database_tables": tables,
            "limits": {
                "max_upload_mb": settings.max_upload_mb,
                "max_document_pages": settings.max_document_pages,
                "llm_max_calls_per_analysis": settings.llm_max_calls_per_analysis,
                "ai_timeout_seconds": settings.ai_timeout_seconds,
            },
            "analysis_disclosure": (
                "Statements, alignments, and findings are produced by deterministic local processing; "
                "no external AI inference is used in mock mode."
            )
            if settings.ai_provider == "mock"
            else "External LLM is enabled; all outputs remain traceable and require human review.",
        },
    )
