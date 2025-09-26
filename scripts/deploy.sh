#!/bin/bash

# VibResearch Platform 部署脚本
# 用于生产环境的一键部署和服务管理

set -e  # 出错时退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 环境变量检查
check_environment() {
    log_info "检查环境变量配置..."

    required_vars=(
        "DATABASE_URL"
        "REDIS_URL"
        "JWT_SECRET_KEY"
        "ENCRYPTION_KEY"
    )

    missing_vars=()
    for var in "${required_vars[@]}"; do
        if [ -z "${!var}" ]; then
            missing_vars+=("$var")
        fi
    done

    if [ ${#missing_vars[@]} -ne 0 ]; then
        log_error "缺少必要的环境变量:"
        for var in "${missing_vars[@]}"; do
            echo "  - $var"
        done
        exit 1
    fi

    log_success "环境变量检查通过"
}

# 依赖检查
check_dependencies() {
    log_info "检查系统依赖..."

    # 检查Python版本
    if ! command -v python3.12 &> /dev/null; then
        log_error "Python 3.12 未安装"
        exit 1
    fi

    # 检查Docker
    if ! command -v docker &> /dev/null; then
        log_warning "Docker 未安装，将无法使用容器化部署"
    fi

    # 检查MySQL客户端
    if ! command -v mysql &> /dev/null; then
        log_warning "MySQL客户端未安装"
    fi

    log_success "系统依赖检查完成"
}

# 数据库迁移
run_migrations() {
    log_info "执行数据库迁移..."

    # 检查数据库连接
    if ! python3 -c "
from app.core.database import SessionLocal
try:
    with SessionLocal() as session:
        session.execute('SELECT 1')
    print('数据库连接正常')
except Exception as e:
    print(f'数据库连接失败: {e}')
    exit(1)
" 2>/dev/null; then
        log_error "数据库连接失败"
        exit 1
    fi

    # 运行迁移
    alembic upgrade head

    log_success "数据库迁移完成"
}

# 健康检查
health_check() {
    log_info "执行健康检查..."

    local max_attempts=30
    local attempt=0

    while [ $attempt -lt $max_attempts ]; do
        if curl -s -f http://localhost:8000/readyz > /dev/null; then
            log_success "健康检查通过"
            return 0
        fi

        attempt=$((attempt + 1))
        log_warning "健康检查失败，重试 $attempt/$max_attempts"
        sleep 2
    done

    log_error "健康检查失败，服务可能未正常启动"
    return 1
}

# 启动Celery Worker
start_celery() {
    log_info "启动Celery Worker..."

    # 检查是否已有Celery进程
    if pgrep -f "celery.*worker" > /dev/null; then
        log_warning "Celery Worker已在运行，正在重启..."
        pkill -f "celery.*worker" || true
        sleep 2
    fi

    # 启动Celery Worker
    nohup celery -A app.celery worker --loglevel=info --concurrency=4 > logs/celery.log 2>&1 &

    # 启动Celery Beat (定时任务)
    nohup celery -A app.celery beat --loglevel=info > logs/celery_beat.log 2>&1 &

    log_success "Celery服务启动完成"
}

# 启动Web服务
start_web() {
    log_info "启动Web服务..."

    # 创建日志目录
    mkdir -p logs

    # 启动Uvicorn服务器
    if [ "$ENVIRONMENT" = "production" ]; then
        # 生产环境配置
        nohup uvicorn app.main:app \
            --host 0.0.0.0 \
            --port 8000 \
            --workers 4 \
            --loop uvloop \
            --access-log \
            --log-level info > logs/uvicorn.log 2>&1 &
    else
        # 开发环境配置
        nohup uvicorn app.main:app \
            --host 0.0.0.0 \
            --port 8000 \
            --reload \
            --log-level debug > logs/uvicorn.log 2>&1 &
    fi

    local server_pid=$!
    echo $server_pid > .server.pid

    log_success "Web服务启动完成 (PID: $server_pid)"
}

# 停止服务
stop_services() {
    log_info "停止所有服务..."

    # 停止Web服务
    if [ -f .server.pid ]; then
        local pid=$(cat .server.pid)
        if kill -0 $pid 2>/dev/null; then
            kill $pid
            log_success "Web服务已停止"
        fi
        rm -f .server.pid
    fi

    # 停止Celery服务
    pkill -f "celery.*worker" || true
    pkill -f "celery.*beat" || true
    log_success "Celery服务已停止"
}

# 部署流程
deploy() {
    log_info "开始部署 VibResearch Platform..."

    # 检查环境
    check_environment
    check_dependencies

    # 安装Python依赖
    log_info "安装Python依赖..."
    pip install -r requirements.txt

    # 数据库迁移
    run_migrations

    # 停止旧服务
    stop_services

    # 启动服务
    start_celery
    start_web

    # 等待服务启动
    sleep 5

    # 健康检查
    if health_check; then
        log_success "🎉 部署成功！VibResearch Platform已启动"
        log_info "服务地址: http://localhost:8000"
        log_info "API文档: http://localhost:8000/docs"
        log_info "健康检查: http://localhost:8000/readyz"
    else
        log_error "❌ 部署失败，请检查日志文件"
        exit 1
    fi
}

# 状态检查
status() {
    log_info "检查服务状态..."

    # 检查Web服务
    if [ -f .server.pid ] && kill -0 $(cat .server.pid) 2>/dev/null; then
        log_success "Web服务运行中 (PID: $(cat .server.pid))"
    else
        log_warning "Web服务未运行"
    fi

    # 检查Celery服务
    if pgrep -f "celery.*worker" > /dev/null; then
        log_success "Celery Worker运行中"
    else
        log_warning "Celery Worker未运行"
    fi

    if pgrep -f "celery.*beat" > /dev/null; then
        log_success "Celery Beat运行中"
    else
        log_warning "Celery Beat未运行"
    fi

    # 健康检查
    if curl -s -f http://localhost:8000/readyz > /dev/null; then
        log_success "健康检查通过"
    else
        log_warning "健康检查失败"
    fi
}

# 重启服务
restart() {
    log_info "重启服务..."
    stop_services
    sleep 2
    start_celery
    start_web
    sleep 5
    if health_check; then
        log_success "服务重启成功"
    else
        log_error "服务重启失败"
        exit 1
    fi
}

# 查看日志
logs() {
    local service=${1:-"all"}

    case $service in
        "web"|"uvicorn")
            tail -f logs/uvicorn.log
            ;;
        "celery")
            tail -f logs/celery.log
            ;;
        "beat")
            tail -f logs/celery_beat.log
            ;;
        "all")
            tail -f logs/*.log
            ;;
        *)
            log_error "未知的日志类型: $service"
            log_info "可用选项: web, celery, beat, all"
            exit 1
            ;;
    esac
}

# 使用说明
usage() {
    echo "VibResearch Platform 部署脚本"
    echo ""
    echo "用法: $0 {deploy|start|stop|restart|status|logs|health}"
    echo ""
    echo "命令:"
    echo "  deploy    - 完整部署流程"
    echo "  start     - 启动所有服务"
    echo "  stop      - 停止所有服务"
    echo "  restart   - 重启所有服务"
    echo "  status    - 检查服务状态"
    echo "  logs      - 查看日志 (logs [web|celery|beat|all])"
    echo "  health    - 执行健康检查"
    echo ""
    echo "环境变量:"
    echo "  ENVIRONMENT - 运行环境 (production|development)"
    echo "  DATABASE_URL - 数据库连接URL"
    echo "  REDIS_URL - Redis连接URL"
    echo "  JWT_SECRET_KEY - JWT密钥"
    echo "  ENCRYPTION_KEY - 加密密钥"
}

# 主命令处理
case "${1:-}" in
    "deploy")
        deploy
        ;;
    "start")
        start_celery
        start_web
        sleep 5
        health_check
        ;;
    "stop")
        stop_services
        ;;
    "restart")
        restart
        ;;
    "status")
        status
        ;;
    "logs")
        logs "${2:-all}"
        ;;
    "health")
        health_check
        ;;
    *)
        usage
        exit 1
        ;;
esac