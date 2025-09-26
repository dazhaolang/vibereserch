#!/bin/bash
# Utility script to restart API (port 8000) and frontend (port 3000) dev servers.

set -euo pipefail

REPO_ROOT="/home/wolf/vibereserch"
BACKEND_PORT=8000
FRONTEND_PORT=3000
BACKEND_CMD=("${REPO_ROOT}/venv/bin/python" "-m" "uvicorn" "app.main:app" "--reload" "--host" "0.0.0.0" "--port" "${BACKEND_PORT}")
FRONTEND_CMD=("npm" "--prefix" "${REPO_ROOT}/frontend" "run" "dev" "--" "--host" "0.0.0.0" "--port" "${FRONTEND_PORT}")
LOG_DIR="${REPO_ROOT}/logs"
BACKEND_LOG="${LOG_DIR}/backend_dev.log"
FRONTEND_LOG="${LOG_DIR}/frontend_dev.log"

kill_port() {
    local port=$1
    if ! command -v lsof >/dev/null 2>&1; then
        echo "lsof not found; aborting clean-up." >&2
        exit 1
    fi

    local pids
    if pids=$(lsof -ti tcp:"${port}" 2>/dev/null); then
        echo "Killing processes on port ${port}: ${pids}" >&2
        kill ${pids} 2>/dev/null || true
        sleep 1
        if pids=$(lsof -ti tcp:"${port}" 2>/dev/null); then
            echo "Force killing processes on port ${port}: ${pids}" >&2
            kill -9 ${pids} 2>/dev/null || true
        fi
    else
        echo "No existing process on port ${port}." >&2
    fi
}

ensure_env() {
    if [ ! -x "${REPO_ROOT}/venv/bin/python" ]; then
        echo "Python venv not found at ${REPO_ROOT}/venv. Please create it before running this script." >&2
        exit 1
    fi
    if [ ! -d "${REPO_ROOT}/frontend/node_modules" ]; then
        echo "Frontend dependencies missing. Run 'npm install --prefix ${REPO_ROOT}/frontend'." >&2
        exit 1
    fi
}

start_backend() {
    echo "Starting backend: ${BACKEND_CMD[*]}" >&2
    (cd "${REPO_ROOT}" && "${BACKEND_CMD[@]}") >>"${BACKEND_LOG}" 2>&1 &
    BACKEND_PID=$!
    echo "Backend PID: ${BACKEND_PID}" >&2
}

start_frontend() {
    echo "Starting frontend: ${FRONTEND_CMD[*]}" >&2
    (cd "${REPO_ROOT}" && "${FRONTEND_CMD[@]}") >>"${FRONTEND_LOG}" 2>&1 &
    FRONTEND_PID=$!
    echo "Frontend PID: ${FRONTEND_PID}" >&2
}

main() {
    mkdir -p "${LOG_DIR}"
    : >"${BACKEND_LOG}"
    : >"${FRONTEND_LOG}"

    ensure_env

    kill_port "${BACKEND_PORT}"
    kill_port "${FRONTEND_PORT}"

    start_backend
    start_frontend

    trap 'echo "Stopping dev servers..." >&2; kill ${BACKEND_PID:-} ${FRONTEND_PID:-} 2>/dev/null || true' EXIT

    echo "Backend log: ${BACKEND_LOG}" >&2
    echo "Frontend log: ${FRONTEND_LOG}" >&2
    echo "Press Ctrl+C to stop both servers." >&2

    wait
}

main "$@"
