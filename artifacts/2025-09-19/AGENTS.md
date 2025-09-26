# Repository Guidelines

## Project Structure & Module Organization
The FastAPI backend lives in `app/`; keep new HTTP routes inside `app/api/`, configuration helpers in `app/core/`, and long-running jobs in `app/services/`. Persisted entities belong in `app/models/` with matching validation schemas in `app/schemas/` so ORM and API stay aligned. Database migrations sit in `alembic/` and custom SQL helpers in `sql/`. The React frontend is housed in `frontend/` with components in `frontend/src/components/`, page flows in `frontend/src/pages/`, and shared hooks in `frontend/src/hooks/`. Pytest suites mirror backend packages under `tests/` and reuse fixtures via `tests/conftest.py`.

## Build, Test, and Development Commands
- `python -m venv venv && source venv/bin/activate && pip install -r requirements.txt` prepares the backend environment.
- `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` launches the API; pair it with `celery -A app.celery worker --loglevel=info` for background jobs.
- `pytest` runs the backend suite; filter async cases with `pytest tests/test_task_service_dispatch.py -k async`.
- `npm install` sets up the frontend, while `npm run dev`, `npm run lint`, and `npm run build` cover local serve, linting, and production builds.
- `docker compose up mysql redis elasticsearch -d` brings required services online for integration work.

## Coding Style & Naming Conventions
Format Python using `black --line-length 88`; keep modules in snake_case, classes in PascalCase, and variables descriptive. All API endpoints should be `async def` with type hints and return the documented schema (e.g., `LiteratureQueryResponse`). React files use PascalCase component names (`ResearchDashboard.tsx`) and kebab-case directories. Tailwind utility classes drive styling; avoid inline styles unless unavoidable.

## Testing Guidelines
Pytest with `pytest-asyncio` powers backend tests—decorate coroutines with `@pytest.mark.asyncio` and assert against serialized responses. Target ≥80% coverage and add at least one integration test per major feature using the FastAPI client fixtures. Extend `scripts/test_integration.sh` when wiring new external services, keeping deterministic seeds for Celery-driven flows.

## Commit & Pull Request Guidelines
Write imperative commit subjects ≤72 characters (e.g., `Add task retry policy`), with optional bodies describing motivation. Pull requests should link relevant issues, call out backend versus frontend impact, and list verification steps such as `pytest` and `npm run build`. Attach payload samples or UI screenshots whenever you touch API responses or user interfaces.

## Security & Configuration Tips
Copy `.env.example` to `.env`, inject local credentials, and never commit secrets. Ensure Docker service hostnames match `docker compose` definitions before running workers or tests. Keep uploads, generated logs, and other artifacts out of version control unless explicitly required.
