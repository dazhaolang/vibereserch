"""MySQL-backed integration coverage for user registration flows."""

from __future__ import annotations

import os
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

# Ensure the backend starts in lightweight mode during tests to avoid heavy init
os.environ.setdefault("LIGHTWEIGHT_MODE", "true")

from app.main import app
from app.core.database import Base, SessionLocal, engine
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import MembershipType, User, UserMembership


@pytest.fixture(scope="session", autouse=True)
def ensure_mysql() -> None:
    """Skip the module if the configured MySQL database is unavailable."""

    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:  # pragma: no cover - guard for local dev
        pytest.skip(f"MySQL is required for registration tests: {exc}")

    Base.metadata.create_all(bind=engine)


@pytest.fixture
def db_session() -> SessionLocal:
    """Provide a transactional session rolled back after each test."""

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def api_client() -> TestClient:
    """Instantiate a FastAPI test client with lightweight lifecycle."""

    with TestClient(app) as client:
        yield client


def _unique_email() -> str:
    return f"pytest-user-{uuid4().hex}@example.com"


def test_user_registration_directly(db_session) -> None:
    """Exercise ORM-level registration logic against MySQL."""

    email = _unique_email()
    password = f"Pw!{uuid4().hex[:8]}Aa1"

    user = User(
        email=email,
        username=f"pytest_{uuid4().hex[:6]}",
        hashed_password=get_password_hash(password),
        full_name="集成测试用户",
        institution="Integration Lab",
        research_field="AI",
        is_active=True,
    )

    db_session.add(user)
    db_session.flush()

    membership = UserMembership(
        user_id=user.id,
        membership_type=MembershipType.FREE,
        monthly_literature_used=0,
        monthly_queries_used=0,
        total_projects=0,
        auto_renewal=False,
    )
    db_session.add(membership)
    db_session.flush()

    stored_user = (
        db_session.query(User)
        .filter(User.email == email)
        .one()
    )
    assert stored_user.username == user.username
    assert stored_user.membership is not None
    assert verify_password(password, stored_user.hashed_password)

    token = create_access_token(
        data={"sub": str(stored_user.id)},
        expires_delta=timedelta(minutes=30),
    )
    assert isinstance(token, str) and token


def test_api_registration_flow(api_client) -> None:
    """Cover the HTTP registration + login + profile flow."""

    email = _unique_email()
    password = f"Pw!{uuid4().hex[:8]}Aa1"

    register_payload = {
        "email": email,
        "username": f"pytest_{uuid4().hex[:6]}",
        "password": password,
        "full_name": "API 测试用户",
        "institution": "API Testing Lab",
        "research_field": "Machine Learning",
    }

    try:
        register_response = api_client.post(
            "/api/auth/register",
            json=register_payload,
            timeout=10,
        )
        assert register_response.status_code == 200, register_response.text
        token_response = register_response.json()
        access_token = token_response["access_token"]
        assert token_response["user_info"]["email"] == email

        login_response = api_client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            timeout=10,
        )
        assert login_response.status_code == 200, login_response.text

        profile_response = api_client.get(
            "/api/user/profile",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        assert profile_response.status_code == 200, profile_response.text
        profile_data = profile_response.json()
        assert profile_data["email"] == email

    finally:
        with SessionLocal() as cleanup_session:
            user = cleanup_session.query(User).filter(User.email == email).first()
            if user:
                cleanup_session.query(UserMembership).filter(
                    UserMembership.user_id == user.id
                ).delete()
                cleanup_session.delete(user)
                cleanup_session.commit()
