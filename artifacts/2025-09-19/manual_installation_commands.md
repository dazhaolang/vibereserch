# 手动安装外部服务命令

## 当前状态
✅ **后端服务**: 已成功运行在 http://localhost:8000
✅ **API 文档**: 可访问 http://localhost:8000/api/docs
✅ **MCP 服务器**: 已成功集成到 Claude Code
⚠️ **外部服务**: 需要手动安装 (需要 sudo 权限)

## 一键安装命令

请在终端中执行以下命令 (需要 sudo 权限):

```bash
# 进入项目目录
cd /home/wolf/vibereserch

# 执行完整安装脚本
sudo ./scripts/install_external_services.sh
```

## 或者分步骤安装

### 1. 安装 Docker
```bash
# 下载 Docker 安装脚本
curl -fsSL https://get.docker.com -o get-docker.sh

# 安装 Docker
sudo sh get-docker.sh

# 将用户添加到 docker 组
sudo usermod -aG docker $USER

# 重新加载用户组 (或者退出重新登录)
newgrp docker
```

### 2. 启动外部服务
```bash
# 进入项目目录
cd /home/wolf/vibereserch

# 使用 Docker Compose 启动所有服务
docker-compose up -d mysql redis elasticsearch

# 等待服务启动 (约 30 秒)
sleep 30

# 检查服务状态
docker-compose ps
```

### 3. 验证服务连接
```bash
# 测试 MySQL 连接
docker exec vibereserch-mysql-1 mysqladmin ping -h localhost

# 测试 Redis 连接
docker exec vibereserch-redis-1 redis-cli ping

# 测试 Elasticsearch 连接
curl -s http://localhost:9200/_cluster/health | jq '.'
```

### 4. 初始化数据库
```bash
# 运行数据库迁移
cd /home/wolf/vibereserch
python3 -m alembic upgrade head
```

### 5. 重启后端服务以连接数据库
当外部服务启动后，后端将自动连接到数据库和 Redis。你可以查看日志确认连接成功。

## 快速验证

安装完成后，访问以下地址验证系统完整性：

- **后端 API**: http://localhost:8000
- **API 文档**: http://localhost:8000/api/docs
- **健康检查**: http://localhost:8000/health
- **系统状态**: http://localhost:8000/api/system/status

## 故障排除

如果遇到权限问题：
```bash
# 检查 Docker 是否正常安装
docker --version

# 检查用户是否在 docker 组中
groups $USER

# 如果不在，重新执行用户组添加
sudo usermod -aG docker $USER
newgrp docker
```

如果服务启动失败：
```bash
# 查看服务日志
docker-compose logs mysql
docker-compose logs redis
docker-compose logs elasticsearch

# 重启服务
docker-compose restart mysql redis elasticsearch
```