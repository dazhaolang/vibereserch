# 全栈测试操作指引 (VibResearch Platform)

本文档为测试团队提供完整的测试脚本执行流程、覆盖范围说明、日志归档要求，以及失败时的报告清单。

## 📋 测试覆盖范围总览

### 后端 API 测试覆盖
- **认证系统**: 登录、注册、用户资料管理、JWT Token验证
- **项目管理**: 项目创建、查询、统计、删除、权限控制
- **文献处理**: 文献方法、统计、用户库管理、处理流水线
- **任务系统**: 任务列表、概览、统计、性能指标、生命周期管理
- **监控指标**: 系统健康、端点统计、业务指标、性能监控
- **性能优化**: 状态监控、仪表盘、成本分析、优化建议
- **协作工作区**: 工作区创建、加入、注释、洞察、成员管理
- **集成功能**: Claude Code、智能助手、知识图谱、MCP协议
- **研究模式**: RAG检索、深度分析、自动化处理三态切换

### 前端 UI 测试覆盖
- **登录流程**: 表单交互、API调用验证、重定向、错误处理
- **项目工作流**: 前后端数据同步、UI状态更新、实时刷新
- **仪表盘**: 数据展示、交互响应、视觉验证、图表渲染
- **用户体验**: 响应式设计、可访问性、错误边界、加载状态

### 实时通信测试覆盖
- **WebSocket连接**: 建立、维持、消息收发、断线重连
- **实时推送**: 事件通知、状态同步、多用户协作
- **消息处理**: 消息格式验证、类型统计、延迟测量

### 模块化专项测试覆盖
- **协作工作区模块**: 工作区生命周期、成员权限、注释系统
- **性能洞察模块**: 项目自动管理、成本估算、性能建议
- **业务工作流**: 端到端用户旅程、核心业务场景

## 🔄 标准测试执行流程

### 环境准备阶段
```bash
# 1. 设置环境变量
export VIBERESEARCH_BASE_URL="http://localhost:8000"
export VIBERESEARCH_FRONTEND_URL="http://localhost:3000"
export VIBERESEARCH_TEST_EMAIL="test@example.com"
export VIBERESEARCH_TEST_PASSWORD="testpass123"

# 2. 初始化依赖
python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
cd frontend && npm install && npx playwright install chromium && cd ..

# 3. 启动依赖服务（可选）
docker compose up mysql redis elasticsearch -d

# 4. 验证服务状态
curl -f "$VIBERESEARCH_BASE_URL/health" || echo "后端服务未启动"
curl -f "$VIBERESEARCH_FRONTEND_URL" || echo "前端服务未启动"

# 5. 创建归档目录
mkdir -p artifacts/$(date +%Y-%m-%d)
```

### 测试执行阶段

#### 阶段 1: 后端核心测试 (优先级：高)

##### 1.1 后端工作流冒烟测试
```bash
python3 scripts/backend_workflow_smoke.py \
  --base-url "$VIBERESEARCH_BASE_URL" \
  --email "$VIBERESEARCH_TEST_EMAIL" \
  --password "$VIBERESEARCH_TEST_PASSWORD" \
  --output backend_workflow_results.json

# 期望结果: 100% PASS (14/14)
# 关键验证: 注册→登录→项目管理→性能监控→清理
```

##### 1.2 API 全量回归测试
```bash
python3 scripts/api_regression_suite.py \
  --base-url "$VIBERESEARCH_BASE_URL" \
  --email "$VIBERESEARCH_TEST_EMAIL" \
  --password "$VIBERESEARCH_TEST_PASSWORD" \
  --output api_regression_report.json

# 期望结果: >95% PASS (47+/48)
# 关键验证: 48个端点的状态码和响应格式
```

#### 阶段 2: 模块专项测试 (优先级：中)

##### 2.1 协作工作区模块测试
```bash
python3 scripts/collaboration_workflow_test.py \
  --base-url "$VIBERESEARCH_BASE_URL" \
  --email "$VIBERESEARCH_TEST_EMAIL" \
  --password "$VIBERESEARCH_TEST_PASSWORD" \
  --output collaboration_workflow_results.json

# 期望结果: 100% PASS (3/3)
# 关键验证: workspace_name字段、成员列表、工作区ID
```

##### 2.2 性能洞察模块测试
```bash
python3 scripts/performance_insights_test.py \
  --base-url "$VIBERESEARCH_BASE_URL" \
  --email "$VIBERESEARCH_TEST_EMAIL" \
  --password "$VIBERESEARCH_TEST_PASSWORD" \
  --output performance_insights_results.json

# 期望结果: 100% PASS (8/8)
# 关键验证: 项目自动创建/清理、成本估算、性能指标
```

#### 阶段 3: 实时通信测试 (优先级：中)

##### 3.1 WebSocket 稳定性测试
```bash
python3 scripts/ws_regression_suite.py \
  --base-url "$VIBERESEARCH_BASE_URL" \
  --email "$VIBERESEARCH_TEST_EMAIL" \
  --password "$VIBERESEARCH_TEST_PASSWORD" \
  --duration 30 \
  --output ws_messages.json

# 期望结果: 连接成功、消息接收正常
# 关键验证: 连接建立、消息类型统计、连接稳定性
```

#### 阶段 4: 前端 UI 测试 (优先级：高)

##### 4.1 登录流程验证
```bash
node scripts/frontend_login_flow.js

# 期望结果: 登录成功、重定向正常
# 生成工件: frontend_login_success.png (成功) 或 frontend_login_failure.png (失败)
# 关键验证: API调用状态200、dashboard内容检测
```

##### 4.2 项目工作流验证
```bash
node scripts/frontend_project_flow.js

# 期望结果: 项目创建并在UI中显示
# 生成工件: frontend_project_workflow.png (成功) 或 frontend_project_workflow_failure.png (失败)
# 关键验证: 前后端数据同步、项目列表更新
```

#### 阶段 5: 一键全栈测试 (可选)

##### 5.1 完整系统套件
```bash
./scripts/run_full_system_suite.sh

# 自动执行: pytest → API回归 → 前端lint/build → Playwright测试
# 生成完整的artifacts/system_tests/<timestamp>/报告
```

##### 5.2 自定义参数执行
```bash
# 自定义运行ID
RUN_ID=custom-id ./scripts/run_full_system_suite.sh

# 调整前端端口
FRONTEND_TEST_PORT=3100 ./scripts/run_full_system_suite.sh

# 远程API测试
VIBERESEARCH_BASE_URL=https://api.example.com ./scripts/run_full_system_suite.sh
```

## 📁 日志归档标准要求

### 标准归档目录结构
```
artifacts/YYYY-MM-DD/
├── backend_tests/
│   ├── backend_workflow_results.json      # 后端工作流测试结果
│   ├── api_regression_report.json         # API全量回归测试结果
│   ├── collaboration_workflow_results.json # 协作工作区模块结果
│   ├── performance_insights_results.json   # 性能洞察模块结果
│   └── ws_messages.json                   # WebSocket通信测试结果
├── frontend_tests/
│   ├── frontend_login_success.png         # 登录流程成功截图
│   ├── frontend_project_workflow.png      # 项目工作流截图
│   ├── frontend_login_failure.png         # 登录流程失败截图(如有)
│   ├── frontend_project_workflow_failure.png # 项目流程失败截图(如有)
│   └── frontend_test_logs.txt            # 前端测试终端完整日志
├── system_tests/
│   └── artifacts/system_tests/<timestamp>/ # 一键全栈测试完整报告
│       ├── backend/pytest.log            # 后端单元测试日志
│       ├── backend/backend_server.log     # 后端服务运行日志
│       ├── integration/api_regression.log # API回归测试执行日志
│       ├── integration/api_regression.json # API测试结构化结果
│       ├── frontend/lint.log              # 前端代码检查日志
│       ├── frontend/build.log             # 前端构建日志
│       ├── frontend/playwright.log        # Playwright测试日志
│       ├── frontend/test-results/console.log # 浏览器控制台日志
│       ├── frontend/test-results/page-errors.log # 页面错误日志
│       ├── frontend/playwright-report/    # HTML测试报告和截图
│       └── summary.log                   # 执行总结和状态汇总
├── reports/
│   ├── TEST_EXECUTION_SUMMARY.md          # 测试执行总结报告
│   ├── MODULE_TEST_VALIDATION_REPORT.md   # 模块测试验证报告
│   ├── FAILURE_ANALYSIS.md               # 失败分析报告(如有)
│   └── PERFORMANCE_METRICS.md            # 性能指标总结
└── metadata/
    ├── test_metadata.txt                  # 测试元数据和环境信息
    ├── execution_commands.log             # 执行的命令历史
    ├── terminal_outputs.log               # 完整终端输出记录
    └── environment_snapshot.json          # 测试时的环境状态快照
```

### 必备归档内容清单

#### 每次测试必须保存
1. **✅ JSON 测试报告**: 所有带 `--output` 参数生成的结构化结果文件
2. **✅ 终端输出日志**: 完整的 PASS/FAIL 信息、错误详情、执行时间
3. **✅ 截图文件**: 所有前端测试自动生成的 PNG 截图文件
4. **✅ 执行命令记录**: 实际运行的完整命令行和环境变量设置
5. **✅ 测试元数据**: 执行时间、环境信息、Git提交信息、执行者

#### 测试元数据记录脚本
```bash
# 在每次测试会话开始时执行
ARTIFACT_DIR="artifacts/$(date +%Y-%m-%d)"
mkdir -p "$ARTIFACT_DIR/metadata"

# 记录测试元数据
cat > "$ARTIFACT_DIR/metadata/test_metadata.txt" << EOF
测试执行时间: $(date)
测试执行者: $(whoami)
执行环境: $(uname -a)
Git提交哈希: $(git rev-parse HEAD)
Git分支: $(git branch --show-current)
Python版本: $(python3 --version)
Node版本: $(node --version)
Docker状态: $(docker ps --format "table {{.Names}}\t{{.Status}}" 2>/dev/null || echo "Docker不可用")
测试环境变量:
  VIBERESEARCH_BASE_URL=$VIBERESEARCH_BASE_URL
  VIBERESEARCH_FRONTEND_URL=$VIBERESEARCH_FRONTEND_URL
  VIBERESEARCH_TEST_EMAIL=$VIBERESEARCH_TEST_EMAIL
EOF

# 记录环境状态快照
curl -s "$VIBERESEARCH_BASE_URL/health" > "$ARTIFACT_DIR/metadata/health_snapshot.json" 2>/dev/null || echo '{"error":"backend_unavailable"}' > "$ARTIFACT_DIR/metadata/health_snapshot.json"
curl -s "$VIBERESEARCH_BASE_URL/info" > "$ARTIFACT_DIR/metadata/info_snapshot.json" 2>/dev/null || echo '{"error":"info_unavailable"}' > "$ARTIFACT_DIR/metadata/info_snapshot.json"
```

### 执行命令记录模板
```bash
# 开始记录会话
script -a "$ARTIFACT_DIR/metadata/terminal_outputs.log"

# 或者手动记录关键命令
echo "=== $(date) ===" >> "$ARTIFACT_DIR/metadata/execution_commands.log"
echo "python3 scripts/backend_workflow_smoke.py --base-url $VIBERESEARCH_BASE_URL ..." >> "$ARTIFACT_DIR/metadata/execution_commands.log"
```

## ⚠️ 失败时的报告清单

### 立即收集信息 (发现失败后5分钟内)

#### 1. 基本失败信息
- **失败脚本名称**: 具体的脚本文件名和失败步骤
- **执行完整命令**: 包含所有参数的命令行
- **失败时间**: 精确的失败时间戳
- **错误类型**: HTTP状态码、脚本退出码、异常类型
- **错误消息**: 完整的error_code、message和detail字段

#### 2. 环境状态快照收集
```bash
# 立即执行以下命令收集环境状态
FAILURE_DIR="$ARTIFACT_DIR/failure_analysis_$(date +%H%M%S)"
mkdir -p "$FAILURE_DIR"

# 服务状态检查
curl -s "$VIBERESEARCH_BASE_URL/health" > "$FAILURE_DIR/health_at_failure.json"
curl -s "$VIBERESEARCH_BASE_URL/status" > "$FAILURE_DIR/status_at_failure.json"
curl -I "$VIBERESEARCH_BASE_URL" > "$FAILURE_DIR/connectivity_test.txt"
curl -I "$VIBERESEARCH_FRONTEND_URL" >> "$FAILURE_DIR/connectivity_test.txt"

# 进程和端口状态
ps aux | grep -E "(uvicorn|npm|node)" > "$FAILURE_DIR/process_status.txt"
netstat -tuln | grep -E "(8000|3000)" > "$FAILURE_DIR/port_status.txt"
docker ps 2>/dev/null > "$FAILURE_DIR/docker_status.txt" || echo "Docker不可用" > "$FAILURE_DIR/docker_status.txt"

# 系统资源状态
df -h > "$FAILURE_DIR/disk_usage.txt"
free -h > "$FAILURE_DIR/memory_usage.txt"
uptime > "$FAILURE_DIR/system_load.txt"
```

#### 3. 特定类型失败的详细收集

##### API 测试失败 (422/404/500)
**必须附加收集**:
- 失败请求的完整 JSON payload
- `api_regression.json` 中对应的响应详情
- 同类型其他端点的测试状态对比
- 数据库连接状态 (如可访问)

**收集脚本**:
```bash
# API失败专项收集
echo "=== API失败详细信息 ===" > "$FAILURE_DIR/api_failure_details.txt"
echo "失败端点: [具体API路径]" >> "$FAILURE_DIR/api_failure_details.txt"
echo "HTTP状态码: [状态码]" >> "$FAILURE_DIR/api_failure_details.txt"
echo "请求payload:" >> "$FAILURE_DIR/api_failure_details.txt"
# 从脚本日志中提取实际请求内容
echo "响应详情:" >> "$FAILURE_DIR/api_failure_details.txt"
# 从JSON报告中提取完整响应
```

##### 前端测试失败 (超时/元素未找到)
**必须附加收集**:
- 失败时的完整页面截图
- 浏览器开发者工具控制台完整日志
- 页面HTML源码快照
- 网络请求瀑布图 (如可获取)

**收集脚本**:
```bash
# 前端失败专项收集 (手动执行Playwright调试)
npx playwright test --debug --headed  # 交互式调试模式
# 生成的trace文件和截图会自动保存到test-results/
cp frontend/test-results/* "$FAILURE_DIR/" 2>/dev/null
```

##### WebSocket 测试失败 (连接失败/消息异常)
**必须附加收集**:
- WebSocket连接建立过程的详细日志
- 消息收发的完整时序记录
- 服务器端WebSocket相关日志 (如可访问)

#### 4. 标准失败报告模板

```markdown
# 测试失败报告 - [脚本名称] - [日期时间]

## 💥 失败基本信息
- **失败时间**: YYYY-MM-DD HH:MM:SS
- **失败脚本**: scripts/[script_name]
- **执行命令**: [完整命令行]
- **失败步骤**: [具体步骤，如 workspace_create]
- **错误类型**: [HTTP状态码/脚本退出码/异常类型]

## 🔍 错误详情
- **HTTP状态码**: [如 422, 404, 500]
- **错误代码**: [如 VALIDATION_ERROR, HTTP_404]
- **错误消息**: [完整的message字段]
- **详细信息**: [detail字段内容]

### 完整响应体
```json
[粘贴完整的错误响应JSON]
```

## 🖥️ 环境状态
- **后端健康检查**: [/health端点响应状态]
- **前端可访问性**: [是否能正常访问frontend URL]
- **服务进程状态**: [uvicorn/npm进程是否运行]
- **端口占用情况**: [8000/3000端口状态]
- **Docker容器状态**: [相关容器运行状态]

## 🔄 复现步骤
1. [环境准备步骤]
2. [具体执行命令]
3. [失败现象描述]
4. [预期vs实际结果对比]

## 📊 相关测试状态
- **同批次其他测试**: [其他脚本执行状态]
- **历史对比**: [与上次成功执行的差异]
- **依赖服务状态**: [数据库/Redis/ES等状态]

## 💡 临时解决方案
[如有可行的临时绕过方法]

## 📋 附件清单
- [x] 失败时终端完整输出
- [x] 环境状态快照文件
- [x] 失败步骤的截图 (前端测试)
- [x] 相关配置文件内容
- [x] 错误日志文件片段

## 🏷️ 分类标签
- **优先级**: [高/中/低]
- **影响范围**: [登录/项目管理/性能/UI等]
- **失败类型**: [环境/代码/配置/网络等]
- **阻塞程度**: [完全阻塞/部分功能/不影响核心流程]
```

### 失败分析决策树

#### 环境相关失败
| 症状 | 可能原因 | 立即操作 | 升级路径 |
|------|----------|----------|----------|
| 401/403 错误 | Token过期/权限不足 | 重新创建测试用户 | 测试团队处理 |
| 404 错误 | 服务未启动/路由错误 | 检查服务状态，重启 | 测试团队处理 |
| 500 错误 | 服务器内部错误 | 收集服务器日志 | 研发团队介入 |
| 超时错误 | 网络/性能问题 | 增加timeout，检查负载 | 测试团队处理 |
| 前端白屏 | 前端服务/构建问题 | 重启前端服务 | 测试团队处理 |

#### 数据相关失败
| 症状 | 可能原因 | 立即操作 | 升级路径 |
|------|----------|----------|----------|
| 项目不存在 | 测试数据被清理 | 重新执行项目创建 | 测试团队处理 |
| 用户不存在 | 数据库重置 | 重新注册测试用户 | 测试团队处理 |
| 权限不足 | 用户角色配置 | 检查用户权限设置 | 研发团队介入 |
| 数据格式错误 | API变更 | 收集新旧格式对比 | 研发团队介入 |

#### 功能相关失败
| 症状 | 可能原因 | 立即操作 | 升级路径 |
|------|----------|----------|----------|
| 新功能404 | 接口未部署 | 确认功能分支合并 | 研发团队介入 |
| 字段缺失 | API响应格式变更 | 对比文档期望 | 研发团队介入 |
| UI元素不存在 | 前端变更 | 更新测试选择器 | 测试团队处理 |
| 性能显著降低 | 代码/数据问题 | 性能分析报告 | 研发团队介入 |

## 6. 手动补充验证（必要时）
自动化覆盖之外，建议在 staging 环境手动巡检：
1. **模型开关与降级策略**：在管理面板切换轻量/标准/深度模式，确认前端数据面板与任务排队行为同步更新。
2. **WebSocket / SSE**：若 Playwright 报警，使用 `scripts/test_websocket_final.py` 单独验证。
3. **大文献库流程**：调用 `scripts/test_integration.sh` 或 Celery worker 场景，确认长耗时任务没有阻塞。
4. **批量导入/导出**：依赖真实外部服务（如 Elasticsearch）的功能需在全量环境执行，并记录数据库/索引状态快照。

## 7. 验收与汇报
- **上线条件**：所有自动化步骤通过（退出码 0），Playwright 报告无失败，`api_regression.json` 中无 `FAIL/ERROR` 记录。
- **汇报模版**：
  1. 执行时间 & `RUN_ID`
  2. 关键脚本（pytest / api_regression / playwright）状态
  3. 失败数为 0 或列出失败清单
  4. 附 `summary.log` 与必要截图/日志
- **持续集成**：建议在 CI 中配置每日构建，使用同一脚本并保留 `artifacts/system_tests` 目录，实现可追溯的历史对比。

## 8. 扩展覆盖路线图
为应对后续版本及细节功能，自动化体系将按照「API 深度 → 前端旅程 → 场景联调」分阶段推进。所有新增脚本会落在既有框架上，执行入口保持不变。

### 8.1 后端 API 补强
- **分析/研究任务**：`scripts/api_regression_suite.py` 新增 `test_analysis_endpoints()`，覆盖 `/api/analysis/ask-question`、`/generate-experience`、`/generate-main-experience`、`/generate-ideas`，并自动记录生成的任务以便清理。
- **任务生命周期**：回归脚本会捕获由深度/自动模式产生的任务，并执行 `/api/task/{id}/cancel`，验证重放/取消路径可用。
- **计划中的补充**：
  - 文献上传与索引（预备使用临时文件 + SQLite 开关）
  - 协作团队增删改（需引入测试用团队成员）
  - 通知、会员升级、密码重置等用户设置接口

执行方式保持不变，仍通过 `./scripts/run_full_system_suite.sh` 调度；只需关注 `integration/api_regression.json` 的新增条目和潜在 `WARN` 记录。

### 8.2 前端旅程扩展
- **导航校验**：Playwright `main feature navigation test` 已覆盖「仪表盘 / 研究工作台 / 文献库 / 任务中心」四个主菜单，并基于页面标题验证加载成功。
- **工作台空态检测**：`workspace guidance state test` 确认无项目时的引导提示，确保提示消息不会消失。
- **计划中的旅程**：
  1. 研究工作台：自动模式发起查询 → 任务状态更新 → 结果面板快照。
  2. 文献库：导入示例 PDF、筛选、切换卡片/表格视图。
  3. 任务中心：取消/重试按钮可用性、抽屉详情展示。
  4. 主题切换与通知：验证光/暗模式及消息提醒。

> Playwright 仍通过 `npm run lint && npm run build && npx playwright test` 运行。若需对比多轮结果，可设置 `RUN_ID=... PLAYWRIGHT_RUN_ID=... ./scripts/run_full_system_suite.sh` 保持产物目录一致。

### 8.3 手动验证补充
- 协作工作台、MCP 工具链、WebSocket 实时事件仍需人工巡检，待稳定数据与 Mock 框架就绪后再纳入自动化。
- 所有新增自动化脚本均会在 `REGRESSION_PROOF.md` 中跟踪「已覆盖/待覆盖」状态，便于 QA 签字。

---
如需扩展测试范围，可在 `scripts/run_full_system_suite.sh` 中新增步骤，或扩充 `scripts/api_regression_suite.py` 的端点列表；请同步更新本指南，确保测试团队掌握最新覆盖面。
