# 开源组件集成方案（文献库 + 对话）

## 1. 项目定位
- 目标：在保持开源兼容（GPL-3.0 + MIT）的前提下，快速复用成熟界面，优化文献三栏体验与聊天界面。
- 库选择：
  - 文献库：Zotero Web Library（GPL-3.0）作为主框架，React Admin（MIT）辅助表格。
  - 对话界面：ChatGPT Next Web（MIT）组件已引入，后续继续沿用。

## 2. 集成方式
### 2.1 仓库管理
- 在 `libs/` 目录中保留 fork 的 `zotero-web-library/`（含 submodule），以便跟踪 upstream。
- 发行资产不再本地编译，而是使用官方构建包（详见 2.2）。
- React Admin 等 MIT 组件通过 npm 依赖维护。

### 2.2 静态资产
- 使用脚本 `scripts/build-zotero.sh`（或 `scripts/download-zotero-assets.sh`）直接下载 `https://www.zotero.org/static/web-library/` 提供的发行版资源：
  - 核心文件 `zotero-web-library.css/js`
  - 字体（`36AC02_*` 等）
  - 图标（`zotero-logo.svg`）
  - `xdelta3.wasm`
- 下载后存放于 `frontend/public/zotero/`，React 适配层通过 `/zotero/...` 引用。
- 如需锁定版本，可改用 GitHub Releases 中带有 `build/` 目录的压缩包。

### 2.3 React 适配
- 包裹组件位于 `frontend/src/components/library/zotero-adapter/`：
  - `useZoteroAssets` 负责加载发行版 CSS/JS。
  - `ZoteroCollectionTree`、`ZoteroItemsTable`、`ZoteroItemPane` 等封装与我们的 Zustand store 对接。
- 文献列表使用 React Admin DataGrid；详情与引用面板调用我们的 `literatureAPI`。
- PDF 预览后续引入 `react-pdf` 或官方 pdf-reader 构建包按需挂载。

## 3. 许可说明
- 项目需在 README 或 NOTICE 中声明使用了 Zotero Web Library 发行资产，并引用其 AGPL-3.0 许可；建议列出下载日期或 release 标签。
- 我们自定义的 React 适配层需保留原著作信息（可在文件头部或文档补充）并明确改动内容。
- 若后续打包发布，请附带 GPL 文档及下载脚本，确保使用者能重建相同资源。

## 4. 技术路线调整
1. 下载发行版 → 编写适配层 → 接入状态管理（已完成基础框架）。
2. 后续扩展 PDF 预览、批量操作等功能，必要时引用 `pdf-reader` 构建产物。
3. 移除历史的本地编译步骤，缩短环境准备时间。

## 5. 后续工作
- Stage 2 按照 “发行版 + 适配层” 路线继续开发。
- Stage 3 将自动建库、抽检 UI 联动文献界面。
- 定期使用脚本刷新发行资产（或固定 release），保持与 Zotero 官方版本同步。
