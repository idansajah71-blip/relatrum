"""Statement extraction pipeline package."""
from app.services.extraction.service import (
    ExtractionReport,
    extract_statements_for_source,
    PIPELINE_VERSION,
)

__all__ = ["ExtractionReport", "extract_statements_for_source", "PIPELINE_VERSION"]
