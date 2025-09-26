# 深度研究平台愿景对照与前端缺口报告

## 1. 愿景对照（已实现能力）
- **三模式研究入口**：后端暴露单一入口支持 `rag/deep/auto` 三种模式，并交由编排器分流（`app/api/research/routes.py:15`，`app/services/research_orchestrator.py:16`）。
- **原子化搜索建库流水线**：`SearchAndBuildLibraryService` 覆盖搜索 → 筛选 → PDF 下载 → Markdown/结构化提取 → 入库的全流程，并提供进度回调（`app/services/search_and_build_library_service.py:89`）。
- **Research Rabbit + MinerU 集成**：检索端调用 ResearchRabbit API（`app/services/research_rabbit_client.py:1`），PDF 处理通过 MinerU 转 Markdown（`app/services/pdf_processor.py:16`），满足“搜索 + 清洁化整理”的愿景。
- **清洁化结构组织**：轻结构化处理服务根据领域模板切分文献并生成提取提示词（`app/services/lightweight_structuring_service.py:21`）。
- **经验迭代引擎**：增强版经验引擎结合可靠性排序、渐进式批次策略与动态停止条件，实现多轮经验书迭代（`app/services/experience_engine.py:71`）。
- **MCP 工具打包**：`collect_literature/process_literature/generate_experience` 等以原子粒度注册供 Claude/CodeX/Gemini 调用（`app/services/mcp_tool_setup.py:40`）。
- **后台任务体系**：所有重任务均落在 Celery 队列，封装成任务中心可追踪的进度事件（`app/tasks/celery_tasks.py:20`）。
- **智能澄清 + 5 秒默认选项**：交互 API 与前端倒计时卡片协同，实现 Skywork 式澄清体验（`app/api/intelligent_interaction.py:35`，`frontend/src/components/interaction/InteractionCards.tsx:26`）。
- **多渠道建库入口**：后端支持 PDF/DOI/Zotero 上传导入（`app/api/literature.py:761`），前端提供统一上传模态框（`frontend/src/components/literature/LiteratureUploadModal.tsx:32`）。

## 2. 愿景差距与隐含矛盾
1. **主经验预生成缺位**：虽然实现了 `create_main_experiences` 与增量更新（`app/services/experience_engine.py:635`），但目前没有任何任务或触发器调用，RAG 依赖的“主经验库”只在运行时按需生成，违背“提前迭代主经验”愿景。
2. **前端模式体验不一致**：
   - 工作台仍固定项目 ID（`frontend/src/pages/workspace/ResearchWorkspace.tsx:18`），模式切换后也未反映差异化控制。
   - 深度研究页的拆解数据完全是本地 mock（`frontend/src/pages/deep/deep-research-page.tsx:72`），与“AI 拆解问题”愿景不符。
   - 全自动页面调用真实接口，但同样写死项目 ID，且编排与进度展示为静态示意（`frontend/src/pages/auto/auto-research-page.tsx:221`、`frontend/src/pages/auto/auto-research-page.tsx:295`）。
   - 旧版 `Rag/Deep/AutoPanel` 仍直接渲染原始 JSON，无真实 UI（`frontend/src/components/research/rag-panel.tsx:26`、`frontend/src/components/research/deep-panel.tsx:29`、`frontend/src/components/research/auto-panel.tsx:36`）。
3. **任务链状态回流不足**：后端触发 `auto_pipeline` 会串行激活多个 Task，但前端只通过 WebSocket 接受零散事件，没有把编排计划与任务状态串起来展示（`app/services/research_orchestrator.py:101` 对 plan 做了返回，前端仅 `JSON.stringify` 显示）。
4. **查询上下文选择未落地**：工作台输入允许附加文献 ID，但组件内仍保留“TODO 打开文献选择器”的占位逻辑（`frontend/src/components/workspace/SmartQueryInput.tsx:255`），无法让用户在 RAG 模式手动指定上下文。
5. **模式边界缺乏后端硬约束**：深度模式通过 `trigger_experience_task` 运作（`app/services/research_orchestrator.py:45`），但缺少防扩库条件（例如强制禁用 `collect_first`），需要在 Task 配置层面显式约束。
6. ✅ **Skywork 式默认继续已后端化**：澄清卡片生成时会调度 Celery 任务 `auto_select_clarification_card`，到时自动提交推荐选项，即便前端断线也能继续流程。

## 3. 改进计划（优先级从高到低）

### 3.1 后端
1. **主经验自动生成管线**（高）
   - 在搜索建库任务成功后触发 `create_main_experiences`（Celery 链或 `TaskOrchestrator` 钩子）。
   - 新建任务类型 `main_experience_generation`，落盘进度事件，供前端显示。
   - 为 RAG 查询加缓存命中逻辑：若主经验缺失则提示用户先运行经验生成。
2. **问题拆解/模式推荐 API**（高）
   - 提供 `POST /research/analysis`，复用 `IntelligentInteractionEngine` 拉取拆解结果，替换前端 mock。
   - 返回推荐模式、子问题、预估资源，用于前端引导。
3. **全自动模式边界强化**（中）
   - 在 `run_auto` 中根据配置禁用或启用 `collect_first`，确保深度模式不会扩库。
   - 对 `auto_config` 补充白名单校验，避免 agent 注入未授权工具。
4. **交互超时后端兜底**（已完成）
   - 澄清卡片生成时即时安排 `auto_select_clarification_card` Celery 任务，5 秒后自动提交推荐选项并广播事件。
5. **任务-计划结构化响应**（中）
   - 为 `run_auto` 结果补充扁平化字段（阶段数组、当前阶段索引）以便前端直接绑定。

### 3.2 前端
1. **统一项目与模式上下文**（高）
   - 实现项目选择器，将 `projectId` 传入所有研究请求（工作台、Landing、Auto/Deep 页面）。
   - 将 `useAppStore` 的 session 信息同步到 `useResearchStore`，避免双状态源。
2. **深度/全自动页面联通真实 API**（高）
   - 用新建的拆解接口替换 mock，展示真实子问题与推荐路径。
   - 根据 `agent_plan` 渲染阶段式进度时间线；监听返回的任务列表映射到 `ProgressPanel`。
3. **RAG 结果展示组件化**（高）
   - 把 `ResearchResultPanel` 用于 `RagPanel` 等旧 UI，移除 JSON 输出。
   - 增加主经验引用、文献引用 tabs，为用户提供溯源。
4. **上下文文献选择器**（中）
   - 在 `SmartQueryInput` 中实现文献搜索 + 多选，将选中 ID 传给 `submitQuery`。
5. **模式差异化控制面板**（中）
   - 深度模式：暴露迭代轮次、批次大小、结构化模板等高级参数。
   - 全自动模式：允许切换 agent、是否先采集、并发度等。
6. **任务中心联动**（中）
   - 订阅 `research_result` 后自动把完成的结果绑到对应任务，提供“跳转到结果”按钮。

### 3.3 运维与体验
- **进度通知统一**：整理 WebSocket 事件结构（类型字段 + payload），前端通过类型表驱动组件。
- **错误兜底**：所有研究模式返回补充 `support_actions` 提示下一步（例如触发建库任务）。

## 4. 前端未完成功能清单
| 区域 | 文件 | 当前状态 | 待补充功能 |
| --- | --- | --- | --- |
| 研究工作台 | `frontend/src/pages/workspace/ResearchWorkspace.tsx:17` | 项目 ID 固定为 1 | 引入项目选择器、支持 session 恢复 |
| 智能输入 | `frontend/src/components/workspace/SmartQueryInput.tsx:255` | 文献上下文入口 TODO | 打开文献选择器、支持多选/清除 |
| 深度研究页 | `frontend/src/pages/deep/deep-research-page.tsx:72` | 拆解/迭代采用 mock | 接入真实拆解 API、显示真实迭代进度、允许参数提交 |
| 全自动模式 | `frontend/src/pages/auto/auto-research-page.tsx:221` & `:295` | 静态时间轴 + 固定项目 ID | 绑定任务/阶段数据、项目选择、展示 `agent_plan` 结构化内容 |
| RAG/Deep/Auto Panels | `frontend/src/components/research/*.tsx` | 仅输出 JSON | 复用 `ResearchResultPanel`，加入分页和引用视图 |
| 任务进度 | `frontend/src/pages/workspace/ResearchWorkspace.tsx:138` | 多任务叠加但无分组 | 合并同类任务、显示阶段详情与失败重试入口 |
| 交互澄清 | `frontend/src/stores/research.store.ts:281` | 后端 Celery 已自动兜底超时 | 前端聚焦展示与手动交互，无需再实现倒计时逻辑 |
| 模式仪表板 | `frontend/src/pages/dashboard` (多组件) | 仅展示静态卡片 | 接入统计 API，突出主经验/任务概览 |

---
本报告可作为对齐愿景、排定迭代计划的基础素材，优先处理“主经验预生成”与“模式前端落地”两大短板，即可让实际体验与最初设想保持一致。
