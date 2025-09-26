# 回归测试脚本执行指南

本指南汇总了新编写的自动化脚本，帮助测试同事快速覆盖后端 API、WebSocket 以及前端登录流程。运行结束后请收集日志或 JSON 输出，反馈异常给研发。

## 环境准备
- **Python 3.10+**：确保已安装 `requests` 与 `websockets`
  ```bash
  pip install requests websockets
  ```
- **Node.js 18+** 与 Playwright 依赖
  ```bash
  cd frontend
  npm install
  npx playwright install chromium
  cd ..
  ```
- 根据测试环境设置以下变量（可写入 `.env` 或直接导出）：
  ```bash
  export VIBERESEARCH_BASE_URL="http://154.12.50.153:8000"
  export VIBERESEARCH_FRONTEND_URL="http://154.12.50.153:3000"
  export VIBERESEARCH_TEST_EMAIL="test@example.com"
  export VIBERESEARCH_TEST_PASSWORD="testpass123"
  ```

## 1. 后端 API 回归脚本
- **脚本**：`scripts/api_regression_suite.py`
- **说明**：覆盖健康检查、认证、用户、项目、任务、监控、性能优化、智能助手等核心 GET/POST 接口。若提供 `--output` 将生成 JSON 报告。
- **示例命令**：
  ```bash
  python3 scripts/api_regression_suite.py \
    --base-url "$VIBERESEARCH_BASE_URL" \
    --email "$VIBERESEARCH_TEST_EMAIL" \
    --password "$VIBERESEARCH_TEST_PASSWORD" \
    --output api_regression_report.json
  ```
- **输出**：终端会显示每个接口的状态（PASS/WARN/FAIL），并保存概要 + 200 字符以内的响应片段。请将 `api_regression_report.json` 与终端关键日志打包反馈。

## 2. WebSocket 稳定性脚本
- **脚本**：`scripts/ws_regression_suite.py`
- **说明**：登录后建立 `/ws/global` 连接，默认监听 15 秒，统计消息类型与数量，验证全局广播是否正常。
- **示例命令**：
  ```bash
  python3 scripts/ws_regression_suite.py \
    --base-url "$VIBERESEARCH_BASE_URL" \
    --email "$VIBERESEARCH_TEST_EMAIL" \
    --password "$VIBERESEARCH_TEST_PASSWORD" \
    --duration 20 \
    --verbose \
    --output ws_messages.json
  ```
- **输出**：终端显示接收的消息数量及类型分布，`--verbose` 会打印实时消息内容。把 `ws_messages.json` 与控制台摘要提供给研发分析。

## 3. 前端登录流程脚本
- **脚本**：`scripts/frontend_login_flow.js`
- **说明**：使用 Playwright 驱动 Chromium 访问 `/auth`，填入账号密码，验证能重定向至仪表盘并截屏。
- **示例命令**：
  ```bash
  node scripts/frontend_login_flow.js
  ```
- **输出**：成功时生成 `frontend_login_success.png`；失败时生成 `frontend_login_failure.png` 并在终端显示报错。截图 + 终端日志请一并记录。

## 日志与反馈建议
1. 每个脚本运行后将终端输出复制到汇总文档中，特别关注 `FAIL`、`ERROR` 或 WebSocket 连接异常。
2. 若脚本报错，请保留命令、环境变量设置、报错堆栈及相关截图。
3. 如需补测特定接口，可在 `scripts/api_regression_suite.py` 中新增或修改测试用例（欢迎标注 TODO，后续跟进自动化扩展）。
4. 反馈时请附带脚本版本（Git commit）、运行时间段和目标环境，方便复现。

执行完成后，请将所有报告文件与突出异常集中发给研发团队，后续我们会根据反馈继续加固接口与前端逻辑。

