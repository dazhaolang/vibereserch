# Repository Guidelines

## Project Structure & Module Organization
Backend code sits in `app/` with HTTP routers under `app/api/`, configuration helpers in `app/core/`, and background jobs in `app/services/`. Persisted models live in `app/models/` with aligned Pydantic schemas in `app/schemas/`. Database migrations land in `alembic/`, while reusable SQL snippets belong to `sql/`. The React client resides in `frontend/`, separating components (`frontend/src/components/`), pages (`frontend/src/pages/`), and shared hooks (`frontend/src/hooks/`). Pytest suites mirror backend packages in `tests/` and share fixtures via `tests/conftest.py`.

## Build, Test, and Development Commands
- `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` prepares the backend env.
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` starts the FastAPI server; pair with `celery -A app.celery worker --loglevel=info` for async jobs.
- `pytest` runs the backend tests; scope async checks using `pytest tests/test_task_service_dispatch.py -k async`.
- `npm install` bootstraps the frontend; `npm run dev`, `npm run lint`, and `npm run build` cover local dev, linting, and production bundles.
- `docker compose up mysql redis elasticsearch -d` spins up required services for integration work.

## Coding Style & Naming Conventions
Python files use 4-space indents and `black --line-length 88` for formatting. Modules stay snake_case, classes PascalCase, and functions descriptive verbs. FastAPI endpoints are `async def` with full type hints and return the documented schema (for example `LiteratureQueryResponse`). React components follow PascalCase filenames such as `ResearchDashboard.tsx`, directories stay kebab-case, and Tailwind utility classes handle styling.

## Testing Guidelines
Pytest with `pytest-asyncio` powers backend suites; decorate coroutines with `@pytest.mark.asyncio` and assert on serialized responses. Target ≥80% coverage, add at least one integration test per major feature using the FastAPI client, and update `scripts/test_integration.sh` whenever external services enter the flow.

## Commit & Pull Request Guidelines
Write imperative commit subjects ≤72 characters (e.g., `Add task retry policy`) and include a body when motivation helps reviewers. Pull requests should link related issues, note backend versus frontend impact, and list verification steps such as `pytest`, `npm run build`, or manual UI captures. Attach payload samples or screenshots whenever API contracts or components change.

## Security & Configuration Tips
Duplicate `.env.example` to `.env`, fill in local secrets, and keep credentials out of git. Align Docker hostnames with `docker compose` service names before running celery or tests. Exclude uploads, logs, and generated artifacts unless the change specifically requires them.
