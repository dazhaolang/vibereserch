#!/usr/bin/env bash
# Full stack test orchestrator for VibResearch.
set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT="${SCRIPT_DIR}/.."
ARTIFACT_ROOT="${REPO_ROOT}/artifacts/system_tests"
RUN_ID=${RUN_ID:-$(date +%Y%m%d_%H%M%S)}
RUN_DIR="${ARTIFACT_ROOT}/${RUN_ID}"
SUMMARY_FILE="${RUN_DIR}/summary.log"
mkdir -p "${RUN_DIR}/backend" "${RUN_DIR}/frontend" "${RUN_DIR}/integration"

YELLOW="\033[1;33m"
GREEN="\033[0;32m"
RED="\033[0;31m"
BLUE="\033[0;34m"
NC="\033[0m"
if [[ ! -t 1 ]]; then
  YELLOW=""
  GREEN=""
  RED=""
  BLUE=""
  NC=""
fi

log_line() {
  echo -e "$1" | tee -a "${SUMMARY_FILE}" >/dev/null
}

log_section() {
  log_line ""
  log_line "${BLUE}=== $1 ===${NC}"
}

STEP_STATUS_ORDER=()
declare -A STEP_STATUS
declare -A STEP_LOG

record_step() {
  local name="$1"
  local status="$2"
  local log_path="$3"
  STEP_STATUS_ORDER+=("$name")
  STEP_STATUS["$name"]="$status"
  STEP_LOG["$name"]="$log_path"
}

run_step() {
  local name="$1"
  local workdir="$2"
  local command="$3"
  local log_path="$4"

  mkdir -p "$(dirname "$log_path")"
  log_line "${YELLOW}→ $name${NC}"
  if (cd "$workdir" && eval "$command") &> >(tee "$log_path"); then
    record_step "$name" "PASS" "$log_path"
    log_line "${GREEN}✓ $name${NC}"
  else
    record_step "$name" "FAIL" "$log_path"
    log_line "${RED}✗ $name${NC}"
  fi
}

find_python() {
  if [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
    echo "${REPO_ROOT}/venv/bin/python"
    return
  fi
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
    return
  fi
  if command -v python >/dev/null 2>&1; then
    command -v python
    return
  fi
  echo ""  # not found
}

PYTHON_BIN=$(find_python)
if [[ -z "${PYTHON_BIN}" ]]; then
  log_line "${RED}未找到可用的 Python 解释器，请先准备虚拟环境。${NC}"
  exit 1
fi

NPM_BIN=$(command -v npm || true)
NPX_BIN=$(command -v npx || true)
CURL_BIN=$(command -v curl || true)

BACKEND_PID=""
cleanup() {
  if [[ -n "${BACKEND_PID}" ]]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

wait_for_http() {
  local url="$1"
  local retries="${2:-30}"
  local delay="${3:-2}"
  local attempt=1
  while (( attempt <= retries )); do
    if [[ -n "${CURL_BIN}" ]] && "${CURL_BIN}" -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
    attempt=$((attempt + 1))
  done
  return 1
}

log_section "环境信息"
log_line "Python: ${PYTHON_BIN}"
log_line "Node: ${NPM_BIN:-missing}"
log_line "curl: ${CURL_BIN:-missing}"
log_line "Artifacts: ${RUN_DIR}"

run_step "Backend unit tests" "${REPO_ROOT}" "\"${PYTHON_BIN}\" -m pytest --disable-warnings" "${RUN_DIR}/backend/pytest.log"

start_backend() {
  local log_file="${RUN_DIR}/backend/backend_server.log"
  if [[ -n "${BACKEND_PID}" ]]; then
    return
  fi
  log_line "${YELLOW}→ 启动后端服务 (uvicorn)${NC}"
  (cd "${REPO_ROOT}" && "${PYTHON_BIN}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --log-level info) &>"${log_file}" &
  BACKEND_PID=$!
  if wait_for_http "http://127.0.0.1:8000/health" 40 2; then
    log_line "${GREEN}✓ 后端健康检查通过${NC}"
    record_step "Backend server" "PASS" "${log_file}"
  else
    log_line "${RED}✗ 后端健康检查失败，请检查 ${log_file}${NC}"
    record_step "Backend server" "FAIL" "${log_file}"
  fi
}

start_backend

run_step "API regression suite" "${REPO_ROOT}" "\"${PYTHON_BIN}\" ${REPO_ROOT}/scripts/api_regression_suite.py --base-url http://127.0.0.1:8000 --timeout 25 --output \"${RUN_DIR}/integration/api_regression.json\"" "${RUN_DIR}/integration/api_regression.log"

collect_frontend_artifacts() {
  local src_dir="${REPO_ROOT}/frontend/test-results"
  if [[ -d "${src_dir}" ]]; then
    find "${src_dir}" -maxdepth 1 -type f -print0 | while IFS= read -r -d '' file; do
      cp "$file" "${RUN_DIR}/frontend/$(basename "$file")"
    done
  fi
  local report_dir="${REPO_ROOT}/frontend/playwright-report"
  if [[ -d "${report_dir}" ]]; then
    cp -R "${report_dir}" "${RUN_DIR}/frontend/playwright-report"
  fi
}

if [[ -n "${NPM_BIN}" ]]; then
  run_step "Frontend lint" "${REPO_ROOT}/frontend" "\"${NPM_BIN}\" run lint" "${RUN_DIR}/frontend/lint.log"
  run_step "Frontend build" "${REPO_ROOT}/frontend" "\"${NPM_BIN}\" run build" "${RUN_DIR}/frontend/build.log"
else
  log_line "${RED}✗ 未找到 npm，跳过前端构建测试${NC}"
  record_step "Frontend lint" "SKIP" ""
  record_step "Frontend build" "SKIP" ""
fi

if [[ -n "${NPX_BIN}" ]]; then
  PLAYWRIGHT_ENV="CI=1 FRONTEND_BASE_URL=http://127.0.0.1:3002 BACKEND_BASE_URL=http://127.0.0.1:8000 PLAYWRIGHT_WAIT_FOR_API_MS=25000 PLAYWRIGHT_WAIT_FOR_UI_MS=20000"
  run_step "Playwright end-to-end" "${REPO_ROOT}/frontend" "${PLAYWRIGHT_ENV} \"${NPX_BIN}\" playwright test --reporter=list" "${RUN_DIR}/frontend/playwright.log"
  collect_frontend_artifacts
else
  log_line "${RED}✗ 未找到 npx，跳过 Playwright 测试${NC}"
  record_step "Playwright end-to-end" "SKIP" ""
fi

log_section "步骤结果"
exit_code=0
for step in "${STEP_STATUS_ORDER[@]}"; do
  status="${STEP_STATUS[$step]}"
  log_path="${STEP_LOG[$step]}"
  case "$status" in
    PASS)
      log_line "${GREEN}${step}: PASS${NC}"
      ;;
    FAIL)
      log_line "${RED}${step}: FAIL${NC} -> ${log_path}"
      exit_code=1
      ;;
    SKIP)
      log_line "${YELLOW}${step}: SKIP${NC}"
      ;;
    *)
      log_line "${YELLOW}${step}: ${status}${NC}"
      ;;
  esac
done

log_line ""
if [[ ${exit_code} -eq 0 ]]; then
  log_line "${GREEN}✅ 测试全部通过，详细日志见 ${RUN_DIR}${NC}"
else
  log_line "${RED}❌ 存在失败项，请检索对应日志进一步分析。${NC}"
fi

exit "${exit_code}"