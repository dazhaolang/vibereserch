# Stage 0 — 需求冻结与信息架构基线

## 目标
- 锁定“Perplexity 式研究工作台”重构的功能范围、主流程和体验原则，形成后续设计与开发的唯一参考。
- 输出低保真线框说明、核心状态机与界面信息架构，供设计与前端 Stage 1 实现使用。
- 列出需要的接口支持与潜在风险，避免 Stage 1 才发现需求缺口。

## 方法与产出
- 与业务方/研发确认 Scope，形成“包含 / 排除”清单。
- 以用户任务为驱动整理主流程：选择文献库、切换模式、自动建库、文献管理、对话调度。
- 用文字+结构图描述 IA；定义关键状态机（模式切换、文献库可用性、建库流水线）。
- 明确设计交付物：线框稿、组件规格、交互稿、动效需求、度量指标基线。

## Scope 定义
### In Scope
- 全新的主界面 Shell（左侧纵向导航 + 顶部模式卡片 + 对话区 + 辅助面板）。
- 文献库入口体验：空状态引导、库概览、库详情（含 Zotero 风格三栏布局）、懒加载 PDF。
- 新建/自动构建文献库向导：AI 主题确认、ResearchRabbit 搜索、200 篇抽检策略、进度/暂停/终止交互。
- 多模式对话：RAG、深度经验增强共享对话流；全自动模式独立流程。
- 文献库合并提醒与备份切换提示。
- 前端与后端的上下文绑定规范（用户 ID、project/library ID、任务 ID）。

### Out of Scope（Stage 0 ~ Stage 1）
- 视觉主题深度定制（颜色、插画、品牌元素），暂用现有 dark theme 指南。
- 新增模型推理能力或后端核心算法改造；仅重新编排已有 API。
- 移动端适配，当前专注桌面视图。
- 完整 i18n 方案（记录需求，后续阶段处理）。

## 用户旅程
1. **登录后首次进入**：检测是否存在可用文献库；若无，强制弹窗 -> 跳转库概览 -> 新建向导。
2. **常规研究**：从侧边栏选择“新研究”-> 顶部选择模式 -> 输入问题 -> 查看对话流，必要时切换 RAG/深度模式。
3. **切换文献库**：左上角库切换器 -> 选择已构建库 -> 主界面刷新引用上下文；若库构建中则提示只读。
4. **自动建库**：在文献库概览点击“新建”或在全自动模式触发 -> 与 AI 确认主题 -> ResearchRabbit 搜索 -> 进度监控 -> 完成/提前停止。
5. **合并与回滚**：用户保存或退出库向导 -> 后台合并 -> 前端显示“处理中，沿用旧库” banner -> 任务完成后提醒可切换新版本。

## 信息架构
```
Root
├─ Conversation Workspace (/research)
│  ├─ Mode Cards (RAG | Deep Experience | Auto Pipeline)
│  ├─ Chat Timeline (messages, citations, tool events)
│  ├─ Context Sidebar (active library, retrieved docs, tasks banner)
│  └─ Input Composer (mode actions, citation insert, uploads)
├─ Library Overview (/library/overview)
│  ├─ Library Cards (name, size, status, % progress, updated_at)
│  ├─ Backup/Version badges
│  └─ CTA: Create New Library
├─ Library Detail (/library/:id)
│  ├─ Collections/Tags tree (left)
│  ├─ Literature Table w/ virtualized rows (center)
│  ├─ Inspector (metadata, citations, notes, lazy PDF) (right)
│  └─ Toolbar (filters, batch actions, sync status)
├─ Auto Build Wizard (/library/new)
│  ├─ Step 1: Theme & constraints (chat w/ AI)
│  ├─ Step 2: Sources & limits (manual overrides, upload/DOI)
│  ├─ Step 3: Progress dashboard (timeline, checkpoints, abort)
│  └─ Step 4: Summary & merge options
└─ Advanced Settings (/settings/advanced)
   ├─ Model defaults (per mode)
   ├─ ResearchRabbit credentials
   ├─ Elasticsearch index management
```

## 状态机定义
### 对话模式状态机
- `RAG_ACTIVE` ↔ `DEEP_ACTIVE`：用户点击模式卡切换；保留对话上下文，向后台附带 `mode` 标识。
- `AUTO_PIPELINE`：单独入口/会话，启动后锁定模式；退出返回 RAG。
- 约束：当自动模式运行时，禁止并行 RAG/深度会话，需提示“完成后返回”。

### 文献库可用性状态
- `UNSELECTED`：无库或未选择 -> 触发库选择器；若用户取消则停留。
- `SELECTED_READY`：库已加载 -> 对话与检索开放。
- `BUILDING`：后台构建中 -> 样式标记 + 限制写操作；可读取旧库。
- `MERGING`：新旧库合并 -> 顶部 banner 提示，仅可读取旧版本。
- `UPDATING_FAILED`：合并失败 -> 提供重试/报告按钮。
- 转移：库构建完成 -> `MERGING` -> `SELECTED_READY`。

### 自动建库流程
- `THEME_DISCOVERY`（AI 澄清主题） -> `SOURCE_SELECTION`（确定来源/阈值） -> `FETCHING`（调用 ResearchRabbit） -> `CHECKPOINT_REVIEW`（每 200 篇抽检） -> `FINALIZING`（索引&结构化） -> `MERGE_READY`。
- 用户可在 `CHECKPOINT_REVIEW` 发出“提前停止” -> 进入 `FINALIZING` 并标记已截断。
- 若 ResearchRabbit 超限或异常 -> `PAUSED_NEEDS_INPUT` -> 弹窗要求用户调整关键词或降级策略。

## 设计交付要求
- **线框稿**：5 套关键界面（对话页、库概览、库详情、建库向导、无库弹窗），含注释说明布局/组件关系。
- **组件规格**：模式卡片、库卡片、进度条、懒加载 PDF 占位符、对话消息块（含引用标签、工具事件）。
- **状态图**：导出上述状态机为 Figma flow 或 Mermaid，提供 JSON/截图归档。
- **交互说明**：
  - 模式切换过渡与禁用态。
  - 文献卡 hover/选中行为。
  - 建库进度中的抽检提示、停止确认。
- **数据绑定文档**：说明每个界面需要的 API 字段（project stats、task progress、conversation session、library version）。
- **验收基线**：列出 Stage 1 结束时的可点击原型要求（Figma 或代码原型）。

## 研究与技术校验
- **现有 API**：`/api/literature`, `/api/project`, `/api/tasks`, `/api/mcp`，确认字段满足概览卡片展示；如缺少进度、备份标识，Stage 1 需同步接口调整。
- **新接口需求**：
  - `/api/library/overview`（汇总状态）
  - `/api/library/build/{id}/checkpoints`（抽检结果）
  - `/api/library/merge-status/{id}`（迁移状态）
- **性能约束**：虚拟滚动列表目标 < 200ms 首屏渲染，懒加载 PDF 需按需加载组件并使用 IntersectionObserver。
- **安全/权限**：所有 API 绑定 `owner_id` 与 `project_id` 校验；库切换必须刷新会话 token/headers 中的 project 上下文。

## 风险 & 未决事项
- 设计资源排期：确认 UI/UX 是否可在 1 周内交付线框；若无专职设计，需确定谁产出线框。
- ResearchRabbit API 配额：需获取准确速率限制；抽检策略可能增大调用次数。
- Elasticsearch 索引策略：合并期间的只读/双写方案需后端确认，避免检索断档。
- i18n：中文/英文文案是否共用，若 Stage 1 即需中英文切换则需额外设计。
- 模式体验：深度经验增强具体差异需业务确认（例如更多思维链、引用格式）。

## 下一步（Stage 1 前准备）
- 约谈设计/产品确认以上 Scope 与状态机；拉通后端确认新增接口可行性与交付时间。
- 输出线框与交互稿后，再将组件拆解成前端任务，并生成 Storybook/设计 token 需求。
- 建立项目看板（例如 Linear/Jira）将 Stage 1 backlog 拆为具体 issue。
