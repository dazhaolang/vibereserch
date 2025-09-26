"""Persistent share token store for research results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Dict, Optional, Sequence
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_share import ResearchShare


@dataclass(frozen=True)
class ShareRecord:
    """Immutable snapshot of a research share entry."""

    id: int
    token: str
    task_id: int
    created_at: datetime
    expires_at: datetime
    share_url: str
    emails: Sequence[str]
    message: Optional[str]
    payload: Dict[str, object]

    def is_expired(self, *, reference: Optional[datetime] = None) -> bool:
        reference_time = reference or datetime.now(timezone.utc)
        return reference_time >= self.expires_at


class ResearchShareStore:
    """Database-backed share storage with TTL semantics."""

    def __init__(self) -> None:
        self._lock = Lock()

    @staticmethod
    def _ensure_aware(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value

    def _generate_unique_token(self, db: Session) -> str:
        """Generate a unique token guarded by a pessimistic check."""

        for _ in range(10):
            candidate = secrets.token_urlsafe(24)
            exists = db.execute(
                select(ResearchShare.id).where(ResearchShare.token == candidate)
            ).scalar_one_or_none()
            if not exists:
                return candidate
        raise RuntimeError("Unable to generate unique share token after multiple attempts")

    def _purge_expired(self, db: Session, *, reference: Optional[datetime] = None) -> None:
        """Remove expired share rows eagerly to limit table growth."""

        now = reference or datetime.now(timezone.utc)
        db.query(ResearchShare).filter(ResearchShare.expires_at <= now).delete(
            synchronize_session=False
        )

    @staticmethod
    def _to_record(entry: ResearchShare) -> ShareRecord:
        return ShareRecord(
            id=entry.id,
            token=entry.token,
            task_id=entry.task_id,
            created_at=ResearchShareStore._ensure_aware(entry.created_at),
            expires_at=ResearchShareStore._ensure_aware(entry.expires_at),
            share_url=entry.share_url,
            emails=tuple(entry.emails or ()),
            message=entry.message,
            payload=entry.payload or {},
        )

    def create_share(
        self,
        db: Session,
        *,
        task_id: int,
        base_url: str,
        payload: Dict[str, object],
        emails: Sequence[str],
        message: Optional[str],
        ttl_minutes: int = 60,
    ) -> ShareRecord:
        """Persist and return a new share record."""

        ttl = max(1, ttl_minutes)
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl)

        with self._lock:
            token = self._generate_unique_token(db)

        share_url = base_url.rstrip('/') + f"/share/research/{task_id}?token={token}"

        self._purge_expired(db, reference=now)

        entry = ResearchShare(
            token=token,
            task_id=task_id,
            share_url=share_url,
            emails=list(emails),
            message=message,
            payload=payload,
            expires_at=expires_at,
        )

        db.add(entry)
        db.commit()
        db.refresh(entry)
        return self._to_record(entry)

    def get_share(self, db: Session, token: str) -> Optional[ShareRecord]:
        """Fetch a share record, enforcing TTL semantics."""

        entry = db.execute(
            select(ResearchShare).where(ResearchShare.token == token)
        ).scalar_one_or_none()

        if not entry:
            return None

        now = datetime.now(timezone.utc)
        expires_at = self._ensure_aware(entry.expires_at)

        if expires_at is None:
            expires_at = now

        if expires_at <= now:
            db.delete(entry)
            db.commit()
            return None

        entry.accessed_at = now
        db.commit()
        db.refresh(entry)
        return self._to_record(entry)


share_store = ResearchShareStore()
