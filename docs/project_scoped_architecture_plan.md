# 项目级控制台重构方案

## 1. 背景与目标
- 当前主控制台既展示全局信息，又在导航中直接暴露「文献库 / 任务中心」等页面，导致项目上下文混乱。
- 用户期望：主控制台仅概览全部项目；文献、任务、自动化流程必须在选定项目后才可访问，并且这些资源严格属于某一项目。
- 本轮重构目标：
  1. 建立清晰的双层导航结构（全局视角 / 项目视角）。
  2. 在前端强制所有文献、任务、会话等操作绑定选定项目。
  3. 后端 API 与数据模型做对应权限与作用域校验，确保跨项目访问被拒绝。

## 2. 设计原则
- **项目优先**：除登录、账户、全局概览外，所有工作流都以 `project_id` 为前提。
- **显式上下文**：URL、导航、标题、接口都必须显式包含项目标识，前端状态存储中也要同步维护。
- **最小割裂**：保留现有模块能力，但迁移到项目内路由下；通过网格/抽屉复用现有组件。
- **渐进式迁移**：前端、后端同步拆分，但可按功能模块（文献 → 任务 → AI 控制台）逐步上线。

## 3. 前端架构调整
### 3.1 路由与导航
- 顶层布局拆分为两个 Shell：
  - `GlobalShell (/)`：包含「项目总览」`/projects`、数据面板 `/dashboard`（可选）、`/profile`、`/settings`。
  - `ProjectShell (/projects/:projectId)`：内部使用次级侧边栏，提供 `overview / library / tasks / automation / settings` 等二级菜单。
- 调整路由表：
  ```tsx
  createBrowserRouter([
    {
      element: <GlobalShell />,
      children: [
        { index: true, element: <Navigate to="/projects" replace /> },
        { path: 'projects', element: <ProjectDirectory /> },
        { path: 'dashboard', element: <PortfolioDashboard /> },
        { path: 'profile', element: <PersonalCenterPage /> },
        { path: 'settings', element: <GlobalSettingsPage /> }
      ]
    },
    {
      path: '/projects/:projectId',
      element: <ProjectShell />,
      children: [
        { index: true, element: <Navigate to="overview" replace /> },
        { path: 'overview', element: <ProjectOverviewPage /> },
        { path: 'library', element: <ProjectLibraryPage /> },
        { path: 'tasks', element: <ProjectTasksPage /> },
        { path: 'automation', element: <ProjectAutomationPage /> },
        { path: 'settings', element: <ProjectSettingsPage /> }
      ]
    }
  ])
  ```
- `AppLayout` 根据当前 Shell 渲染不同的侧边栏菜单：全局模式仅显示全局功能，项目模式下主栏显示项目名称 + 二级菜单。

### 3.2 状态管理
- 新增 `ProjectScopeProvider`（React context）：封装 `currentProject`、`projectSummary`、`refreshProject()` 等。
- `useAppStore` 精简为全局偏好与项目缓存：
  - `activeProjectId` 改为只存储 ID。
  - 仅在 `ProjectShell` 挂载时加载项目详情并注入到 context。
- 当 URL 离开 `/projects/:projectId` 时自动清理项目上下文；进入项目页会触发一次 `GET /projects/:id/summary`。

### 3.3 页面与组件
- **全局视角**：
  - `/projects` ⇒ 全量项目列表（卡片 + 状态统计 + 快捷入口）。
  - `/dashboard` ⇒ 聚合统计（项目数量、上次活动、运行中的任务数等）。
- **项目视角**（在 ProjectShell 内）
  - `overview` ⇒ 当前项目关键指标、最近任务、top 文献。
  - `library` ⇒ 迁移现有 `LibraryPage` 功能，默认显示项目文献；保留抽屉查看元数据。
  - `tasks` ⇒ 任务面板与工作流看板。
  - `automation` ⇒ 自动研究/Agent 相关页面（原 `ResearchWorkspace`、`AutoResearch`）。
  - `settings` ⇒ 项目元数据、成员、配额。
- 重构侧边栏：
  - GlobalShell：`项目中心`、`全局概览`、`个人中心`、`系统设置`。
  - ProjectShell：`项目概览`、`文献库`、`任务中心`、`自动化`、`项目设置`。
  - 响应式时主内容宽度与侧栏联动（沿用当前改进）。

### 3.4 交互流程
1. 登录 → 默认跳转 `/projects`。
2. 用户在项目列表点击项目 → 跳转 `/projects/:id/overview` 并初始化 `ProjectScope`。
3. 访问文献/任务页面时，所有 API 请求自动带上 `projectId`；如果 context 缺失则重定向回 `/projects`。
4. 切换项目 → 通过顶栏「项目切换器」弹窗，选择后重定向新的项目路径。

## 4. 后端改动概览
### 4.1 API 命名与作用域
- 按资源重新组织路由：
  - `app/api/project_router.py` ⇒ 持有 `/projects/{project_id}` 下的子路由。
  - `app/api/project/literature.py`、`app/api/project/tasks.py` 等。
- 所有文献、任务、自动研究接口新增/强化 `project_id` 路径参数，并在依赖项中校验 `project.owner_id == current_user.id`。
- 现有 `/library`、`/tasks` 类接口迁入 `/projects/{project_id}/...`；提供向后兼容的临时重定向（2-3 个版本内移除）。

### 4.2 数据访问层
- `app/services/*` 中涉及文献/任务的方法统一增加 `project_id` 参数。
- 为高频查询写仓储方法：
  - `LiteratureRepository.list_by_project(project_id, filters)`
  - `TaskService.list_by_project(project_id, status)`
  - `ResearchWorkspaceService.start_run(project_id, payload)`
- 新增 `ProjectSummaryService`：聚合项目指标（文献数、任务成功率、最近活动时间）。

### 4.3 数据模型
- 现有模型大多已有 `project_id` 字段；需检查以下模型补充：
  - `app/models/task.py`：确认所有任务类型均持有 `project_id` 且非空。
  - `app/models/session.py`（如存在）确保绑定项目。
- 为性能添加索引：
  - `CREATE INDEX idx_literature_project_status ON literature (project_id, status)`
  - `CREATE INDEX idx_tasks_project_type ON tasks (project_id, task_type)`

### 4.4 权限与安全
- 在 `get_current_project` 依赖中统一处理：
  ```python
  def get_project_or_404(project_id: int, current_user: User, db: Session) -> Project:
      project = db.query(Project).filter(Project.id == project_id, Project.owner_id == current_user.id).first()
      if not project:
          raise HTTPException(status_code=404, detail="项目不存在或无权限")
      return project
  ```
- 对外暴露的共享链接（若有）需增加 project scope 校验。

### 4.5 聚合接口
- 新增：`GET /projects/summary` 返回卡片列表（项目状态、文献/任务统计）。
- 新增：`GET /projects/{project_id}/insights` 为项目概览页面提供图表数据。

## 5. 数据迁移与兼容
1. **数据审计**：排查 Literatur/Task 等表中 `project_id IS NULL` 的记录，生成报表。
2. **迁移脚本**：
   - 若存在公共文献，先创建“全局项目 (Global Library)”并通知用户手动归档，或暂作软删除。
   - 任务/日志同理。
3. **API 兼容层**：旧前端在过渡期访问 `/library` 时返回 410 或附带引导信息。

## 6. 迭代计划（建议 3 个冲刺）
1. **Sprint 1**：
   - 完成路由/布局拆分，交付新的 `GlobalShell` 与 `ProjectShell`，同时新增项目概览页骨架。
   - 后端补齐 `GET /projects/{id}/summary`。
2. **Sprint 2**：
   - 迁移文献库与任务页面到项目作用域；重构对应 API。
   - 开发数据迁移脚本，完成历史数据映射。
3. **Sprint 3**：
   - 迁移自动研究/AI 工作台至项目内。
   - 完成自测、文档更新、监控与告警调优。

## 7. 测试策略
- 前端 E2E：编写 Playwright 场景覆盖“选择项目 → 浏览文献 → 发起任务 → 返回全局”的全链路。
- 后端：新增项目作用域的单元测试 & API 集成测试，确保跨用户访问被拒绝。
- 数据迁移：在预发布环境跑全量回放，核对项目统计与原数据一致。

## 8. 风险与缓解
- **历史数据缺失 project_id**：需要运营参与确认归属；提供脚本与校验表。
- **用户书签失效**：提供临时重定向及 UI 提示。
- **性能回退**：提前在 Staging 做压测，观察项目级列表阻塞情况。

## 9. 上线与回滚
- 上线步骤：
  1. 部署后端新版本，启用 project-scoped API。
  2. 执行数据迁移脚本，生成校验报告。
  3. 部署前端新路由，灰度验证。
- 回滚策略：保留旧 API 路由文件备份以及 feature flag，如果需要可让前端回退到旧构建。

