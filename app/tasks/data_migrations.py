"""One-off data migration helpers for newly added fields."""

from typing import Any, Dict

from loguru import logger
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.literature import Literature, LiteratureSegment


def _ensure_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def populate_new_literature_fields() -> None:
    """Populate defaults for newly added literature columns."""
    db: Session = SessionLocal()
    updated = 0
    try:
        for literature in db.query(Literature).all():
            changed = False

            if literature.reference_count is None:
                literature.reference_count = 0
                changed = True

            if literature.fields_of_study is None:
                literature.fields_of_study = []
                changed = True

            if literature.external_ids is None:
                literature.external_ids = _ensure_dict(literature.external_ids)
                changed = True

            if literature.raw_data is None:
                literature.raw_data = {}
                changed = True

            if literature.is_open_access is None:
                literature.is_open_access = False
                changed = True

            if changed:
                updated += 1

        for segment in db.query(LiteratureSegment).all():
            if segment.extraction_method is None:
                segment.extraction_method = "unknown"
                updated += 1

        db.commit()
        logger.info(f"Data migration completed. Updated {updated} records.")
    except Exception as exc:
        db.rollback()
        logger.error(f"Data migration failed: {exc}")
        raise
    finally:
        db.close()
