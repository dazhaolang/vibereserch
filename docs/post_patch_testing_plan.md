# 完整功能修复回归计划

## 修复摘要
- **注册接口 422 响应**：`/api/auth/register` 现在统一返回 `UserMembershipResponse`，消除了 MembershipType 枚举不匹配造成的响应验证错误。代码位置：`app/api/auth.py`。
- **实时通道异常**：前端 WebSocket 管理器新增候选地址与 Token 检测逻辑，自动在 `VITE_WS_URL`、当前域名及 `localhost` 之间切换，避免连接失败后始终卡在单一地址。代码位置：`frontend/src/services/websocket/WebSocketManager.ts`。

## 建议测试顺序

### 立即回归
1. **注册/登录 API**
   - `POST /api/auth/register`，校验 200 响应及返回的 membership 字段。
   - UI 注册流程（Playwright `user onboarding journey` 场景）。
2. **WebSocket 通信**
   - 浏览器登录后检查控制台无 `max_reconnect_exceeded` 日志。
   - 触发任务，确认 `/ws/global`、`/ws/progress/{taskId}` 可收到消息。

### 扩展验证
1. **任务实时更新**：创建自动研究任务，验证前端任务面板实时刷新。
2. **多候选地址 Fallback**：
   - 人为设置无效的 `VITE_WS_URL`，确认管理器能回退到当前域名。
   - 在 HTTPS 环境确认自动切换为 `wss://` 协议。
3. **负载与断网恢复**：
   - 并行发起 ≥5 个任务，观察是否发生队列阻塞或重复连接。
   - 在连接成功后断网 10 秒再恢复，确认会自动重连并补发队列消息。

### 后续计划
- 文献上传 / 解析流程端到端测试。
- API 映射清单的系统化验证（可使用 `tests/playwright/userJourney.spec.ts` 中 API 集成段落扩展）。
- 压力测试：重点观察 Redis/Celery 队列与 WebSocket 会话上限。

## 备注
- 测试前请刷新前端构建或 `npm run dev`，以加载新的 WebSocket 管理逻辑。
- 若使用 Playwright，建议增加 `PLAYWRIGHT_WS_URL` 环境变量来模拟不同连接场景。
