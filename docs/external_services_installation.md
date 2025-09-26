# 外部服务安装指南

由于当前环境没有 sudo 权限和 Docker，需要手动安装外部服务。以下是完整的安装指南：

## 当前系统状态

### ✅ 已正常运行的服务
- **FastAPI 后端**: http://localhost:8000 ✅
- **API 文档**: http://localhost:8000/api/docs ✅
- **MCP 服务器**: 已注册到 Claude Code ✅
- **Celery Worker**: 已启动但无法连接 Redis ⚠️

### ⚠️ 需要安装的外部服务
- **MySQL** (数据库): 未安装
- **Redis** (缓存和消息队列): 未安装
- **Elasticsearch** (搜索引擎): 未安装

## 安装方案选择

### 方案 1: Docker Compose (推荐)

如果有 sudo 权限，使用 Docker Compose 是最简单的方案：

```bash
# 1. 安装 Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 2. 安装 Docker Compose (现代版本已集成)
sudo usermod -aG docker $USER
newgrp docker

# 3. 启动外部服务
cd /home/wolf/vibereserch
docker compose up -d mysql redis elasticsearch

# 4. 验证服务状态
docker compose ps
```

### 方案 2: 本地安装

如果无法使用 Docker，可以本地安装服务：

#### 安装 MySQL
```bash
sudo apt update
sudo apt install mysql-server
sudo mysql_secure_installation

# 创建数据库和用户
sudo mysql -u root -p
```

```sql
CREATE DATABASE research_platform;
CREATE USER 'raggar'@'localhost' IDENTIFIED BY 'raggar123';
GRANT ALL PRIVILEGES ON research_platform.* TO 'raggar'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

#### 安装 Redis
```bash
sudo apt install redis-server
sudo systemctl start redis-server
sudo systemctl enable redis-server

# 测试 Redis
redis-cli ping
```

#### 安装 Elasticsearch
```bash
# 安装 Java (Elasticsearch 依赖)
sudo apt install openjdk-11-jdk

# 下载和安装 Elasticsearch
wget https://artifacts.elastic.co/downloads/elasticsearch/elasticsearch-8.10.0-linux-x86_64.tar.gz
tar -xzf elasticsearch-8.10.0-linux-x86_64.tar.gz
cd elasticsearch-8.10.0

# 配置 Elasticsearch
echo "xpack.security.enabled: false" >> config/elasticsearch.yml
echo "discovery.type: single-node" >> config/elasticsearch.yml

# 启动 Elasticsearch
./bin/elasticsearch
```

### 方案 3: 云服务

使用云服务提供商的托管服务：

#### MySQL
- **AWS RDS**
- **Google Cloud SQL**
- **Azure Database for MySQL**
- **PlanetScale** (免费层)

#### Redis
- **Redis Cloud**
- **AWS ElastiCache**
- **Upstash** (免费层)

#### Elasticsearch
- **Elastic Cloud**
- **AWS Elasticsearch Service**
- **Bonsai** (免费层)

## 快速启动命令 (需要 sudo 权限)

如果您有 sudo 权限，可以使用以下一键安装脚本：

```bash
#!/bin/bash
# 一键安装所有外部服务

# 安装 Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER

# 启动服务
cd /home/wolf/vibereserch
sudo docker compose up -d mysql redis elasticsearch

# 等待服务启动
sleep 30

# 检查服务状态
echo "=== 服务状态检查 ==="
sudo docker compose ps

# 测试连接
echo "=== 连接测试 ==="
mysql -h localhost -u raggar -praggar123 -e "SELECT 1;"
redis-cli ping
curl http://localhost:9200
```

## 环境变量配置

确保 `.env` 文件包含正确的连接信息：

```env
# 数据库配置
DATABASE_URL=mysql://raggar:raggar123@localhost:3306/research_platform

# Redis 配置
REDIS_URL=redis://localhost:6379

# Elasticsearch 配置
ELASTICSEARCH_URL=http://localhost:9200
```

## 服务端口说明

- **MySQL**: 3306
- **Redis**: 6379
- **Elasticsearch**: 9200, 9300
- **Kibana** (可选): 5601
- **Backend API**: 8000

## 数据库初始化

安装服务后，需要初始化数据库结构：

```bash
# 安装 Alembic (如果还没安装)
pip install alembic

# 运行数据库迁移
cd /home/wolf/vibereserch
alembic upgrade head
```

## 验证安装

安装完成后，可以使用以下命令验证服务：

```bash
# 测试 MySQL 连接
mysql -h localhost -u raggar -praggar123 research_platform -e "SHOW TABLES;"

# 测试 Redis 连接
redis-cli ping

# 测试 Elasticsearch 连接
curl -X GET "http://localhost:9200/_cluster/health?pretty"

# 测试后端 API 健康检查
curl -X GET "http://localhost:8000/health"
```

## 当前可用功能 (无外部服务)

即使没有外部服务，以下功能仍然可用：

### ✅ 完全可用
- API 文档和接口定义
- 健康检查端点
- MCP 工具集成
- Claude Code 集成
- 性能监控 (内存模式)
- 多模型协调器

### ⚠️ 部分可用
- 用户认证 (JWT 生成，但无法持久化)
- 配置管理
- 静态文件服务

### ❌ 需要外部服务
- 数据持久化 (需要 MySQL)
- 缓存功能 (需要 Redis)
- 搜索功能 (需要 Elasticsearch)
- 后台任务处理 (需要 Redis)

## 建议的安装顺序

1. **Redis** (最重要，影响缓存和 Celery)
2. **MySQL** (数据持久化)
3. **Elasticsearch** (搜索功能)

## 故障排除

### MySQL 连接问题
```bash
# 检查 MySQL 状态
sudo systemctl status mysql

# 重启 MySQL
sudo systemctl restart mysql

# 检查端口
netstat -tulnp | grep 3306
```

### Redis 连接问题
```bash
# 检查 Redis 状态
sudo systemctl status redis-server

# 测试连接
redis-cli ping

# 检查配置
cat /etc/redis/redis.conf | grep bind
```

### Elasticsearch 连接问题
```bash
# 检查 Elasticsearch 进程
ps aux | grep elasticsearch

# 检查日志
tail -f elasticsearch-8.10.0/logs/elasticsearch.log

# 检查端口
netstat -tulnp | grep 9200
```

## 总结

虽然当前环境限制了我们直接安装这些服务，但我们已经成功启动了核心后端服务。用户可以根据自己的权限和环境选择合适的安装方案。

**推荐顺序**: Docker Compose > 本地安装 > 云服务