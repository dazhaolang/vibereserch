import importlib.metadata as importlib_metadata
import os
import sys
import types
from types import SimpleNamespace

import pytest

# Pydantic 的 EmailStr 依赖 email_validator，可在测试环境中使用轻量 stub
if "email_validator" not in sys.modules:  # pragma: no cover - import hook
    email_validator = types.ModuleType("email_validator")

    class _EmailError(ValueError):
        pass

    def _validate_email(value, *_, **__):
        return SimpleNamespace(email=value)

    email_validator.EmailNotValidError = _EmailError
    email_validator.validate_email = _validate_email
    sys.modules["email_validator"] = email_validator


_original_version = getattr(importlib_metadata, "version", None)


def _version(name):  # pragma: no cover - compatibility shim
    if name == "email-validator":
        return "2.0.0"
    if _original_version is None:
        raise importlib_metadata.PackageNotFoundError(name)
    return _original_version(name)


importlib_metadata.version = _version


os.environ.setdefault("OPENAI_API_KEY", "test-key")

from app.api.intelligent_interaction import start_intelligent_interaction
from app.api.literature import list_literature
from app.models.project import Project
from app.models.literature import Literature
from app.schemas.interaction_schemas import InteractionStartRequest


class _FilterCapturingQuery:
    """Test helper capturing SQLAlchemy filter条件。"""

    def __init__(self):
        self.filters = []

    def filter(self, *criteria):
        self.filters.extend(criteria)
        return self

    def first(self):
        return object()


@pytest.mark.asyncio
async def test_start_interaction_filters_by_owner_id(monkeypatch):
    captured_query = _FilterCapturingQuery()

    class _FakeDB:
        def query(self, model):
            assert model is Project
            return captured_query

    class _DummyEngine:
        def __init__(self, db):
            self.db = db

        async def create_interaction_session(self, **kwargs):  # pragma: no cover - simple stub
            return {
                "success": True,
                "session_id": "test-session",
                "requires_clarification": False,
                "direct_result": {"status": "ok"},
            }

    monkeypatch.setattr(
        "app.api.intelligent_interaction.IntelligentInteractionEngine",
        _DummyEngine,
    )

    request = InteractionStartRequest(
        project_id=1,
        context_type="search",
        user_input="测试",
    )
    current_user = SimpleNamespace(id=42)

    response = await start_intelligent_interaction(request, db=_FakeDB(), current_user=current_user)

    assert response.success is True
    owner_filters = [
        criterion
        for criterion in captured_query.filters
        if getattr(getattr(criterion, "left", None), "key", None) == "owner_id"
    ]
    assert owner_filters, "查询应当基于 Project.owner_id 过滤"


@pytest.mark.asyncio
async def test_list_literature_joins_owner_filter(monkeypatch):
    captured_filters = []

    class _FakeLiteratureQuery:
        def join(self, model):
            assert model is Project
            return self

        def filter(self, *criteria):
            captured_filters.extend(criteria)
            return self

        def offset(self, _):
            return self

        def limit(self, _):
            return self

        def all(self):
            return []

    class _FakeDB:
        def query(self, model):
            if model is Literature:
                return _FakeLiteratureQuery()
            raise AssertionError("Unexpected model query")

    result = await list_literature(
        page=1,
        page_size=20,
        project_id=None,
        current_user=SimpleNamespace(id=99),
        db=_FakeDB(),
    )

    assert result == []
    owner_filters = [
        criterion
        for criterion in captured_filters
        if getattr(getattr(criterion, "left", None), "key", None) == "owner_id"
    ]
    assert owner_filters, "联结查询必须使用 Project.owner_id 过滤"
