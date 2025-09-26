# Stage 2 — 文献库三栏视图集成计划

（原有内容已省略，下方新增开源集成策略）

## 开源集成策略
我们改为直接基于开源仓库二次开发，优先选择 **Zotero Web Library**（GPL-3.0）作为主框架，辅以 MIT 许可的辅助库：

### 目标仓库与角色
| 仓库 | 许可 | 角色 | 使用方式 |
| ---- | ---- | ---- | ---- |
| [Zotero Web Library](https://github.com/zotero/web-library) | GPL-3.0 | 主三栏布局、集合树、条目详情、PDF 预览 | fork 仓库至 `libs/zotero-web-library`，保留 LESS/CSS 和模板结构；交互改写为 React 包裹层 |
| [React Admin](https://github.com/marmelab/react-admin) | MIT | 数据表格、虚拟滚动 | 在项目中安装，替换原 Backbone 表格逻辑 |
| [react-pdf](https://github.com/wojtekmaj/react-pdf) | MIT | PDF 预览组件 | 懒加载 PDF 面板 |
| [ChatGPT Next Web](https://github.com/Yidadaa/ChatGPT-Next-Web) | MIT | 对话界面（已引入） | 保持现有适配 |

### 引入策略
1. **Zotero Fork**：在 `libs/zotero-web-library` 子目录存放 fork 代码；保留原 CSS/资源，逐步用 React 组件重写核心视图。
2. **打包脚本**：添加 `scripts/build-zotero.sh` 将 LESS 编译为 CSS，方便我们在主 app 中引入。
3. **React 适配层**：在 `frontend/src/components/library/zotero-adapter/` 编写包装组件：
   - `ZoteroCollectionTree`：利用原模板 + minimal DOM，事件转发给我们的 store。
   - `ZoteroItemTable`：由 React Admin DataGrid 替换。
   - `ZoteroItemPane`：复用 CSS + 自定义 React 结构。
4. **GPL 合规**：
   - 项目根目录新增 `LICENSE`（GPL-3.0 改写）或 `NOTICE` 说明组件来源。
   - 文档中列出派生细节（本文件、README、贡献指南）。

### 实施路径调整
- **阶段 2.1（本周）**：完成 fork、子模块或 git subtree 引入；跑通原 web-library 的 build，并确认 CSS 在我们项目中可用。
- **阶段 2.2**：将我们已有的 Zustand store 与 React Admin 表格组合，替换 Zotero 的 item table，同时保证 GPL 代码与 MIT 代码隔离清晰。
- **阶段 2.3**：改造集合树、详情面板、PDF 预览；逐步删去原 Backbone 依赖。
- **阶段 2.4**：完成批量操作、标签管理、拖拽等高阶功能，对照原 Zotero 行为做验收。

