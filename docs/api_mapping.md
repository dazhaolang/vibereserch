# 前端功能与后端接口映射（基于 154.12.50.153 环境）

本文仅依据当前前端代码（React + Vite 项目）梳理后端接口调用行为，便于按照前端实际用法编写和执行后端测试。所有请求默认以 `http://154.12.50.153:8000` 为基础地址，除特别说明外均需要带上 `Authorization: Bearer <token>` 头。

## 使用说明
- 浏览器访问前端时默认走 `http://154.12.50.153:3000`，同域下的 API 请求直连 `http://154.12.50.153:8000`。
- WebSocket 默认地址：`ws://154.12.50.153:8000/ws/global`（事件总线），进度流使用 `/ws/progress/{taskId}`。
- 基础 Axios 客户端位置：`src/services/api/client.ts`；某些旧代码仍使用 `src/api/client.ts`。
- React Query 相关 hook 位于 `src/hooks/api-hooks.ts`；Zustand store 与动作在 `src/stores`、`src/store` 目录。

## 1. 应用初始化与认证
- **GET `/api/user/profile`**
  - 前端触发：`App.tsx` 调用 `useAppStartup`（`src/hooks/use-app-startup.ts`）。
  - 作用：应用加载时拉取当前登录用户资料，失败（401/403）会在控制台警告但继续渲染匿名态。
  - 测试要点：验证返回体符合 `src/types/user.ts` 中的结构；确保 401 时不会造成无限重试。

- **未直接挂接但已定义的认证动作**（均在 `src/services/api/auth.ts`）：
  - `POST /api/auth/register`
  - `POST /api/auth/login`
  - `POST /api/auth/logout`
  - `POST /api/auth/request-verification`
  - `POST /api/auth/verify-email`
  - `POST /api/auth/forgot-password`
  - `POST /api/auth/reset-password`
  - `PUT /api/user/profile`
  - `PUT /api/user/password`
  > 前端暂未提供界面调用，但 store (`src/stores/auth-store.ts`) 会在 `login/register/logout` 成功时写入或清理 token。

## 2. 仪表盘与全局统计
- **GET `/api/project/list`**
  - 入口：React Query hook `useProjects`（`src/hooks/api-hooks.ts`）在 `DashboardPage`（`src/pages/dashboard/dashboard-page.tsx`）初始化时调用；同时 `ProjectSelector` 组件也会手动调用 `projectAPI.getProjects()`。
  - 要求：返回数组需包含 `id/name/title/description/created_at/progress_percentage/literature_count` 等字段，前端会做 `normalizeProject` 处理。

- **GET `/api/tasks/overview`**
  - 入口：`useTaskOverview`（`src/hooks/api-hooks.ts`），`DashboardPage` 轮询（5 秒一次）。
  - 预期结构：
    ```json
    {
      "total_tasks": 0,
      "status_breakdown": {"completed": 0, ...},
      "running_task_ids": [],
      "cost_summary": {"total_cost": 0, "estimated_remaining": 0},
      "recent_tasks": [ ... ]
    }
    ```
  - 备注：若后端暂不支持该路径，需要补齐或改为兼容旧接口。

- **GET `/api/user/usage-statistics`**
  - 入口：`fetchUsageStatistics`（`src/services/api/usage.ts`），仪表盘用来展示总项目数、文献数、月度调用等。

## 3. 项目管理相关
- **GET `/api/project/list`**
  - 组件：`ProjectSelector`（`src/components/workspace/ProjectSelector.tsx`）、`ResearchConsole`（`src/pages/research/research-console.tsx`）、`LibraryPage` 等处重复使用。
  - 额外要求：若返回为空，前端会自动提示创建示例项目。

- **POST `/api/project/create-empty`**
  - 组件：`ProjectSelector` 新建按钮、`ProjectListDemo` 页面（`src/pages/ProjectListDemo.tsx`）。
  - 请求体：`{ name: string; description?: string; category?: string }`。
  - 响应：预期返回完整项目对象，立即写入列表。

- **DELETE `/api/project/{id}`**
  - 组件：`ProjectListDemo` 删除操作。
  - 响应：期待 `{ message: string }` 或 204；前端删除本地列表。

- **其他项目接口（暂未在 UI 中调用）**：创建完整项目 `/api/project/create`、方向分析 `/api/project/determine-direction`、上传/索引文件 `/api/project/{id}/upload-files`、`/index`、更新 `/api/project/{id}`。

## 4. 研究交互（RAG / Deep / Auto）
- **POST `/api/interaction/start`**
  - 入口：
    - 研究控制台 `ClarificationDeck`（`src/components/research/clarification-deck.tsx`）；`context_type` 为当前模式（`rag/deep/auto`）。
    - 研究工作台 `useResearchStore.submitQuery`（`src/stores/research.store.ts`）在自动模式下先尝试澄清。
    - 着陆页 `LandingPage`（`src/pages/landing/landing-page.tsx`）分析意图。
  - 请求体核心字段：`project_id`, `context_type`, `user_input`, `additional_context`（可空）。
  - 响应预期：`{ success, session_id, requires_clarification, clarification_card?, direct_result? }`。

- **POST `/api/interaction/{sessionId}/select`**
  - 入口：`InteractionCards`（`src/components/interaction/InteractionCards.tsx`）以及 `ClarificationDeck` 自动选择逻辑。
  - 请求体：`{ option_id, selection_data: {}, client_timestamp? }`。

- **POST `/api/interaction/{sessionId}/custom`**
  - 入口：`InteractionCards` 自定义输入提交。
  - 请求体：`{ custom_input: string, context: {}, client_timestamp }`。

- **POST `/api/interaction/{sessionId}/timeout`**
  - 入口：`InteractionCards.handleTimeout`，倒计时结束自动触发。

- **POST `/api/research/query`**（最核心）
  - 触发位置：
    - `RagPanel` / `DeepPanel` / `AutoPanel`（`src/components/research/*.tsx`）。
    - `ResearchWorkspace`（`src/pages/workspace/ResearchWorkspace.tsx`）内的 `useResearchStore.runAutoPipeline`、`submitQuery`。
    - 深度研究页 `deep-research-page.tsx`、自动模式页 `auto-research-page.tsx`（`src/pages/deep`、`src/pages/auto`）。
  - 常见载荷：
    - RAG：`{ project_id, query, mode: 'rag', max_literature_count }`
    - Deep：`{ project_id, query, mode: 'deep', processing_method, keywords?, auto_config? }`
    - Auto：`{ project_id, query, mode: 'auto', keywords?, auto_config?, agent? }`
  - 响应：需要返回 `{ mode, payload }`。payload 会被当作研究结果或任务说明。

- **POST `/api/research/analysis`**
  - 入口：深度研究页 `handleDecomposeQuery`（`src/pages/deep/deep-research-page.tsx`）。
  - 用途：根据查询推荐子问题与关键词。

- **POST `/api/tasks/{task_id}/result`**
  - 入口：`ResearchWorkspace` 在收到 `research_result` WebSocket 事件后调用，写入结果与任务绑定。
  - 请求体：`{ result_id, status: 'completed_with_result' }`。

> `src/services/api/research.ts` 还定义了历史、停止、重试、导出、评分等接口，目前 UI 未调用，可按需补测。

## 5. 任务监控
- **GET `/api/task`**
  - 入口：`TasksPage`（`src/pages/tasks/tasks-page.tsx`）通过 `fetchTasks`（`src/services/api/tasks.ts`）。支持查询参数 `project_id`、`status`。
  - 响应：期望 `{ tasks: TaskDetail[] }`，前端会抽取基本字段。

- **GET `/api/task/{id}`**
  - 入口：`TaskDetailDrawer`（`src/components/tasks/task-detail-drawer.tsx`）。
  - 响应需包含 `progress_logs`、`result`、`error_message` 等。

- **GET `/api/task/stats`**
  - 封装在 `src/services/api/task-stats.ts`，当前页面未使用，可用于后续统计。

## 6. 文献库
- **GET `/api/literature`**
  - 入口：
    - `LibraryPage`（`src/pages/library/library-page.tsx`），参数：`project_id`, `query`, `page`, `size`。
    - `LiteratureSelector`（`src/components/workspace/LiteratureSelector.tsx`）使用原生 `fetch` 请求，参数命名为 `page_size`、`search` —— ⚠️ 后端需要兼容或前端需修正。

- **POST `/api/literature/search`**
  - 入口：`literatureAPI.fetchProjectLiterature` 在有搜索词时使用；`useLiteratureSearch` hook 亦指向该接口。

- **GET `/api/literature/project/{projectId}`**
  - 入口：`literatureAPI.fetchProjectLiterature` 在无搜索词时调用。

- **POST `/api/literature/upload`**
  - 入口：`LiteratureUploadModal`（`src/components/literature/LiteratureUploadModal.tsx`），FormData 包含 `file`，可选 `project_id`，以及 `import_type=zotero`。
  - 返回结构需含 `{ success, data }` 或 `{ imported_count }`。

- **POST `/api/literature/upload-batch`**
  - 入口：同上，批量上传。

- **POST `/api/literature/ai-search`**
  - 入口：`handleDOIImport`，payload `{ query, project_id?, max_results }`。
  - 期望返回 `{ success, papers: [], total_count }`。

- **POST `/api/literature/project/{projectId}/batch-add`**
  - 入口：`LiteratureUploadModal` AI 搜索完成后写库。

- **未在 UI 中露出的操作**：`DELETE /api/literature/{id}`、`PUT /api/literature/{id}`、`POST /api/literature/{id}/tags`、`/note`。

## 7. WebSocket 通道
- **全局业务事件**：`ws://154.12.50.153:8000/ws/global`
  - 管理：`src/services/websocket/WebSocketManager.ts`。
  - 监听事件：`task_progress`、`interaction_update`、`research_result`、`experience_generated`。
  - 使用者：`ResearchWorkspace`（`src/pages/workspace/ResearchWorkspace.tsx`）、`src/stores/research.store.ts`（会针对任务/会话进一步订阅）。
  - 需要在 URL 上附带 `token` 查询参数（自动读取本地存储）。

- **任务实时进度**：`ws[s]://{host}/ws/progress/{taskId}[?token=...]`
  - 管理：`src/services/ws/progress-socket.ts`。
  - 使用者：`TaskDetailDrawer` 实时事件列表。

- **Socket.IO 连接**：`http://154.12.50.153:8000`
  - 管理：`src/api/websocket.ts`。
  - 使用者：自动研究页 `src/pages/auto/auto-research-page.tsx` 加入/离开 `join_research_session` 房间、监听 `task_progress`、`notification` 等。
  - 需要确认后端是否同时提供 Socket.IO 服务。

## 8. 其他辅助接口
- **GET `/api/performance/dashboard`**：封装于 `src/services/api/dashboard.ts`，暂未使用。
- **GET `/api/system/status`、`/api/system/capabilities`**：在 `src/hooks/api-hooks.ts` 定义 `useSystemStatus/useSystemCapabilities`，尚未挂接界面。
- **MCP 工具相关**：`/api/mcp/tools`、`/api/mcp/run` 定义在 `src/api/client.ts`，暂无入口。

## 9. 详细测试计划（逐步执行）

以下步骤默认后端监听 `http://154.12.50.153:8000`，所有请求需在 Header 中附带 `Authorization: Bearer <token>`。示例 `curl` 命令以 Linux/macOS 为例，Windows 可改用 PowerShell。每一步都列明“通过条件”，若结果不符请立即断点排查。

### 9.1 准备阶段
1. **获取访问令牌**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/auth/login' -H 'Content-Type: application/json' -d '{"email": "<测试账号>", "password": "<密码>"}'
     ```
   - 通过条件：HTTP 200；响应体包含 `access_token`，且 `token_type` 为 `bearer`。
2. **验证当前用户**  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/user/profile' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；返回中 `id`、`email`、`username`、`membership` 字段齐全。

### 9.2 项目基础流程
1. **创建空项目**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/project/create-empty' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"name": "API 测试项目", "description": "自动化测试"}'
     ```
   - 通过条件：HTTP 200/201；响应含 `id`、`name`、`status`，`status` 为 `empty` 或 `active`。
2. **列出项目**  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/project/list' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；列表中出现“API 测试项目”，且包含 `literature_count`、`created_at` 字段。
3. **获取项目详情**（可选）  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/project/<project_id>' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；`id` 与请求一致，`keywords` 为数组。

### 9.3 文献导入路径
1. **上传 PDF**（需准备 `sample.pdf`）  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/literature/upload' -H 'Authorization: Bearer <token>' -F 'file=@sample.pdf' -F 'project_id=<project_id>'
     ```
   - 通过条件：HTTP 200；响应包含 `success: true` 与 `data.id`。
2. **AI 搜索导入**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/literature/ai-search' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"query": "solid electrolyte", "project_id": <project_id>, "max_results": 3}'
     ```
   - 通过条件：HTTP 200；`success` 为 true，`papers` 为数组。
3. **批量写入项目文献**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/literature/project/<project_id>/batch-add' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"literature": [...]}'
     ```
   - 通过条件：HTTP 200；包含 `added_count` ≥ 1。
4. **查询项目文献**  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/literature?project_id=<project_id>&page=1&size=20' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；`items` 为数组且长度 > 0。

### 9.4 RAG 模式回归
1. **触发 RAG 研究**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/research/query' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"project_id": <project_id>, "query": "锂离子电池循环效率", "mode": "rag", "max_literature_count": 12}'
     ```
   - 通过条件：HTTP 200；`mode` 为 `rag`，`payload.answer` 存在或返回 `status: pending` 与任务信息。
2. **若返回任务 ID**（异步）：轮询 `GET /api/task/<task_id>` 直至 `status` 为 `completed` 或 `failed`。  
   - 通过条件：最终状态为 `completed`，`result` 字段含回答内容。

### 9.5 深度研究模式
1. **查询分析**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/research/analysis' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"project_id": <project_id>, "query": "固态电解质热稳定性", "context": {"mode": "deep"}}'
     ```
   - 通过条件：HTTP 200；响应含 `recommended_mode`、`sub_questions` 数组。
2. **提交深度任务**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/research/query' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"project_id": <project_id>, "query": "固态电解质热稳定性", "mode": "deep", "processing_method": "standard", "keywords": ["solid electrolyte", "thermal stability"]}'
     ```
   - 通过条件：HTTP 200；`mode` 为 `deep`；若返回 `task_ids`，对应任务最终需 `completed`。

### 9.6 自动模式（含互动澄清）
1. **启动互动**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/interaction/start' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"project_id": <project_id>, "context_type": "auto", "user_input": "请自动规划固态电解质研究"}'
     ```
   - 通过条件：HTTP 200；`success` 为 true；若 `requires_clarification` 为 true，返回 `session_id` 与 `clarification_card`。
2. **提交澄清选项或自定义输入**  
   - 命令示例：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/interaction/<session_id>/select' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"option_id": "<card_option_id>", "selection_data": {}}'
     ```
   - 通过条件：HTTP 200；响应更新会话状态。
3. **提交自动任务**  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/research/query' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"project_id": <project_id>, "query": "固态电解质研究自动方案", "mode": "auto", "auto_config": {"enable_ai_filtering": true, "enable_pdf_processing": true, "enable_structured_extraction": true}, "agent": "claude"}'
     ```
   - 通过条件：HTTP 200；`mode` 为 `auto`；若返回 `payload.task_ids`，任务中心能看到新任务。
4. **任务绑定结果**（如需手动补写）  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/tasks/<task_id>/result' -H 'Authorization: Bearer <token>' -H 'Content-Type: application/json' -d '{"result_id": "<研究结果ID>", "status": "completed_with_result"}'
     ```
   - 通过条件：HTTP 200；返回确认消息。

### 9.7 任务中心与实时进度
1. **任务列表**  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/task' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；`tasks` 数组包含上一阶段生成的任务。
2. **任务详情**  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/task/<task_id>' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；`progress_logs` 为数组。
3. **实时进度 WebSocket**  
   - 命令（需安装 `wscat`）：
     ```bash
     wscat -c 'ws://154.12.50.153:8000/ws/progress/<task_id>?token=<token>'
     ```
   - 通过条件：连接期间可收到包含 `task_id`、`progress`、`status` 的 JSON 消息。

### 9.8 仪表盘统计
1. **任务概览**  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/tasks/overview' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；响应含 `total_tasks`、`status_breakdown`。
2. **用户使用统计**  
   - 命令：
     ```bash
     curl -X GET 'http://154.12.50.153:8000/api/user/usage-statistics' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；`usage.total_projects` ≥ 1。

### 9.9 WebSocket 全局事件验证
1. **连接业务总线**  
   - 命令：
     ```bash
     wscat -c 'ws://154.12.50.153:8000/ws/global?token=<token>'
     ```
   - 通过条件：研究或任务操作时可收到 `task_progress`、`research_result` 等事件。
2. **Socket.IO 兼容性检查**（如后端提供）  
   - 命令：
     ```bash
     node -e "const { io } = require('socket.io-client'); const socket = io('http://154.12.50.153:8000', { auth: { token: '<token>' } }); socket.on('connect', () => console.log('connected')); socket.onAny((event, data) => console.log(event, data));"
     ```
   - 通过条件：成功连接且无错误事件。

### 9.10 回归与清理
1. **删除测试项目**（若后端支持）  
   - 命令：
     ```bash
     curl -X DELETE 'http://154.12.50.153:8000/api/project/<project_id>' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200/204；再次调用 `GET /api/project/list` 时项目已移除。
2. **退出登录**（确认令牌失效）  
   - 命令：
     ```bash
     curl -X POST 'http://154.12.50.153:8000/api/auth/logout' -H 'Authorization: Bearer <token>'
     ```
   - 通过条件：HTTP 200；随后访问 `GET /api/user/profile` 返回 401。

按照上述顺序执行可以覆盖前端当前使用的主要接口与实时能力。

## 10. 潜在对齐问题/注意事项
- `LiteratureSelector` 使用的查询参数为 `page_size`、`search`，与 `literatureAPI.getLiterature` 的 `size`、`query` 不一致；建议后端临时兼容或前端修正。
- `useTaskOverview` 依赖 `/api/tasks/overview`，若后端仍提供旧版 `/api/task/stats`，需新增路由或前端改写。
- 自动模式页面引用了 Socket.IO 客户端（`src/api/websocket.ts`），需要后端提供兼容的 Socket.IO 服务；否则应退回 HTTP/WebSocket 实现。
- 多处仍保留未使用的接口封装（如系统状态、项目模板等），在移除前请确认后端是否计划支持，以免出现“前端调用缺失”误判。
- 所有请求均会自动附带 `Bearer` 头（通过 zustand store 存储的 access token），后端需保证跨域与 CORS 已允许 `http://154.12.50.153:3000`。

以上映射可作为后端性能测试、契约校验或对齐排查的基准，若某个前端功能修改了请求路径，请同步更新本文档。
