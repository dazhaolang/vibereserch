"""Coverage for the persistent research share store."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.core.database import Base, SessionLocal, engine
from app.models.research_share import ResearchShare
from app.services.research_share_store import share_store


def _unique(value: str) -> str:
    return f"{value}-{uuid4().hex[:8]}"


def _prepare_task_graph() -> dict[str, int]:
    """Insert minimal user/project/task rows using raw SQL."""

    session = SessionLocal()
    try:
        email = _unique("share-test@example.com")
        username = _unique("share_user")

        user_id = session.execute(
            text(
                """
                INSERT INTO users (email, username, hashed_password, full_name, is_active, is_verified)
                VALUES (:email, :username, :hashed_password, :full_name, 1, 0)
                """
            ),
            {
                "email": email,
                "username": username,
                "hashed_password": "hashed",
                "full_name": "Share Test User",
            },
        ).lastrowid

        project_id = session.execute(
            text(
                """
                INSERT INTO projects (name, description, status, owner_id, max_literature_count, is_public)
                VALUES (:name, :description, 'active', :owner_id, :max_count, 0)
                """
            ),
            {
                "name": _unique("Share Project"),
                "description": "share store test",
                "owner_id": user_id,
                "max_count": 1000,
            },
        ).lastrowid

        task_id = session.execute(
            text(
                """
                INSERT INTO tasks (
                    project_id,
                    task_type,
                    title,
                    description,
                    status,
                    progress_percentage,
                    result,
                    token_usage,
                    cost_estimate
                )
                VALUES (
                    :project_id,
                    :task_type,
                    :title,
                    :description,
                    'completed',
                    100.0,
                    :result,
                    0.0,
                    0.0
                )
                """
            ),
            {
                "project_id": project_id,
                "task_type": "literature_collection",
                "title": "Collect literature",
                "description": "share store test task",
                "result": '{"mode": "auto", "main_answer": "done"}',
            },
        ).lastrowid

        session.commit()
        return {
            "task_id": task_id,
            "project_id": project_id,
            "user_id": user_id,
        }
    finally:
        session.close()


def _cleanup_graph(ids: dict[str, int]) -> None:
    with SessionLocal() as session:
        session.execute(
            text("DELETE FROM research_shares WHERE task_id = :task_id"),
            {"task_id": ids["task_id"]},
        )
        session.execute(
            text("DELETE FROM tasks WHERE id = :task_id"),
            {"task_id": ids["task_id"]},
        )
        session.execute(
            text("DELETE FROM projects WHERE id = :project_id"),
            {"project_id": ids["project_id"]},
        )
        session.execute(
            text("DELETE FROM users WHERE id = :user_id"),
            {"user_id": ids["user_id"]},
        )
        session.commit()


@pytest.fixture(scope="module", autouse=True)
def ensure_mysql() -> None:
    """Skip module if the configured MySQL database is unavailable."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:  # pragma: no cover - guard for local dev
        pytest.skip(f"MySQL is required for research share tests: {exc}")

    Base.metadata.create_all(bind=engine)


def test_create_share_persists_and_retrieves_record() -> None:
    ids = _prepare_task_graph()
    payload = {"task": {"id": ids["task_id"]}, "result": {"status": "completed"}}

    try:
        with SessionLocal() as session:
            record = share_store.create_share(
                session,
                task_id=ids["task_id"],
                base_url="https://example.com",
                payload=payload,
                emails=["test@example.com"],
                message="hello",
                ttl_minutes=5,
            )

        assert record.token
        assert record.share_url.startswith("https://example.com/share/research/")
        assert record.payload == payload
        assert record.emails == ("test@example.com",)

        with SessionLocal() as session:
            stored = session.get(ResearchShare, record.id)
            assert stored is not None
            assert stored.task_id == ids["task_id"]
            assert stored.accessed_at is None

        with SessionLocal() as session:
            fetched = share_store.get_share(session, record.token)
            assert fetched is not None
            assert fetched.token == record.token

        with SessionLocal() as session:
            refreshed = session.get(ResearchShare, record.id)
            assert refreshed is not None
            assert refreshed.accessed_at is not None

    finally:
        _cleanup_graph(ids)


def test_expired_share_is_deleted() -> None:
    ids = _prepare_task_graph()

    try:
        with SessionLocal() as session:
            record = share_store.create_share(
                session,
                task_id=ids["task_id"],
                base_url="http://local",
                payload={},
                emails=[],
                message=None,
                ttl_minutes=1,
            )

        # Force expiry by adjusting the timestamp directly.
        with SessionLocal() as session:
            stored = session.get(ResearchShare, record.id)
            assert stored is not None
            stored.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
            session.commit()

        with SessionLocal() as session:
            assert share_store.get_share(session, record.token) is None

        with SessionLocal() as session:
            assert session.get(ResearchShare, record.id) is None

    finally:
        _cleanup_graph(ids)
