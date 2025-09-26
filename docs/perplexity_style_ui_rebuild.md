# Perplexity式界面重构调查报告与开发计划

## 一、背景与目标
- 目标是将当前的研究平台前端体验重构为类似 Perplexity、ChatGPT、Claude 的简洁对话式界面，同时强化文献库构建、切换与自动化搜索能力。
- 后端 API 已经覆盖文献检索、ResearchRabbit 集成、任务编排等功能，需要在前端重新编排交互，并补充进度状态、懒加载 PDF 等细节。
- 本报告评估现状、识别缺口，并提出详细的技术实施与阶段计划。

## 二、现状调研
### 2.1 前端架构现状
- 核心布局位于 `frontend/src/components/layout/app-layout.tsx:7`，采用左侧收缩侧边栏与顶部导航 (`sidebar.tsx`, `top-bar.tsx`) 组合，整体风格偏企业管理台。
- `frontend/src/pages/research/research-console.tsx:6` 通过 `ModeSwitcher`、`ClarificationDeck`、`RagPanel`、`DeepPanel`、`AutoPanel` 将不同研究模式分屏呈现。
- 文献库页面 `frontend/src/pages/library/library-page.tsx:1` 为多卡片/表格切换布局，内置上传、批量操作、引用图谱等高级功能，组件体量较大且状态管理复杂。
- 全局状态由多个 Zustand store (`frontend/src/stores/`) 管理，路由基于 React Router 6，UI 依赖 Ant Design + Tailwind。

### 2.2 对话与模式能力
- RAG/深度研究/全自动流程分别封装在 `frontend/src/components/research/rag-panel.tsx`, `deep-panel.tsx`, `auto-panel.tsx`，均以一次性提问+结果面板为主，缺少多轮对话与消息流组件。
- `ClarificationDeck` 调用 `startInteraction` (后端 `app/api/intelligent_interaction.py`) 进行前置澄清，但最终结果仍落在静态面板中，未形成对话记录。

### 2.3 文献库与构建流水线
- 文献管理依赖 `literatureAPI` (`frontend/src/services/api/literature.ts`) 与 `literature_workflow`、`search_and_build_library_service` 等后端模块。
- 后端已具备 ResearchRabbit 搜索、AI 筛选、PDF 下载、轻结构化、Elasticsearch 入库等流程 (`app/services/search_and_build_library_service.py:1`)，也提供批处理状态推送与任务服务。
- 当前前端缺少统一的“文献库概览/选择”入口，也没有展示构建进度、估算完成百分比的界面。

### 2.4 任务与合并
- 任务队列、进度广播由 Celery 与 websocket 实现 (`app/api/websocket.py`, `app/tasks/literature_tasks.py`)，但前端仅零散使用，未在文献库或研究 UI 中集中呈现。
- 数据合并与备份逻辑在 `app/services/data_sync_service.py`、`search_pipeline` 中已有封装，需要对接前端状态提醒。

## 三、需求与缺口分析
- **界面风格**：现有多栏目管理台与目标的对话式布局差异大，需要重构全局布局、导航、主题。
- **文献库切换**：目前在 `ClarificationDeck` 中以项目下拉形式存在，无法满足“左上角模型位展示文献库切换”的即时操作与空库自动跳转需求。
- **文献库概览**：缺少统一的文献库选择/概览页，现有 `library-page` 更像单库管理。需要新增概览视图支撑历史库列表、构建状态、进度条、备份提示。
- **自动建库流程**：后端已有 ResearchRabbit 集成，但前端未提供“与 AI 确认主题→自动建库→每 200 篇抽检”的交互节点与可视化进度。
- **懒加载 PDF**：当前文献详情通过 Ant Design Drawer 直接渲染，缺少懒加载策略与性能防护。
- **对话模式切换**：模式之间没有会话上下文，RAG/深度经验模式无法在一次对话中切换；全自动模式 UI 与其它模式混合，违背新需求。
- **库合并与备份提示**：用户保存/退出后端会执行合并，但前端未告知状态，也无法阻止用户在迁移中切换。

## 四、目标信息架构与用户流程
### 4.1 全局布局
- 采用三区域结构：左侧窄栏显示“新研究”“文献库”“高级设置”等入口；主区域承载对话式界面；右侧可选展示上下文（选中模式、相关文献）。
- 左上角替换为“当前文献库”选择器：展示库名称与状态标签（同步中/构建中/只读），点击触发库选择弹窗。
- 无文献库 + 非全自动模式时，阻断主界面，弹出库选择器引导到文献库概览页。

### 4.2 文献库概览与管理
- 新增“文献库概览”页：卡片列出所有库（名称、文献量、构建阶段、百分比、最近更新时间、备份状态），最后一项是“新建文献库”。
- 新建流程拆分为：主题确认（与 AI 对话）、构建参数设定（来源、目标篇数、抽检策略）、实时进度（200 篇抽样反馈、可提前停止）、完成后合并提示。
- 现有 `library-page` 调整为“文献库详情”，内容布局可借鉴 Zotero：左侧库目录及标签，中部文献表格，右侧文献详情/引用网络。PDF 渲染使用懒加载（IntersectionObserver + 按需加载阅读器组件）。

### 4.3 对话主界面
- 顶部显示“模式卡片”：`RAG`、`深度经验增强`、`全自动流水线`。前两者允许多轮对话中即时切换（保持共享上下文，切换时向后端提交模式标识）。全自动模式在专用标签页启动，不与其它模式混用。
- 中央区域使用消息气泡形式记录用户与 AI 对话，底部输入框支持模式切换、引用插入、文献预览。
- 侧边上下文栏展示当前检索使用的文献条目、引用卡片、构建状态提醒。

### 4.4 自动建库特性
- AI 确认阶段：基于 `ClarificationDeck` 扩展为聊天式组件，记录关键词、约束条件，并允许用户修改。
- 构建阶段：连接 `search_and_build_library_service` 的进度事件，每完成 200 篇调用后端评估接口返回摘要，实时展示继续/停止选项。
- 完成阶段：提示“合并进行中”，提供“继续使用旧版文献库”或“切换到新版本”选择，直到后台完成合并任务。

## 五、技术实施方案
### 5.1 前端重构策略
1. **布局与导航重构**
   - 新建 `frontend/src/components/shell/PerplexityShell.tsx`，封装左侧纵向导航、顶部模式卡片、主对话区。弃用 `AppLayout` 或保留兼容模式。
   - 重构路由：将 `/research` 作为默认主页，`/library/overview` 进入文献库概览，`/library/:id` 进入详情。
   - 更新 Zustand 布局 store，支持窄栏固定宽度与光暗主题切换。

2. **对话流组件**
   - 设计通用 `ChatSession` 组件，管理消息数组、模式、引用。为 RAG/深度模式复用，后端接口通过 `mode` 字段区分。
   - 连接 websocket (已存在于 `frontend/src/services/api/websocket.ts` 若有) 或使用 react-query 轮询，保证生成过程逐条推送。

3. **模式切换与状态管理**
   - 新建全局 store 记录 `conversationMode`, `currentLibraryId`, `sessionId`。在模式切换时调用新的 session API，保留上下文。
   - 全自动模式单独页面 `AutoOrchestratorPage`，沿用 `auto-panel` 逻辑但以聊天形式展示流水线步骤。

4. **文献库概览与详情**
   - 新建 `frontend/src/pages/library/library-overview.tsx`：调用 `/api/project` / `/api/literature/library-status`（需新增）拉取统计数据。
   - 详情页组件化：左侧 `CollectionTree`、中部 `LiteratureTable`（虚拟滚动）、右侧 `LiteratureInspector`（分段展示 metadata、引用、标签、懒加载 PDF）。
   - PDF 浏览使用动态 import（如 `react-pdf`）并依赖 IntersectionObserver 触发加载。

5. **弹窗与指引**
   - 无库时触发 `LibraryRequiredModal`，引导创建或切换。
   - 在合并/迁移阶段显示 `LibraryProcessingBanner`，禁用部分高危操作。

### 5.2 后端与数据层改动
1. **文献库统计接口**
   - 新增 `/api/library/overview`，返回每个库的文献总数、构建状态、进度、抽检评估、最近更新时间、是否有备份。可以复用 `SearchAndBuildLibraryService` 内部统计 + `DataSyncService`。

2. **构建进度与抽检**
   - 在 `search_and_build_library_service` 的 200 篇节点调用 AI 审核接口，写出 `/api/library/build/checkpoint` 事件，通过 websocket 推送与数据库 `library_build_log` 持久化。

3. **库合并事务**
   - 强化 `DataSyncService.merge_libraries`：在开始前创建快照 ID，完成后更新状态，暴露 `/api/library/merge-status/{id}` 供前端轮询。

4. **模式化 Session API**
   - 扩展 `app/api/research/routes.py`：新增 `POST /api/research/sessions` 创建会话并返回 `session_id`、支持 `mode` 与 `library_id`；`POST /api/research/sessions/{id}/messages` 追加消息，返回流式结果。
   - 对接现有 `triggerResearch` 等函数，将 RAG/Deep 模式封装为统一响应结构。

5. **权限与配置**
   - 确保当用户未绑定文献库时，RAG/Deep API 返回明确错误码 (`422`)，供前端触发弹窗。

### 5.3 任务与基础设施
- 校验 Celery 队列对新建库高并发的承载能力，必要时为大任务引入 Redis Stream 反馈。
- Elasticsearch 索引在合并前需新建别名策略，保证旧库仍可查询；合并完成后切换别名并清理旧索引。
- 对 ResearchRabbit API 调用增加超时与速率限制配置，避免全自动模式多次触发被封禁。

## 六、开发阶段计划
1. **阶段 0：需求冻结与 UI 原型 (1 周)**
   - 与设计确认 IA、线框与视觉稿；梳理模式切换、文献库状态机。
2. **阶段 1：基础架构重构 (2 周)**
   - 实现新 Shell、导航、全局 store；迁移研究页到聊天框架；保持旧页面可访问以便回归测试。
3. **阶段 2：文献库概览与详情 (2-3 周)**
   - 开发概览视图、详情页虚拟滚动、懒加载 PDF；对接新统计接口；处理上传/筛选模块迁移。
4. **阶段 3：自动建库与进度可视化 (2 周)**
   - 前后端联调 ResearchRabbit 流水线、抽检策略、合并提示；完善 websocket 推送。
5. **阶段 4：模式会话统一与 QA (1-2 周)**
   - 整合 RAG/Deep/Auto 调用链，补充异常处理、权限控制；执行端到端测试与性能调优。
6. **阶段 5：灰度发布与回滚策略 (1 周)**
   - 支持按用户开关新界面；记录指标；准备回滚方案。

## 七、测试与验收策略
- **单元测试**：补齐前端组件测试（React Testing Library）以及后端新接口 pytest，用例覆盖模式切换、库状态转换、进度节点。
- **集成测试**：扩展 `tests/test_task_service_dispatch.py` 与新建 `tests/test_library_build_flow.py`，模拟 1000 篇构建流程及抽检终止路径。
- **性能测试**：针对懒加载 PDF、虚拟滚动和 websocket 消息量进行压力测试；确保 1000 篇文献加载 < 2 秒初始列表。
- **回归测试**：保留旧功能路径，执行 `npm run lint`, `npm run build`, `pytest`。

## 八、风险与开放问题
- **设计资源**：需要 UI/UX 支持确定聊天式界面细节；无设计稿将影响迭代效率。
- **ResearchRabbit 额度**：需确认 API 调用额度与授权流程，必要时实现请求队列与缓存。
- **合并时数据一致性**：大规模库合并需完善事务与失败回滚策略；建议引入快照表或 S3 备份。
- **权限分级**：若存在多人共享库，需要确定切换、编辑、合并权限模型。
- **国际化**：新界面需兼顾中英文，建议同步梳理 i18n 方案。
- **时间计划**：总体 8-10 周迭代，若要压缩周期需并行小组协作，提前明确接口协议。

---

本报告为后续前端重构与相关后端改造的基础，请在启动前评审确认需求、资源与时间表。
