#!/bin/bash
# 后端服务恢复脚本
# 用于快速启动所需的外部依赖服务

set -e

echo "🚀 开始恢复后端外部依赖服务..."

# 检查Docker是否可用
if ! command -v docker &> /dev/null; then
    echo "❌ Docker未安装或不可用。请先安装Docker。"
    exit 1
fi

echo "✅ Docker环境检查通过"

# 停止并删除现有容器（如果存在）
echo "🧹 清理现有容器..."
docker rm -f viberes-mysql viberes-redis viberes-elasticsearch 2>/dev/null || true

# 启动MySQL
echo "📀 启动MySQL数据库..."
docker run -d --name viberes-mysql \
  -e MYSQL_ROOT_PASSWORD=viberes_root_123 \
  -e MYSQL_DATABASE=research_platform \
  -e MYSQL_USER=raggar \
  -e MYSQL_PASSWORD=raggar123 \
  -p 3306:3306 \
  mysql:8.0 \
  --default-authentication-plugin=mysql_native_password

# 启动Redis
echo "📡 启动Redis缓存..."
docker run -d --name viberes-redis \
  -p 6379:6379 \
  redis:7-alpine

# 启动Elasticsearch
echo "🔍 启动Elasticsearch搜索引擎..."
docker run -d --name viberes-elasticsearch \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms512m -Xmx512m" \
  -p 9200:9200 \
  -p 9300:9300 \
  elasticsearch:8.10.0

# 等待服务启动
echo "⏳ 等待服务启动完成..."
sleep 30

# 检查服务状态
echo "🔍 检查服务状态..."

# 检查MySQL
if docker exec viberes-mysql mysqladmin ping -h localhost --silent; then
    echo "✅ MySQL服务正常"
else
    echo "❌ MySQL服务异常"
fi

# 检查Redis
if docker exec viberes-redis redis-cli ping | grep -q PONG; then
    echo "✅ Redis服务正常"
else
    echo "❌ Redis服务异常"
fi

# 检查Elasticsearch
if curl -f http://localhost:9200/_cluster/health &>/dev/null; then
    echo "✅ Elasticsearch服务正常"
else
    echo "❌ Elasticsearch服务异常"
fi

echo "🎉 外部依赖服务启动完成！"
echo ""
echo "📋 服务信息："
echo "   - MySQL: localhost:3306 (用户: raggar, 密码: raggar123, 数据库: research_platform)"
echo "   - Redis: localhost:6379"
echo "   - Elasticsearch: localhost:9200"
echo ""
echo "🔧 下一步操作："
echo "   1. 运行数据库迁移: alembic upgrade head"
echo "   2. 启动后端应用: uvicorn app.main:app --reload"
echo "   3. 启动Celery: celery -A app.celery worker --loglevel=info"
echo ""
echo "🛑 停止服务："
echo "   docker rm -f viberes-mysql viberes-redis viberes-elasticsearch"