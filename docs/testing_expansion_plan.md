# VibResearch 扩展测试规划

## 1. 当前自动化状态
- **后端**：`./scripts/run_full_system_suite.sh` 已覆盖健康检查、鉴权、项目/任务/研究模式及 `/api/analysis` 系列接口；新建的任务会在清理阶段自动取消并删除项目。
- **前端**：Playwright 脚本完成登录注册、仪表盘/工作台/文献库/任务中心导航、工作台空态检测、错误页回退以及基础 API 集成。
- **稳定性**：`RUN_ID=20250919_203600` 复跑结果全绿，可作为回归基线。

## 2. 扩展覆盖路线图

### 2.1 后端 API 补强
1. **文献上传与索引**
   - 端点：`/api/literature/upload`、`/api/literature/processing-methods`、`/api/literature/statistics-v2` 等
   - 脚本：在 `scripts/api_regression_suite.py` 新增方法，使用临时 PDF 文件；清理逻辑同步删除测试文献

2. **团队协作与通知**
   - 端点：`/api/collaborative-workspace/*`、`/api/collaboration/*`、通知/邀请相关接口
   - 脚本：引入测试专用账号和团队成员，覆盖创建/加入/邀请等流程

3. **用户设置与安全**
   - 端点：`/api/user/password`、`/api/user/usage-statistics`、会员升级
   - 脚本：验证密码修改成功/失败路径、配额计算、会员类型切换

> 统一入口仍是 `./scripts/run_full_system_suite.sh`，关注 `integration/api_regression.json` 中新增条目的 PASS/WARN。

### 2.2 前端旅程扩展
1. **研究工作台自动流程**
   - 流程：选择项目 → 触发 RAG/自动模式 → 观察任务提示与结果面板
   - 脚本：在 Playwright 中新增专用场景，必要时通过 API 预置项目数据

2. **文献库操作**
   - 流程：上传示例文献 → 切换卡片/表格视图 → 搜索过滤 → 查看详情
   - 脚本：使用浏览器文件上传、校验筛选条件与列表更新

3. **任务中心交互**
   - 流程：打开任务抽屉、取消/重试按钮、状态徽标
   - 脚本：配合 API 创建任务后进入页面，校验 UI 状态与提示

4. **界面辅助功能**
   - 流程：光/暗模式切换、通知面板、用户资料菜单
   - 脚本：验证主题切换后的样式标记、通知小红点、菜单项可见性

> 所有 Playwright 扩展仍保留截图/视频/日志，RUN_ID 与 PLAYWRIGHT_RUN_ID 应保持一致，方便回溯。

### 2.3 手动验证保留
- 实时协作（WebSocket 互动）、MCP 工具链、外部服务深度集成仍需人工确认；待模型数据与 Mock 框架稳定后再纳入自动化。

## 3. 执行与归档
1. 测试团队统一执行命令：
   ```bash
   RUN_ID=<stamp> PLAYWRIGHT_RUN_ID=<stamp> ./scripts/run_full_system_suite.sh
   ```
2. 归档目录：`artifacts/system_tests/<RUN_ID>/`，包含 `summary.log`、`integration/api_regression.json`、`frontend/playwright.log`、`frontend/playwright-report/` 等。
3. 汇报原则：参考 `docs/full_stack_testing_playbook.md`，在 `REGRESSION_PROOF.md` 记录新增覆盖/待覆盖模块。

## 4. 下一步协作
- 完成本说明中任一扩展模块后，请附带新的 RUN_ID 产物和失败截图/日志（如有）回传，我们再做复审。
- 对于暂未自动化的场景（协作、MCP、外部服务），请在发布前做一次手工巡检，并在测试报告中注明执行情况。

---
如需新增脚本或调整执行环境，保持与开发团队沟通，确保脚本指向最新接口与 UI 元素。EOF
