"""Shared data models for the search-and-build literature pipeline."""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


class ProcessingStage(Enum):
    """Pipeline stage identifiers."""

    INITIALIZATION = "initialization"
    SEARCH = "search"
    AI_FILTERING = "ai_filtering"
    PDF_DOWNLOAD = "pdf_download"
    CONTENT_EXTRACTION = "content_extraction"
    STRUCTURE_PROCESSING = "structure_processing"
    DATABASE_INGESTION = "database_ingestion"
    CLEANUP = "cleanup"
    COMPLETED = "completed"


@dataclass
class ProcessingConfig:
    """Configuration knobs for the search-build pipeline."""

    batch_size: int = 10
    max_concurrent_downloads: int = 5
    max_concurrent_ai_calls: int = 3
    enable_ai_filtering: bool = True
    enable_pdf_processing: bool = True
    enable_structured_extraction: bool = True
    quality_threshold: float = 6.0
    max_retries: int = 3
    timeout_seconds: int = 300
    max_results: int = 200


@dataclass
class ProcessingStats:
    """Aggregated pipeline statistics."""

    total_found: int = 0
    ai_filtered: int = 0
    pdf_downloaded: int = 0
    successfully_processed: int = 0
    structure_extracted: int = 0
    database_ingested: int = 0
    errors: int = 0
    duplicates: int = 0
    processing_time: float = 0.0


@dataclass
class LiteratureItem:
    """Intermediary representation of a search result item."""

    paper_id: str
    raw_data: Dict
    quality_score: float = 0.0
    is_duplicate: bool = False
    ai_filtered: bool = False
    pdf_path: Optional[str] = None
    content_extracted: bool = False
    structured_data: Optional[Dict] = None
    literature_id: Optional[int] = None
    error: Optional[str] = None
