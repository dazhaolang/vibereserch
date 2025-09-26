# 测试团队执行指引（JWT 修复 & 文献接口修复后）

本指引覆盖后端 JWT 认证修复与文献查询修复后的完整回归测试流程。所有命令默认使用 `http://154.12.50.153:8000`，请在执行前确保后端已完成数据库迁移 `alembic upgrade head`，并根据需要配置 `.env` 中的 `JWT_SECRET_KEY_FALLBACKS`（如果仍需兼容旧令牌）。

---

## 1. 环境准备

1. **重启后端服务**（确保最新代码和配置生效）。
2. **执行数据库迁移**：
   ```bash
   alembic upgrade head
   ```
   若迁移失败，请记录错误并反馈开发。
3. **准备测试账号**：建议使用新注册账号，避免旧令牌干扰结果。

---

## 2. JWT 认证回归（测试计划 9.1）

1. **获取访问令牌**
   ```bash
   curl -X POST 'http://154.12.50.153:8000/api/auth/login' \
     -H 'Content-Type: application/json' \
     -d '{"email": "<测试账号>", "password": "<密码>"}'
   ```
   - **通过条件**：HTTP 200，响应体含 `access_token`、`token_type: bearer`。

2. **验证当前用户信息**
   ```bash
   curl -X GET 'http://154.12.50.153:8000/api/user/profile' \
     -H 'Authorization: Bearer <token>'
   ```
   - **通过条件**：HTTP 200，返回字段包含 `id/email/username/membership`。

若出现 401/403，请确认迁移是否执行、密钥是否一致、后端是否重启。

---

## 3. 文献流程回归（测试计划 9.2 ~ 9.3）

1. **创建空项目**
   ```bash
   curl -X POST 'http://154.12.50.153:8000/api/project/create-empty' \
     -H 'Authorization: Bearer <token>' \
     -H 'Content-Type: application/json' \
     -d '{"name": "API 测试项目", "description": "自动化测试"}'
   ```
   - **通过条件**：HTTP 200；响应包含 `id/name/status`。

2. **列出项目确认新建成功**
   ```bash
   curl -X GET 'http://154.12.50.153:8000/api/project/list' \
     -H 'Authorization: Bearer <token>'
   ```
   - **通过条件**：HTTP 200；列表中有“API 测试项目”。

3. **上传 PDF 文献（步骤 9.3.1）**
   ```bash
   curl -X POST 'http://154.12.50.153:8000/api/literature/upload' \
     -H 'Authorization: Bearer <token>' \
     -F 'file=@sample.pdf' \
     -F 'project_id=<项目ID>'
   ```
   - **通过条件**：HTTP 200；响应 `success: true`，返回 `literature_id`。

4. **项目文献查询（关键回归点 9.3.4）**
   ```bash
   curl -X GET 'http://154.12.50.153:8000/api/literature?project_id=<项目ID>&page=1&size=20' \
     -H 'Authorization: Bearer <token>'
   ```
   - **通过条件**：HTTP 200；`items` 数组包含步骤 3 上传的文献。
   - 若返回空数组，请确认前一步是否成功；若响应为 500，请立即记录并反馈。

5. **（可选）AI 搜索导入与批量写入**
   - 执行 `POST /api/literature/ai-search` 和 `POST /api/literature/project/<id>/batch-add`。
   - 再次调用查询接口，确认新导入的文献可被检索到。

---

## 4. 后续接口回归（测试计划 9.4 ~ 9.10）

在文献查询通过后，继续执行剩余步骤：

1. **RAG 模式**：`POST /api/research/query`，`mode = "rag"`。
2. **深度模式**：`POST /api/research/analysis`，随后 `POST /api/research/query`（`mode = "deep"`）。
3. **自动模式 + 智能澄清**：依照计划 9.6 顺序执行互动、选项提交、自动任务触发。
4. **任务中心与实时进度**：`GET /api/task`、`GET /api/task/<id>`，并使用 `wscat` 连接 `/ws/progress/<task_id>?token=<token>`。
5. **仪表盘统计**：`GET /api/tasks/overview`、`GET /api/user/usage-statistics`。
6. **收尾**：若需要，删除测试项目并调用 `POST /api/auth/logout`，确认返回 401。

每个步骤都必须对照 `docs/api_mapping.md` 中的“通过条件”判定是否成功。若出现异常（错误码、字段缺失、响应格式异常），即时停止并记录详细请求/响应。

---

## 5. 测试结果记录

- 请将测试记录写入 `docs/testing/reports/` 目录，文件命名建议 `YYYYMMDD_HHMM_<tester>.md`。
- 记录内容应包括：
  - 测试步骤与使用的命令；
  - 实际响应（建议采用代码块形式粘贴 JSON）；
  - 通过/失败判定及备注。
- 如果遇到失败，请附上完整请求、响应和错误描述，便于快速排查。

---

如在执行过程中需要支持，或发现文档与实际行为不一致，请及时反馈开发团队。
