from unittest.mock import MagicMock
import sys
import types

import pytest
celery_stub = types.SimpleNamespace(
    search_and_build_library_celery=types.SimpleNamespace(delay=lambda *a, **k: None),
    ai_search_batch_celery=types.SimpleNamespace(delay=lambda *a, **k: None),
    literature_collection_celery=types.SimpleNamespace(delay=lambda *a, **k: None),
    literature_processing_celery=types.SimpleNamespace(delay=lambda *a, **k: None),
    experience_generation_celery=types.SimpleNamespace(delay=lambda *a, **k: None),
    literature_index_celery=types.SimpleNamespace(delay=lambda *a, **k: None),
    download_pdf_celery=types.SimpleNamespace(delay=lambda *a, **k: None),
)

sys.modules.setdefault("app.tasks.celery_tasks", celery_stub)


from app.models.task import Task, TaskType  # type: ignore
from app.models.project import Project  # type: ignore
from app.services.task_service import TaskService


def _make_task(task_type: str, *, config=None, input_data=None, owner_id: int = 1) -> Task:
    task = Task(
        project_id=1,
        task_type=task_type,
        title="t",
        description="d",
        config=config or {},
        input_data=input_data or {},
    )
    task.id = 42
    # Create a Project instance for the task
    task.project = Project(name="Test Project", owner_id=owner_id)
    task.project.id = task.project_id  # keep ids aligned for assertions
    return task


def _patch_celery(monkeypatch, dotted_name):
    calls = []

    def fake_delay(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})

    monkeypatch.setattr(dotted_name, fake_delay)
    return calls


def test_dispatch_search_and_build(monkeypatch):
    calls = _patch_celery(monkeypatch, "app.services.task_service.search_and_build_library_celery.delay")
    service = TaskService(MagicMock())
    task = _make_task("search_and_build_library", config={"keywords": ["ai"]})

    service._dispatch_task(task)

    assert calls, "search_build dispatch should invoke celery"
    args = calls[0]["args"]
    assert args[0] == task.id
    assert args[1] == ["ai"]
    assert args[2] == task.project_id


def test_dispatch_ai_collection(monkeypatch):
    calls = _patch_celery(monkeypatch, "app.services.task_service.ai_search_batch_celery.delay")
    service = TaskService(MagicMock())
    task = _make_task(
        TaskType.LITERATURE_COLLECTION.value,
        config={"search_mode": "ai_batch", "query": "ml", "max_results": 10},
    )

    service._dispatch_task(task)

    assert calls
    args = calls[0]["args"]
    assert args == (task.id, "ml", 10)


def test_dispatch_standard_collection(monkeypatch):
    calls = _patch_celery(monkeypatch, "app.services.task_service.literature_collection_celery.delay")
    service = TaskService(MagicMock())
    task = _make_task(
        TaskType.LITERATURE_COLLECTION.value,
        config={"keywords": ["biology"], "max_count": 5, "sources": ["researchrabbit"]},
    )

    service._dispatch_task(task)

    assert calls
    args = calls[0]["args"]
    assert args == (task.id, ["biology"], 5, ["researchrabbit"])


def test_dispatch_experience(monkeypatch):
    calls = _patch_celery(monkeypatch, "app.services.task_service.experience_generation_celery.delay")
    service = TaskService(MagicMock())
    task = _make_task(
        "experience_generation",
        input_data={"research_question": "测试问题"},
    )

    service._dispatch_task(task)

    assert calls
    assert calls[0]["args"] == (task.id, "测试问题")


def test_dispatch_pdf_processing(monkeypatch):
    calls = _patch_celery(monkeypatch, "app.services.task_service.download_pdf_celery.delay")
    service = TaskService(MagicMock())
    task = _make_task(
        TaskType.PDF_PROCESSING.value,
        config={"literature_id": 99},
    )

    service._dispatch_task(task)

    assert calls
    assert calls[0]["args"] == (99, task.project.owner_id, task.id)


def test_dispatch_pdf_missing_id(monkeypatch):
    service = TaskService(MagicMock())
    task = _make_task(TaskType.PDF_PROCESSING.value)

    with pytest.raises(ValueError):
        service._dispatch_task(task)


def test_dispatch_unknown_task(monkeypatch):
    service = TaskService(MagicMock())
    task = _make_task("unknown_task")

    with pytest.raises(ValueError):
        service._dispatch_task(task)
