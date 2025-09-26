# 模块测试脚本与数据参考

本文档说明新编写的模块化测试脚本如何执行，以及每个接口预期返回的关键字段，便于测试团队快速比对实际结果。

## 1. 协作工作区 API 测试
- **脚本**：`scripts/collaboration_workflow_test.py`
- **命令示例**：
  ```bash
  python3 scripts/collaboration_workflow_test.py \
    --base-url "$VIBERESEARCH_BASE_URL" \
    --email "$VIBERESEARCH_TEST_EMAIL" \
    --password "$VIBERESEARCH_TEST_PASSWORD" \
    --output collaboration_workflow_results.json
  ```
- **主要步骤与预期数据**：
  1. `login`：HTTP 200，响应含 `access_token`。
  2. `project_create`：HTTP 200，JSON 包含 `id`、`name`、`status`（如 `"empty"`）。
  3. `workspace_create`：HTTP 200，JSON `workspace.workspace_id` 为字符串；`workspace_data.name` 应等于请求的 `workspace_name`，成员列表包含当前用户。
  4. `workspace_join`：HTTP 200，返回 `role` 等信息，重复加入时可能返回 200 或提示已在工作区。
  5. `annotation_create`：HTTP 200，返回 `annotation_id`、`content`、`created_at`。
  6. `insight_share`：HTTP 200，返回 `insight_id`、`title`、`summary`。
  7. `workspace_status`：HTTP 200，JSON 包含 `active_members`、`recent_activity`、`workspace_metadata`。
  8. `annotations_list`：HTTP 200，列表中至少包含刚创建的注释（比对 `content`）。
  9. `insights_list`：HTTP 200，列表中至少包含刚共享的洞察。
 10. `workspace_leave` / `project_cleanup`：允许 200 或 404（表示已被删除）。
- **结果整理**：脚本输出 JSON `results` 数组，逐项记录 `status_code` 与 `response`。将此文件与终端日志同存，以便对照接口行为。

## 2. 性能优化 API 测试
- **脚本**：`scripts/performance_insights_test.py`
- **命令示例**：
  ```bash
  python3 scripts/performance_insights_test.py \
    --base-url "$VIBERESEARCH_BASE_URL" \
    --email "$VIBERESEARCH_TEST_EMAIL" \
    --password "$VIBERESEARCH_TEST_PASSWORD" \
    --output performance_insights_results.json
  ```
- **关键接口与字段**：
  1. `performance_status`（GET `/api/performance/status`）
     - 期望：HTTP 200，包含 `status` (`"healthy"`/`"degraded"`)、`overall_score`、`current_metrics.cpu_usage` 等。
  2. `performance_dashboard`（GET `/api/performance/dashboard`）
     - 期望：HTTP 200，`system_health`、`current_metrics`、`active_alerts` 列表、`recommendations`。
  3. `performance_recommendations`（GET `/api/performance/recommendations/optimization`）
     - 期望：HTTP 200，包含 `strategies`、`recommendations` 字段。
  4. `performance_cost_analytics`（GET `/api/performance/analytics/cost`）
     - 期望：HTTP 200，返回 `analytics_period`、`cost_summary`、`status`。
  5. `performance_estimate_cost`（POST `/api/performance/estimate-cost`）
     - 请求：脚本会先创建测试项目，并自动填入该 `project_id`；可通过 `performance_insights_results.json` 验证。
     - 期望：HTTP 200，响应包含各模式的成本估算（`processing_modes` 列表、`recommendation`）。
- **注意事项**：若测试账号没有样本数据，某些成本/推荐字段可能为空或走默认值。记录响应内容以便研发确认数据源是否就绪。

## 3. 输出整理建议
- **JSON 报告**：脚本 `--output` 参数生成的 JSON 应存放在 `artifacts/<日期>/` 中，与其他测试报告统一归档。
- **终端日志**：保留命令与关键输出（PASS/FAIL、错误文本），可直接复制至测试日报或缺陷描述。
- **异常处理**：若出现非预期状态码，请记录响应体并通知研发；可附上相关脚本命令、环境变量和 `response` 字段内容。

如需扩展更多模块的验证脚本，可在该文档继续追加章节，保持字段说明与运行示例同步更新。
