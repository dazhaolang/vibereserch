#!/bin/sh
set -e

if [ "$1" = "celery" ]; then
  shift
  echo "Starting Celery worker..."
  exec celery "$@"
fi

if [ "$1" = "bash" ] || [ "$1" = "sh" ]; then
  exec "$@"
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Applying database migrations..."
  alembic upgrade head
else
  echo "Skipping database migrations (RUN_MIGRATIONS=${RUN_MIGRATIONS})."
fi

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
