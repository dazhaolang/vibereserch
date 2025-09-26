# 后端测试操作手册

本手册默认在 Linux / macOS 环境下操作，Python ≥3.10，且已安装 MySQL、Redis、Elasticsearch。如果缺少，可参考文末 Docker 命令快速启动。

## 一、准备工作

1. **拉取代码并进入目录**  
   ```bash
   git clone <your-repo-url> && cd vibereserch
   ```

2. **创建虚拟环境并安装依赖**  
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **配置环境变量**  
   ```bash
   cp .env.example .env
   ```
   - `DATABASE_URL`：例如 `mysql://raggar:raggar123@127.0.0.1:3306/research_platform`
   - `REDIS_URL`：例如 `redis://127.0.0.1:6379/0`
   - `ELASTICSEARCH_URL`：例如 `http://127.0.0.1:9200`
   - `MAX_FILE_SIZE` 已以字节为单位，无需修改

4. **初始化数据库**
   ```bash
   mysql -uroot -p < sql/init.sql
   alembic upgrade head
   ```

5. **确保基础服务运行**（如果未启动）：MySQL、Redis、Elasticsearch。

## 二、启动核心组件

1. **FastAPI 应用**  
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   验证：`http://localhost:8000/api/system/health`

2. **Celery Worker**  
   ```bash
   celery -A app.celery worker --loglevel=info
   ```
   如需监控，可另开终端：`flower -A app.celery`

## 三、功能验证流程

### 1. 注册并登录

```bash
# 注册
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "username": "demo", "password": "Demo@1234", "full_name": "Demo User"}'

# 登录
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "demo", "password": "Demo@1234"}'
```

登陆响应中的 `access_token` 供后续调用使用：
```
-H "Authorization: Bearer <access_token>"
```

### 2. 创建项目

```bash
curl -X POST http://localhost:8000/api/project \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{"name": "Auto Research Demo", "description": "测试自动化研究流程"}'
```

返回体包含 `project_id`，后续请求需要。

### 3. 触发自动研究（搜索建库 + 经验生成）

```bash
curl -X POST http://localhost:8000/api/research/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
        "project_id": <project_id>,
        "query": "最新的氢燃料电池催化剂技术",
        "mode": "auto",
        "keywords": ["氢燃料电池", "催化剂"],
        "auto_config": {
          "collect_first": false,
          "enable_ai_filtering": true,
          "enable_pdf_processing": true,
          "enable_structured_extraction": true
        }
      }'
```

- 响应 `tasks` 数组包含搜索建库和经验生成任务。
- 可通过 `GET /api/tasks` 或 `GET /api/project/<id>/tasks` 查看状态。
- 观察 Celery 日志，可看到建库完成后自动触发主经验生成。

### 4. 验证主经验生成

```bash
curl -X GET "http://localhost:8000/api/experience/main?project_id=<project_id>" \
  -H "Authorization: Bearer <token>"
```
若返回非空，主经验已同步。

### 5. 测试澄清交互 + 超时自动选择

1. **启动 WebSocket 客户端**（举例使用 websocat）：
   ```
   websocat ws://localhost:8000/api/websocket/ws/intelligent-interaction/<session_id>
   ```
   初始没有 `session_id`，下一步接口返回后再连接。

2. **发起智能交互会话**
   ```bash
   curl -X POST http://localhost:8000/api/intelligent-interaction/start \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer <token>" \
     -d '{
           "user_input": "请帮我设计光伏材料的实验路线",
           "project_id": <project_id>,
           "context_type": "search"
         }'
   ```

   - 若 `requires_clarification = true`，响应中包含 `clarification_card.timeout_seconds`（默认 5 秒）。
   - 记录 `session_id`，用于 WebSocket 订阅与下一步验证。

3. **等待 5 秒以上**（不要点击选项）
   - Celery worker 会执行 `auto_select_clarification_card`。
   - WebSocket 可收到 `auto_timeout_selection` 事件，包含自动选项信息。
   - 数据库中 `clarification_cards.is_auto_selected = true`。

4. **可选：手动接口测试**
   - `POST /api/intelligent-interaction/{session_id}/select` 提交选项。
   - `POST /api/intelligent-interaction/{session_id}/timeout` 人工触发超时。

### 6. 获取系统健康与任务统计

```bash
curl http://localhost:8000/api/system/health
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/tasks/overview
```

## 四、Docker 快速启动（如本地无服务）

```bash
docker run -d --name mysql -e MYSQL_ROOT_PASSWORD=root -p 3306:3306 mysql:8
docker run -d --name redis -p 6379:6379 redis:7
docker run -d --name es -e "discovery.type=single-node" -p 9200:9200 elasticsearch:8
```
启动后按“准备工作”步骤继续。

## 五、反馈信息

遇到问题时，请记录：
1. 具体请求（注意脱敏 Token）。
2. FastAPI 与 Celery 日志。
3. 如涉及任务执行，给出 `GET /api/tasks/<id>` 返回内容。

完成流程后，把所得响应与日志提供给我，我会协助分析。祝测试顺利！
