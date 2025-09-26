# 科研文献智能分析平台

## 项目概述

该仓库包含科研文献智能分析平台的 **FastAPI 后端** 与 **React 前端**，提供文献采集、AI 分析、任务编排、实时进度、知识图谱等功能。系统依赖 MySQL、Redis、Elasticsearch 以及 Celery，并提供一键启动的 Docker Compose 环境。

## 技术栈

- 后端：FastAPI · SQLAlchemy · Celery · Redis · Elasticsearch
- 前端：React 18 · Vite · Ant Design Pro · TailwindCSS · Zustand
- 数据库：MySQL 8
- 消息与搜索：Redis 7 · Elasticsearch 8
- 部署：Docker Compose（推荐）

## 快速开始（Docker Compose）

1. 准备环境变量
   ```bash
   cp .env.example .env
   # 根据需要填写 OpenAI、数据库等配置，至少保证 JWT_SECRET_KEY 已修改
   # 如需区分环境，可设置 APP_ENV=development|staging|production
   ```

2. 启动所有服务（首次运行会自动构建镜像并初始化数据库迁移）
   ```bash
   docker compose up -d --build
   ```

3. 验证服务
   ```bash
   # 查看容器状态
   docker compose ps

   # 查看后端健康检查
   curl http://localhost:8000/healthz

   # 查看前端页面（浏览器访问）
   http://localhost:3000
   ```

4. 常用命令
   ```bash
   # 查看日志
   docker compose logs -f backend
   docker compose logs -f celery

   # 关闭服务
   docker compose down

   # 清理数据卷（会删除数据库/索引/上传文件）
   docker compose down -v
   ```

> 注意：当前环境未启用 Docker 权限检查，如 `docker compose build` 出现 `permission denied`，请确保当前用户具备 Docker 运行权限再执行。

## 本地开发

### 后端
1. 创建虚拟环境并安装依赖
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. 选择运行模式：
   - **轻量模式（无需 MySQL/Redis/Elasticsearch）**
     ```bash
     export LIGHTWEIGHT_MODE=true
     export ALLOW_SQLITE_FALLBACK=true
     export DATABASE_URL=sqlite:///./dev.db
     # 如需禁用 Redis，保持默认即可（轻量模式下会自动跳过）
     ```
   - **完整模式**：配置 `.env` 与 Docker 相同，并确保外部服务已就绪，然后执行 `alembic upgrade head`。
3. 启动后端
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
4. 启动 Celery（可选，轻量模式可跳过）
   ```bash
   celery -A app.celery worker --loglevel=info
   ```

#### 可选运行开关

通过下列环境变量可显式关闭重型依赖，便于本地或 CI 运行：

| 变量 | 默认值 | 作用 |
| --- | --- | --- |
| `ENABLE_ELASTICSEARCH` | `true` | 为 `false` 时跳过 Elasticsearch 连接与索引创建 |
| `ENABLE_MULTI_MODEL` | `true` | 关闭多模型协调器线程 |
| `ENABLE_PERFORMANCE_MONITOR` | `true` | 禁用性能监控后台任务 |
| `ENABLE_CLAUDE_MCP` | `true` | 不初始化 Claude Code MCP 客户端 |
| `SKIP_ELASTICSEARCH_BOOTSTRAP` | `false` | 为 `true` 时不自动创建索引 |

轻量模式 (`LIGHTWEIGHT_MODE=true`) 会自动跳过以上所有组件。

### 前端
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173 默认带有 API 代理
```
如需连接后端地址，可在 `.env` 中设置 `VITE_API_BASE_URL` 或直接使用 `frontend/start.sh` 脚本（支持自定义 `BACKEND_URL`）。

#### Zotero 发行资源

前端三栏界面复用了 Zotero Web Library 的样式与脚本，相关静态资源无需本地编译，可通过脚本直接下载发行版：

```bash
# 下载/刷新官方发行版资源，写入 frontend/public/zotero/
./scripts/build-zotero.sh
```

该脚本会从 `https://www.zotero.org/static/web-library/` 拉取 CSS、JS、字体、图标和 `xdelta3.wasm`，使用前请留意 `NOTICE.md` 中的来源与许可说明。如需锁定特定版本，可改写脚本为下载指定 release，并在文档中记录下载日期/版本号。React 适配层通过 `/zotero/...` 引用这些资源，应确保目录在版本管理中或部署阶段一并发布。

## 测试与质量保证

- 后端单元测试
  ```bash
  pytest
  ```
- 前端静态检查与构建
  ```bash
  cd frontend
  npm run lint
  npm run build
  ```

目前测试全部通过（70 个后端测试 + 新增健康检查覆盖，前端 `lint` 与 `build` 通过）。

## 健康检查与监控

- 存活检查：`GET http://localhost:8000/live`
- 就绪检查：`GET http://localhost:8000/readyz`
- 系统状态：`GET http://localhost:8000/api/system/status`
- Prometheus 指标：`GET http://localhost:8000/metrics`

> `/healthz` 和 `/metrics` 现在会回传运行环境 (`APP_ENV`)、服务启动时长以及活动用户、文献总数和任务排队数量等业务指标，便于外部监控平台采集。

### 邮件通知

若希望启用任务完成或协作邀请等邮件通知，请在 `.env` 中配置：

```
NOTIFICATIONS_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=...
SMTP_PASSWORD=...
SMTP_USE_TLS=true
NOTIFICATIONS_FROM_EMAIL=research-bot@example.com
```

未配置 SMTP 时服务会自动降级为仅记录日志，不会抛出未处理异常。

当通过 Docker Compose 部署时，`backend` 服务会在启动时自动执行 Alembic 迁移，并通过健康检查确保依赖可用；`frontend` 容器会将 `/api`、`/ws`、`/uploads` 代理到后端。

## 目录结构

```
.
├── app/                 # FastAPI 应用代码
├── frontend/            # React 前端
├── alembic/             # 数据库迁移脚本
├── docker/              # Docker 相关文件（前端构建、入口脚本、Nginx 配置）
├── docker-compose.yml   # 一键启动编排
├── requirements.txt     # 后端依赖
├── scripts/             # 外部服务脚本/工具
├── tests/               # 后端测试
└── docs/                # 设计与运维文档（如 websocket_integration_guide.md、notification_setup.md）
```

## 进一步规划

- 补充 Docker 环境下的端到端自动化测试
- 将 `datetime.utcnow()` 替换为时区感知时间戳
- 优化前端构建体积（目前部分 chunk > 500 kB，仅有警告）

欢迎按照上述步骤验证并部署，如需定制化部署或监控集成，可在 `docs/` 目录扩展文档。
