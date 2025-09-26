#!/bin/bash
# 修复版外部服务安装脚本
# 解决 Docker 权限和 Elasticsearch 镜像版本问题

set -e

echo "🔧 修复 Docker 权限问题..."

# 添加用户到 docker 组
sudo usermod -aG docker $USER

# 重新加载用户组
newgrp docker << 'EOF'

echo "✅ Docker 权限修复完成"

# 检查 Docker 状态
echo "📋 检查 Docker 服务状态..."
sudo systemctl start docker
sudo systemctl enable docker

echo "🔍 验证 Docker 安装..."
docker --version

# 创建必要的目录
echo "📁 创建数据目录..."
mkdir -p ~/viberes-data/mysql
mkdir -p ~/viberes-data/elasticsearch
mkdir -p ~/viberes-data/redis

# 启动 MySQL
echo "📀 启动 MySQL 数据库..."
docker run -d --name viberes-mysql \
  --restart unless-stopped \
  -e MYSQL_ROOT_PASSWORD=viberes_root_123 \
  -e MYSQL_DATABASE=research_platform \
  -e MYSQL_USER=raggar \
  -e MYSQL_PASSWORD=raggar123 \
  -p 3306:3306 \
  -v ~/viberes-data/mysql:/var/lib/mysql \
  mysql:8.0 \
  --default-authentication-plugin=mysql_native_password \
  --character-set-server=utf8mb4 \
  --collation-server=utf8mb4_unicode_ci

# 启动 Redis
echo "📡 启动 Redis 缓存..."
docker run -d --name viberes-redis \
  --restart unless-stopped \
  -p 6379:6379 \
  -v ~/viberes-data/redis:/data \
  redis:7-alpine \
  redis-server --appendonly yes

# 启动 Elasticsearch (使用正确的版本)
echo "🔍 启动 Elasticsearch 搜索引擎..."
docker run -d --name viberes-elasticsearch \
  --restart unless-stopped \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  -p 9200:9200 \
  -p 9300:9300 \
  -v ~/viberes-data/elasticsearch:/usr/share/elasticsearch/data \
  elasticsearch:8.11.0

# 等待服务启动
echo "⏳ 等待服务启动完成..."
echo "正在启动 MySQL..."
sleep 20

echo "等待 MySQL 完全启动..."
while ! docker exec viberes-mysql mysqladmin ping -h localhost --silent 2>/dev/null; do
    echo "MySQL 正在启动中..."
    sleep 5
done

echo "等待 Redis 启动..."
sleep 10

echo "等待 Elasticsearch 启动..."
sleep 30

# 验证服务状态
echo "🔍 验证服务状态..."

# 检查容器状态
echo "=== Docker 容器状态 ==="
docker ps --filter "name=viberes-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# 检查 MySQL
echo ""
echo "=== MySQL 连接测试 ==="
if docker exec viberes-mysql mysqladmin ping -h localhost --silent; then
    echo "✅ MySQL 服务正常"
    # 验证数据库和用户
    docker exec viberes-mysql mysql -u raggar -praggar123 -e "SELECT 'MySQL connection successful' as status;"
else
    echo "❌ MySQL 服务异常"
fi

# 检查 Redis
echo ""
echo "=== Redis 连接测试 ==="
if docker exec viberes-redis redis-cli ping | grep -q PONG; then
    echo "✅ Redis 服务正常"
    docker exec viberes-redis redis-cli info server | grep redis_version
else
    echo "❌ Redis 服务异常"
fi

# 检查 Elasticsearch
echo ""
echo "=== Elasticsearch 连接测试 ==="
sleep 10  # 给 ES 更多启动时间
if curl -s -f http://localhost:9200/_cluster/health &>/dev/null; then
    echo "✅ Elasticsearch 服务正常"
    curl -s http://localhost:9200 | grep '"version" : {' -A 3
else
    echo "⚠️ Elasticsearch 可能仍在启动中..."
    echo "请稍等片刻后运行: curl http://localhost:9200"
fi

echo ""
echo "🎉 外部服务安装完成！"
echo ""
echo "📋 服务信息："
echo "   - MySQL:        localhost:3306"
echo "     用户名: raggar"
echo "     密码: raggar123"
echo "     数据库: research_platform"
echo ""
echo "   - Redis:        localhost:6379"
echo "   - Elasticsearch: localhost:9200"
echo ""
echo "📊 数据持久化:"
echo "   - MySQL 数据:     ~/viberes-data/mysql"
echo "   - Redis 数据:     ~/viberes-data/redis"
echo "   - Elasticsearch:  ~/viberes-data/elasticsearch"
echo ""
echo "🔧 下一步操作："
echo "   1. 运行数据库迁移: cd /home/wolf/vibereserch && alembic upgrade head"
echo "   2. 后端应用将自动连接到数据库"
echo "   3. Celery 将自动连接到 Redis"
echo ""
echo "🛑 停止服务："
echo "   docker stop viberes-mysql viberes-redis viberes-elasticsearch"
echo "   docker rm viberes-mysql viberes-redis viberes-elasticsearch"
echo ""
echo "🔄 重启服务："
echo "   docker start viberes-mysql viberes-redis viberes-elasticsearch"

EOF