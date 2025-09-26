# Docker 权限和服务启动快速修复指南

## 问题分析
1. **Docker 权限问题**: 用户不在 docker 组中
2. **Elasticsearch 镜像版本错误**: 8.10.0 不存在，应该使用 8.11.0

## 快速修复步骤

### 1. 修复 Docker 权限
```bash
# 添加用户到 docker 组
sudo usermod -aG docker $USER

# 重新登录或使用 newgrp 加载新组权限
newgrp docker

# 验证权限
docker ps
```

### 2. 启动服务 (使用正确的镜像版本)
```bash
cd /home/wolf/vibereserch

# 启动 MySQL
docker run -d --name viberes-mysql \
  --restart unless-stopped \
  -e MYSQL_ROOT_PASSWORD=viberes_root_123 \
  -e MYSQL_DATABASE=research_platform \
  -e MYSQL_USER=raggar \
  -e MYSQL_PASSWORD=raggar123 \
  -p 3306:3306 \
  mysql:8.0

# 启动 Redis
docker run -d --name viberes-redis \
  --restart unless-stopped \
  -p 6379:6379 \
  redis:7-alpine

# 启动 Elasticsearch (修正版本)
docker run -d --name viberes-elasticsearch \
  --restart unless-stopped \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  -e "ES_JAVA_OPTS=-Xms1g -Xmx1g" \
  -p 9200:9200 \
  -p 9300:9300 \
  elasticsearch:8.11.0
```

### 3. 验证服务状态
```bash
# 检查容器状态
docker ps

# 测试连接
sleep 30  # 等待服务启动
curl http://localhost:9200
docker exec viberes-mysql mysqladmin ping
docker exec viberes-redis redis-cli ping
```

### 4. 运行数据库迁移
```bash
cd /home/wolf/vibereserch
python3 -m alembic upgrade head
```

## 一键执行脚本
```bash
chmod +x scripts/install_fixed_services.sh
sudo ./scripts/install_fixed_services.sh
```

## 如果仍有问题
1. 重启 Docker 服务: `sudo systemctl restart docker`
2. 清理旧容器: `docker rm -f viberes-mysql viberes-redis viberes-elasticsearch`
3. 重新执行启动命令