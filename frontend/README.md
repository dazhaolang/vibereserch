# 科研文献智能分析平台 - 前端

## 🚀 快速开始

### 1. 安装依赖
```bash
cd frontend
npm install
```

### 2. 启动后端服务
```bash
# 在项目根目录
cd ..
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 启动前端开发服务器
```bash
# 在frontend目录
npm run dev

# 或使用启动脚本
./start.sh
```

### 4. 访问系统
- 主页：http://localhost:3000
- 研究工作台：http://localhost:3000/workspace
- 文献库：http://localhost:3000/library
- 任务中心：http://localhost:3000/tasks

## 📦 核心功能

### 研究工作台 `/workspace`
- **三种研究模式**：
  - RAG模式：快速检索现有知识库
  - 深度研究：生成专属研究经验
  - 全自动模式：AI编排完整研究流程

- **智能交互**：
  - 5秒倒计时自动选择
  - AI推荐选项
  - 自定义输入支持

- **实时进度**：
  - WebSocket实时更新
  - 多阶段进度展示
  - 详细日志查看

### 文献管理
- PDF批量上传
- DOI批量导入
- Zotero文献库导入
- 文献列表管理
- 结构化数据查看

### 任务管理
- 实时任务进度
- 任务暂停/继续
- 成本统计
- 日志查看

## 🛠 技术栈

- **框架**：React 18 + TypeScript
- **UI组件**：Ant Design 5
- **状态管理**：Zustand
- **实时通信**：Socket.io
- **动画**：Framer Motion
- **构建工具**：Vite

## 📁 项目结构

```
frontend/
├── src/
│   ├── components/      # UI组件
│   │   ├── interaction/ # 智能交互组件
│   │   ├── workspace/   # 工作台组件
│   │   └── literature/  # 文献组件
│   ├── pages/          # 页面组件
│   ├── services/       # API和WebSocket服务
│   ├── stores/         # 状态管理
│   ├── hooks/          # 自定义Hooks
│   └── types/          # TypeScript类型
├── package.json
├── vite.config.ts
└── start.sh           # 启动脚本
```

## 🔧 开发命令

```bash
# 开发模式
npm run dev

# 构建生产版本
npm run build

# 预览生产版本
npm run preview

# 代码检查
npm run lint

# 格式化代码
npm run format
```

## 🌟 功能亮点

1. **智能问答输入**
   - Markdown支持
   - AI建议提示
   - 历史记录
   - 查询模板

2. **交互式选择卡片**
   - 5秒自动倒计时
   - 推荐选项高亮
   - 自定义输入
   - 平滑动画

3. **实时进度跟踪**
   - 多阶段展示
   - 预计剩余时间
   - 详细日志
   - 暂停/继续控制

4. **结果展示**
   - Markdown渲染
   - 参考文献列表
   - 置信度评分
   - 导出功能

## 🔍 调试

1. 打开浏览器开发者工具
2. 查看Console日志
3. 查看Network标签页的WebSocket连接
4. React Query Devtools（开发模式自动启用）

## 📝 注意事项

- 确保后端服务运行在 `http://localhost:8000`
- WebSocket连接需要后端支持
- 首次运行需要安装依赖
- 开发模式下热更新自动启用

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可证

MIT License