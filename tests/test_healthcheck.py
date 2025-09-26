import pytest
from types import SimpleNamespace

from app.services import healthcheck


@pytest.mark.asyncio
async def test_check_celery_parses_worker_list(monkeypatch):
    responses = [
        {"celery@worker-a": {"ok": "pong"}},
        {"celery@worker-b": {"ok": "pong"}},
    ]
    dummy_app = SimpleNamespace(control=SimpleNamespace(ping=lambda timeout=3: responses))
    monkeypatch.setattr(healthcheck, "celery_app", dummy_app)

    result = await healthcheck.health_service.check_celery()

    assert result.name == "celery"
    assert result.status == "healthy"
    assert result.details["active_workers"] == 2
    assert sorted(result.details["workers"]) == ["celery@worker-a", "celery@worker-b"]


@pytest.mark.asyncio
async def test_check_celery_handles_unexpected_payload(monkeypatch):
    responses = [{}]
    dummy_app = SimpleNamespace(control=SimpleNamespace(ping=lambda timeout=3: responses))
    monkeypatch.setattr(healthcheck, "celery_app", dummy_app)

    result = await healthcheck.health_service.check_celery()

    assert result.status == "degraded"
    assert result.details["active_workers"] == 0
    assert result.details["error"] == "unexpected ping response format"


@pytest.mark.asyncio
async def test_check_celery_marks_unhealthy_without_workers(monkeypatch):
    responses = []
    dummy_app = SimpleNamespace(control=SimpleNamespace(ping=lambda timeout=3: responses))
    monkeypatch.setattr(healthcheck, "celery_app", dummy_app)

    result = await healthcheck.health_service.check_celery()

    assert result.status == "unhealthy"
    assert result.details["error"] == "no workers responding"
