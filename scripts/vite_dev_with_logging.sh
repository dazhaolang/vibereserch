#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FRONTEND_DIR="${SCRIPT_DIR}/../frontend"
LOG_DIR="${FRONTEND_DIR}/test-results"
LOG_FILE="${LOG_DIR}/devserver.log"
PORT="${FRONTEND_TEST_PORT:-3002}"
HOST="${FRONTEND_TEST_HOST:-127.0.0.1}"

mkdir -p "${LOG_DIR}"
: > "${LOG_FILE}"

cd "${FRONTEND_DIR}"

# Run the Vite dev server with logging captured to the Playwright artifact folder.
exec npm run dev -- --host "${HOST}" --port "${PORT}" "$@" | tee -a "${LOG_FILE}"
