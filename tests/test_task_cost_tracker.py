from unittest.mock import MagicMock

from app.models.task import Task
from app.models.project import Project
from app.services.task_cost_tracker import TaskCostTracker


def _make_task(task_id=1):
    task = Task(
        project_id=1,
        task_type="test",
        title="Task",
        description="Desc",
    )
    task.id = task_id
    # Create a Project instance for the task
    task.project = Project(name="Test Project", owner_id=1)
    task.project.id = task.project_id  # keep ids aligned for assertions
    return task


def test_record_usage_with_bound_session():
    tracker = TaskCostTracker()
    task = _make_task()

    session = MagicMock()
    query = session.query.return_value
    query.filter.return_value.first.return_value = task

    token = tracker.activate(task.id, session)
    tracker.record_usage(
        "gpt-4",
        {"total_tokens": 100, "prompt_tokens": 60, "completion_tokens": 40},
    )
    tracker.deactivate(token)

    assert task.token_usage == 100
    assert task.cost_estimate > 0


def test_record_usage_with_factory(monkeypatch):
    tracker = TaskCostTracker()
    task = _make_task(2)

    session = MagicMock()
    query = session.query.return_value
    query.filter.return_value.first.return_value = task

    tracker._session_factory = MagicMock(return_value=session)

    token = tracker.activate(task.id)
    tracker.record_usage(
        "gpt-3.5-turbo",
        {"total_tokens": 50, "prompt_tokens": 30, "completion_tokens": 20},
    )
    tracker.deactivate(token)

    assert task.token_usage == 50


def test_record_usage_without_context():
    tracker = TaskCostTracker()
    tracker.record_usage("gpt-4", {"total_tokens": 10})  # should no-op
