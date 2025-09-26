# 后端外部依赖恢复方案

根据 `backend_test_report.md` 的测试结论，当前后端基础路由和监控功能已恢复正常，但仍有四项关键外部依赖缺失，导致数据持久化、异步任务、搜索与 MCP 集成无法使用。下面给出逐项恢复方案以及验证步骤。

## 1. MySQL 数据库服务

- **问题现象**：`(pymysql.err.OperationalError) (2003, "Can't connect to MySQL server on 'localhost' ...)`，所有与数据库相关的 API（用户、项目、文献持久化）不可用。
- **启动方式（推荐 Docker）**：

  ```bash
  docker run -d --name viberes-mysql \
    -e MYSQL_ROOT_PASSWORD=your_root_pwd \
    -e MYSQL_DATABASE=viberes \
    -p 3306:3306 \
    mysql:8
  ```

- **应用配置**：将 `.env` 中的数据库配置指向容器，示例：

  ```env
  DATABASE_URL=mysql+pymysql://root:your_root_pwd@127.0.0.1:3306/viberes
  ```

- **初始化数据结构**：

  ```bash
  poetry run alembic upgrade head  # 或 venv/bin/alembic
  python scripts/init_seed_data.py  # 如需初始化示例数据
  ```

## 2. Redis 消息队列/缓存服务

- **问题现象**：`Error 101 connecting to localhost:6379. Network is unreachable`，Celery 任务、缓存、实时进度推送无法工作。
- **启动方式**：

  ```bash
  docker run -d --name viberes-redis -p 6379:6379 redis:7
  ```

- **应用配置**：

  ```env
  REDIS_URL=redis://127.0.0.1:6379/0
  CELERY_BROKER_URL=${REDIS_URL}
  CELERY_RESULT_BACKEND=${REDIS_URL}
  ```

- **验证 Celery**：

  ```bash
  poetry run celery -A app.celery worker --loglevel=info
  ```

  观察「Connected to redis://...」日志确认连接成功。

## 3. Elasticsearch 检索服务

- **问题现象**：`ClientConnectorError(Cannot connect to host localhost:9200 ...)`，文献搜索和语义检索功能不可用。
- **启动方式**：

  ```bash
  docker run -d --name viberes-es \
    -e "discovery.type=single-node" \
    -e "xpack.security.enabled=false" \
    -p 9200:9200 \
    elasticsearch:8
  ```

- **应用配置**：

  ```env
  ELASTICSEARCH_URL=http://127.0.0.1:9200
  ```

- **索引初始化（如项目已有脚本）**：

  ```bash
  python scripts/init_elasticsearch_indices.py
  ```

## 4. MCP 服务（Claude Code 集成）

- **问题现象**：缺少 `app/mcp_server.py`，智能编排无法工作。
- **建议方案**：
  1. 若已有独立的 MCP 服务仓库，请将实现复制/挂载到 `app/`，并在 `app/services/mcp_tool_setup.py` 中调整导入路径。
  2. 如果尚未开发，可先提供一个最小可用的 stub，实现基础的工具注册与响应，保障接口返回 200，后续再接入真实逻辑。
  3. 配置 `.env` 新增 `MCP_SERVER_URL` 指向该服务，后端启动时调用 `setup_mcp_tools()` 即可完成注册。

## 5. 验证流程

1. **服务就绪检查**：
   ```bash
   docker ps | grep -E 'viberes-(mysql|redis|es)'
   ```

2. **后端启动**：
   ```bash
   uvicorn app.main:app --reload
   ```

3. **快速验证 API**：
   - `GET /health` 应返回 `status: healthy`
   - `POST /api/auth/register` 能创建用户（需 MySQL）
   - `POST /api/literature/search` 返回数据（需 ES）
   - 提交异步任务后在 Celery worker 日志中看到执行（需 Redis）

4. **自动化测试**：服务全部就绪后，执行 `pytest` 或报告中提到的测试脚本，确保回归通过。

## 6. 额外建议

- 将上述容器写入 `docker-compose.yml`，统一启停：

  ```yaml
  services:
    mysql:
      image: mysql:8
      environment:
        MYSQL_ROOT_PASSWORD: your_root_pwd
        MYSQL_DATABASE: viberes
      ports:
        - "3306:3306"

    redis:
      image: redis:7
      ports:
        - "6379:6379"

    elasticsearch:
      image: elasticsearch:8
      environment:
        discovery.type: single-node
        xpack.security.enabled: "false"
      ports:
        - "9200:9200"
  ```

- 在应用启动时增加外部服务健康检查，提前给出友好错误信息，便于排查。

---

按照以上步骤即可恢复数据库、消息队列、搜索与 MCP 相关能力，为后续端到端功能测试提供稳定基础。
