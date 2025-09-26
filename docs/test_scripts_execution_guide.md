# 测试脚本执行总览

本文档整理了当前提供给测试团队的自动化脚本，说明运行方式、依赖准备、推荐输出及结果整理建议。所有路径均以仓库根目录为起点。

## 1. 环境准备
- **Python 3.10+**：用于运行后端脚本
  ```bash
  pip install requests websockets
  ```
- **Node.js 18+**：运行 Playwright 前端脚本
  ```bash
  cd frontend
  npm install
  npx playwright install chromium
  cd ..
  ```
- 设置公共环境变量（可写入 `.env` 或在终端导出）：
  ```bash
  export VIBERESEARCH_BASE_URL="http://localhost:8000"
  export VIBERESEARCH_FRONTEND_URL="http://localhost:3000"
  export VIBERESEARCH_TEST_EMAIL="test@example.com"
  export VIBERESEARCH_TEST_PASSWORD="testpass123"
  ```

## 2. 脚本清单与执行指南

### 2.1 后端工作流冒烟测试
- **脚本**：`scripts/backend_workflow_smoke.py`
- **作用**：按真实业务流程串联注册/登录、项目创建、项目与任务仪表盘、性能面板、文献方法等关键 API。
- **命令示例**：
  ```bash
  python3 scripts/backend_workflow_smoke.py \
    --base-url "$VIBERESEARCH_BASE_URL" \
    --email "$VIBERESEARCH_TEST_EMAIL" \
    --password "$VIBERESEARCH_TEST_PASSWORD" \
    --output backend_workflow_results.json
  ```
- **输出整理**：
  - 终端将逐步显示 PASS/FAIL；
  - `--output` 会生成 JSON 报告（推荐纳入测试附件）；
  - 若失败，关注 `detail` 字段获取服务器响应。

### 2.2 API 回归套件
- **脚本**：`scripts/api_regression_suite.py`
- **作用**：覆盖健康检查、认证、用户、项目、文献、任务、监控、性能优化等广泛 API（48 项检查）。
- **命令示例**：
  ```bash
  python3 scripts/api_regression_suite.py \
    --base-url "$VIBERESEARCH_BASE_URL" \
    --email "$VIBERESEARCH_TEST_EMAIL" \
    --password "$VIBERESEARCH_TEST_PASSWORD" \
    --output api_regression_report.json
  ```
- **输出整理**：`api_regression_report.json` 保存每个端点的状态码与响应片段，便于快速定位故障。

### 2.3 WebSocket 稳定性测试
- **脚本**：`scripts/ws_regression_suite.py`
- **作用**：登录后建立 `/ws/global` 连接，统计消息类型/数量，验证实时推送。
- **命令示例**：
  ```bash
  python3 scripts/ws_regression_suite.py \
    --base-url "$VIBERESEARCH_BASE_URL" \
    --email "$VIBERESEARCH_TEST_EMAIL" \
    --password "$VIBERESEARCH_TEST_PASSWORD" \
    --duration 30 \
    --output ws_messages.json
  ```
- **输出整理**：`ws_messages.json` 保存摘要与原始消息，终端会展示类型统计；如需详细分析请附带 JSON。

### 2.4 前端登录流程验证
- **脚本**：`scripts/frontend_login_flow.js`
- **作用**：使用 Playwright 自动化登录 UI，并监控 `/api/auth/login` POST 状态。
- **命令示例**：
  ```bash
  node scripts/frontend_login_flow.js
  ```
- **输出整理**：
  - 终端记录登录接口状态、重定向 URL；
  - 成功生成 `frontend_login_success.png`，失败则输出 `frontend_login_failure.png`。

### 2.5 前端项目工作流验证
- **脚本**：`scripts/frontend_project_flow.js`
- **作用**：先通过后端 API 创建项目，再在前端登录并确认该项目出现在仪表盘，验证前后端联调。
- **命令示例**：
  ```bash
  node scripts/frontend_project_flow.js
  ```
- **输出整理**：
  - 成功时生成 `frontend_project_workflow.png`；
  - 若失败记录 `frontend_project_workflow_failure.png` 与终端报错；
  - 脚本会在结束时自动删除新建项目。

## 3. 推荐的执行顺序
1. `backend_workflow_smoke.py` – 快速确认后端核心流程；
2. `api_regression_suite.py` – 全量回归收集 JSON 报告；
3. `ws_regression_suite.py` – 验证实时能力；
4. `frontend_login_flow.js` – 确认基础 UI 可用性；
5. `frontend_project_flow.js` – 完整验证前后端联调路径。

## 4. 测试输出整理建议
- **汇总表**：将每个脚本终端结果与生成的 JSON/截图列成表格，注明运行时间、环境、负责人员。
- **附件打包**：按日期建立目录，如 `artifacts/2025-09-19/`，集中存放 JSON、截图、异常日志。
- **问题反馈**：出现 FAIL 或 WARN 时，附带命令、环境变量、响应片段及截图，方便研发复现。
- **回归基线**：建议信息化保存最新一轮 `api_regression_report.json` 与 `backend_workflow_results.json`，作为后续对比基线。

## 5. 常见问题排查
- **401/403**：确认测试账号密码、Token 是否过期或缺少权限；
- **404**：检查后端服务是否更新并重启，或脚本中 base_url 是否指向正确实例；
- **Playwright 超时**：确保前端服务器 `npm run dev` 已启动，或网络允许访问；
- **WebSocket 无消息**：确认后端正在产出事件（触发任务、活动通知），或延长 `--duration`。

如需新增测试脚本或扩展覆盖范围，欢迎在 `docs/tester_regression_script_guide.md` 上追加需求并通知研发同步维护。

