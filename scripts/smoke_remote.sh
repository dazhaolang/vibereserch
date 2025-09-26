#!/bin/bash

# VibResearch 远程健康探测脚本
# 用于定时检查公网服务的健康状态

set -euo pipefail

# 配置参数
API_BASE_URL="${API_BASE_URL:-http://154.12.50.153:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://154.12.50.153:3000}"
TIMEOUT="${TIMEOUT:-10}"
MAX_RETRIES="${MAX_RETRIES:-3}"
RETRY_DELAY="${RETRY_DELAY:-2}"

# 日志设置
LOG_DIR="${LOG_DIR:-./logs}"
LOG_FILE="${LOG_DIR}/smoke_remote_$(date +%Y%m%d).log"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 日志函数
log() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" | tee -a "$LOG_FILE"
}

log_info() {
    log "INFO" "$@"
}

log_warn() {
    log "WARN" "$@"
}

log_error() {
    log "ERROR" "$@"
}

log_success() {
    log "SUCCESS" "$@"
}

# HTTP 请求函数，带重试机制
http_request() {
    local url="$1"
    local description="$2"
    local expected_status="${3:-200}"

    log_info "Testing $description: $url"

    local attempt=1
    while [ $attempt -le $MAX_RETRIES ]; do
        if [ $attempt -gt 1 ]; then
            log_info "Retry attempt $attempt/$MAX_RETRIES for $description"
            sleep $RETRY_DELAY
        fi

        local response
        local status_code

        # 执行请求并获取状态码
        if response=$(curl -s -w "%{http_code}" --max-time "$TIMEOUT" "$url" 2>/dev/null); then
            status_code="${response: -3}"
            response_body="${response%???}"

            if [ "$status_code" = "$expected_status" ]; then
                log_success "$description: HTTP $status_code ✓"
                return 0
            else
                log_warn "$description: HTTP $status_code (expected $expected_status)"
                if [ $attempt -eq $MAX_RETRIES ]; then
                    log_error "$description: Failed after $MAX_RETRIES attempts"
                    return 1
                fi
            fi
        else
            log_warn "$description: Request failed (timeout or connection error)"
            if [ $attempt -eq $MAX_RETRIES ]; then
                log_error "$description: Failed after $MAX_RETRIES attempts"
                return 1
            fi
        fi

        ((attempt++))
    done
}

# 检查 JSON 响应是否包含期望的字段
check_json_field() {
    local json="$1"
    local field="$2"
    local description="$3"

    if echo "$json" | grep -q "\"$field\""; then
        log_success "$description: Field '$field' found ✓"
        return 0
    else
        log_error "$description: Field '$field' missing ✗"
        return 1
    fi
}

# 详细的 API 健康检查
check_api_health() {
    local url="$API_BASE_URL/health"
    log_info "=== API Health Check ==="

    local response
    if response=$(curl -s --max-time "$TIMEOUT" "$url" 2>/dev/null); then
        local status_code
        status_code=$(curl -s -w "%{http_code}" -o /dev/null --max-time "$TIMEOUT" "$url" 2>/dev/null)

        if [ "$status_code" = "200" ]; then
            log_success "Health endpoint: HTTP 200 ✓"

            # 检查关键字段
            check_json_field "$response" "status" "Health response"
            check_json_field "$response" "version" "Health response"

            # 检查状态值
            if echo "$response" | grep -q '"status":"healthy"'; then
                log_success "Service status: healthy ✓"
            else
                log_error "Service status: not healthy ✗"
                return 1
            fi
        else
            log_error "Health endpoint: HTTP $status_code ✗"
            return 1
        fi
    else
        log_error "Health endpoint: Request failed ✗"
        return 1
    fi
}

# 检查项目列表 API（需要认证的端点示例）
check_project_list() {
    local url="$API_BASE_URL/api/project/list"
    log_info "=== Project List Check ==="

    # 这个端点需要认证，403 是预期的响应（服务正常但需要认证）
    http_request "$url" "Project list endpoint (without auth)" "403"
}

# 检查前端页面
check_frontend() {
    log_info "=== Frontend Check ==="
    http_request "$FRONTEND_URL" "Frontend homepage" "200"
}

# 检查其他关键 API 端点
check_core_apis() {
    log_info "=== Core APIs Check ==="

    # 公开端点
    http_request "$API_BASE_URL/" "Root endpoint" "200"
    http_request "$API_BASE_URL/openapi.json" "OpenAPI spec" "200"
    http_request "$API_BASE_URL/api/docs" "API documentation" "200"

    # 健康检查端点
    http_request "$API_BASE_URL/healthz" "Readiness check" "200"
    http_request "$API_BASE_URL/live" "Liveness check" "200"
    http_request "$API_BASE_URL/status" "Status endpoint" "200"
}

# 生成测试报告
generate_report() {
    local start_time="$1"
    local end_time
    end_time=$(date +%s)
    local duration=$((end_time - start_time))

    log_info "=== Test Summary ==="
    log_info "Test duration: ${duration}s"
    log_info "Log file: $LOG_FILE"

    # 统计成功和失败的数量
    local success_count=0
    local error_count=0

    if [ -f "$LOG_FILE" ]; then
        success_count=$(grep -c "SUCCESS" "$LOG_FILE" 2>/dev/null || echo "0")
        error_count=$(grep -c "ERROR" "$LOG_FILE" 2>/dev/null || echo "0")

        # 确保是数字
        success_count="${success_count//[!0-9]/}"
        error_count="${error_count//[!0-9]/}"

        # 如果为空，设为0
        [ -z "$success_count" ] && success_count=0
        [ -z "$error_count" ] && error_count=0
    fi

    log_info "Successful checks: $success_count"
    log_info "Failed checks: $error_count"

    if [ "$error_count" -eq 0 ]; then
        log_success "All smoke tests passed! 🎉"
        return 0
    else
        log_error "Some smoke tests failed! ❌"
        return 1
    fi
}

# 主函数
main() {
    local start_time
    start_time=$(date +%s)

    log_info "=========================================="
    log_info "VibResearch Remote Smoke Test Started"
    log_info "API Base URL: $API_BASE_URL"
    log_info "Frontend URL: $FRONTEND_URL"
    log_info "Timeout: ${TIMEOUT}s"
    log_info "Max Retries: $MAX_RETRIES"
    log_info "=========================================="

    local overall_result=0

    # 执行各项检查
    if ! check_api_health; then
        overall_result=1
    fi

    if ! check_core_apis; then
        overall_result=1
    fi

    if ! check_project_list; then
        overall_result=1
    fi

    if ! check_frontend; then
        overall_result=1
    fi

    # 生成报告
    if ! generate_report "$start_time"; then
        overall_result=1
    fi

    log_info "=========================================="
    log_info "VibResearch Remote Smoke Test Completed"
    log_info "=========================================="

    exit $overall_result
}

# 脚本入口点
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
