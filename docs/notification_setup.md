# 邮件通知配置指南

后端的 `NotificationService` 支持通过 SMTP 发送协作邀请、任务完成提醒等邮件。默认情况下如果未配置 SMTP 或显式关闭通知，服务会安全降级，仅记录日志。以下步骤可帮助你快速启用通知功能。

## 1. 配置环境变量

在 `.env` 中设置：

```ini
NOTIFICATIONS_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=bot@example.com
SMTP_PASSWORD=your-app-password
SMTP_USE_TLS=true
SMTP_TIMEOUT_SECONDS=30
NOTIFICATIONS_FROM_EMAIL=research-bot@example.com
```

说明：
- **NOTIFICATIONS_ENABLED**：全局开关，置为 `false` 会跳过所有外发邮件。
- **SMTP_HOST / SMTP_PORT**：SMTP 服务器地址与端口，常见提供商通常使用 587 端口配合 STARTTLS。
- **SMTP_USERNAME / SMTP_PASSWORD**：登录凭据，可使用应用专用密码。
- **SMTP_USE_TLS**：是否在发送前执行 `STARTTLS`，若使用 465 端口可改为 `false` 并结合 SSL。
- **SMTP_TIMEOUT_SECONDS**：网络请求超时时间，避免 SMTP 阻塞事件循环。
- **NOTIFICATIONS_FROM_EMAIL**：发件人地址，未设置时回退到 `SMTP_USERNAME`。

## 2. 验证健康检查

配置完成后，`GET /healthz` 会继续返回 `healthy`，若 SMTP 失效不会影响健康检查（服务会自动降级并记录日志）。

## 3. 触发测试

可通过以下任一方式验证：
- 触发任务执行并等待完成，任务完成通知会向任务所有者发送邮件。
- 使用交互式 shell 调用 `NotificationService().send_invitation_notification(...)`，确认邮件送达。

## 4. 故障排查

| 症状 | 排查建议 |
| --- | --- |
| 日志提示 `SMTP 未配置` | 确保 `.env` 中设置了 `SMTP_HOST` 和 `NOTIFICATIONS_FROM_EMAIL` |
| 日志提示登录失败 | 检查用户名/密码或是否需要应用专用密码 |
| 邮件被判为垃圾 | 为发件域名配置 SPF/DKIM，或使用受信任的邮件服务商 |

如需扩展其他通知渠道（如 Slack、企业微信），可在 `NotificationService` 中新增对应方法，复用当前的开关逻辑以便统一管理。
