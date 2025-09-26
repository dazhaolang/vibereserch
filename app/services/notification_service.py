"""
通知服务
"""

import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional
from loguru import logger
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import Notification, NotificationType, NotificationStatus

class NotificationService:
    """通知服务类"""
    
    def __init__(self):
        # 邮件配置（从全局设置读取，便于不同环境覆盖）
        self.smtp_server = settings.smtp_host
        self.smtp_port = settings.smtp_port
        self.smtp_username = settings.smtp_username
        self.smtp_password = settings.smtp_password
        self.use_tls = settings.smtp_use_tls
        self.smtp_timeout = settings.smtp_timeout_seconds
        self.default_sender = settings.notifications_from_email or self.smtp_username

    def _smtp_configured(self) -> bool:
        """判断SMTP是否已正确配置"""
        return bool(self.smtp_server and self.default_sender)
        
    async def send_email(
        self,
        to_email: str,
        subject: str,
        content: str,
        html_content: Optional[str] = None
    ) -> bool:
        """
        发送邮件通知
        
        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            content: 邮件内容（文本）
            html_content: 邮件内容（HTML）
            
        Returns:
            是否发送成功
        """
        if not settings.notifications_enabled:
            logger.info("通知发送已禁用，跳过邮件发送: %s", to_email)
            return False

        if not self._smtp_configured():
            logger.warning("SMTP 未配置，无法发送邮件通知: %s", to_email)
            return False

        try:
            # 创建邮件消息
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.default_sender
            message["To"] = to_email
            
            # 添加文本内容
            text_part = MIMEText(content, "plain", "utf-8")
            message.attach(text_part)
            
            # 添加HTML内容
            if html_content:
                html_part = MIMEText(html_content, "html", "utf-8")
                message.attach(html_part)
            
            # 发送邮件，放入线程池避免阻塞事件循环
            def _send_message() -> None:
                with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=self.smtp_timeout) as server:
                    if self.use_tls:
                        server.starttls()
                    if self.smtp_username and self.smtp_password:
                        server.login(self.smtp_username, self.smtp_password)
                    server.send_message(message)

            await asyncio.to_thread(_send_message)
            logger.info(f"邮件已发送到: {to_email}")
            return True

        except Exception as e:
            logger.error(f"邮件发送失败: {e}")
            return False
    
    async def send_batch_emails(
        self,
        recipients: List[str],
        subject: str,
        content: str,
        html_content: Optional[str] = None
    ) -> Dict[str, bool]:
        """
        批量发送邮件
        
        Args:
            recipients: 收件人列表
            subject: 邮件主题
            content: 邮件内容
            html_content: HTML内容
            
        Returns:
            发送结果字典
        """
        if not recipients:
            return {}

        send_tasks = [self.send_email(email, subject, content, html_content) for email in recipients]
        results = await asyncio.gather(*send_tasks, return_exceptions=True)

        outcome: Dict[str, bool] = {}
        for email, result in zip(recipients, results):
            if isinstance(result, Exception):
                logger.error(f"发送邮件到 {email} 失败: {result}")
                outcome[email] = False
            else:
                outcome[email] = bool(result)

        return outcome
    
    async def send_invitation_notification(
        self,
        inviter_name: str,
        invitee_email: str,
        project_name: Optional[str] = None,
        team_name: Optional[str] = None,
        invitation_link: str = ""
    ) -> bool:
        """发送协作邀请通知"""
        
        target = project_name or team_name or "项目"
        
        subject = f"{inviter_name} 邀请您加入 {target} 协作"
        
        content = f"""
亲爱的研究者，

{inviter_name} 邀请您加入科研文献智能分析平台的协作项目。

项目信息：
- 项目名称：{target}
- 邀请人：{inviter_name}
- 邀请时间：{datetime.now().strftime('%Y年%m月%d日')}

通过协作，您可以：
✅ 共同管理和分析文献库
✅ 分享研究经验和洞察
✅ 协同生成创新想法
✅ 实时交流和讨论

请点击以下链接接受邀请：
{invitation_link}

如果您还没有账户，系统将引导您完成注册。

此邀请将在7天后过期，请及时处理。

祝您研究顺利！

科研文献智能分析平台
https://research-platform.com
"""
        
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>协作邀请</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #3b82f6, #8b5cf6); color: white; padding: 30px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: white; padding: 30px; border: 1px solid #e5e7eb; }}
        .footer {{ background: #f9fafb; padding: 20px; text-align: center; border-radius: 0 0 8px 8px; }}
        .button {{ display: inline-block; background: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
        .features {{ background: #f0f9ff; padding: 20px; border-radius: 6px; margin: 20px 0; }}
        .features ul {{ list-style: none; padding: 0; }}
        .features li {{ padding: 8px 0; }}
        .features li:before {{ content: "✅"; margin-right: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 科研协作邀请</h1>
            <p>加入智能化的科研团队</p>
        </div>
        
        <div class="content">
            <h2>您被邀请加入协作项目</h2>
            <p><strong>{inviter_name}</strong> 邀请您加入 <strong>{target}</strong> 的协作研究。</p>
            
            <div class="features">
                <h3>协作功能亮点：</h3>
                <ul>
                    <li>共同管理和分析文献库</li>
                    <li>分享研究经验和洞察</li>
                    <li>协同生成创新想法</li>
                    <li>实时交流和讨论</li>
                </ul>
            </div>
            
            <div style="text-align: center;">
                <a href="{invitation_link}" class="button">接受邀请</a>
            </div>
            
            <p><small>此邀请将在7天后过期，请及时处理。</small></p>
        </div>
        
        <div class="footer">
            <p>科研文献智能分析平台</p>
            <p><a href="https://research-platform.com">https://research-platform.com</a></p>
        </div>
    </div>
</body>
</html>
"""
        
        return await self.send_email(invitee_email, subject, content, html_content)
    
    async def send_task_completion_notification(
        self,
        user_email: str,
        task_name: str,
        project_name: str,
        result_summary: str
    ) -> bool:
        """发送任务完成通知"""
        
        subject = f"任务完成通知 - {task_name}"
        
        content = f"""
您好！

您在项目 "{project_name}" 中的任务 "{task_name}" 已完成。

任务结果：
{result_summary}

您可以登录平台查看详细结果：
https://research-platform.com/app/projects

科研文献智能分析平台
"""
        
        return await self.send_email(user_email, subject, content)
    
    async def send_comment_notification(
        self,
        recipient_email: str,
        commenter_name: str,
        project_name: str,
        comment_content: str
    ) -> bool:
        """发送评论通知"""
        
        subject = f"新评论通知 - {project_name}"
        
        content = f"""
您好！

{commenter_name} 在项目 "{project_name}" 中添加了新评论：

"{comment_content[:200]}{'...' if len(comment_content) > 200 else ''}"

登录平台查看完整评论和回复：
https://research-platform.com/app/projects

科研文献智能分析平台
"""
        
        return await self.send_email(recipient_email, subject, content)

    async def create_in_app_notification(
        self,
        db: Session,
        user_id: int,
        notification_type: NotificationType,
        title: str,
        message: str,
        action_url: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> bool:
        """创建应用内通知"""

        try:
            notification = Notification(
                user_id=user_id,
                type=notification_type,
                title=title,
                message=message,
                action_url=action_url,
                metadata_payload=metadata,
                status=NotificationStatus.UNREAD
            )

            db.add(notification)
            db.commit()
            db.refresh(notification)

            logger.info(f"应用内通知已创建: {notification_type.value} for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"创建应用内通知失败: {e}")
            db.rollback()
            return False

    async def create_task_completion_notification(
        self,
        db: Session,
        user_id: int,
        task_name: str,
        project_name: str,
        task_id: Optional[int] = None
    ) -> bool:
        """创建任务完成通知"""

        metadata = {"task_id": task_id} if task_id else None
        action_url = f"/app/projects/{task_id}" if task_id else None

        return await self.create_in_app_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.TASK_COMPLETED,
            title="任务完成",
            message=f"项目 '{project_name}' 中的任务 '{task_name}' 已完成",
            action_url=action_url,
            metadata=metadata
        )

    async def create_task_failed_notification(
        self,
        db: Session,
        user_id: int,
        task_name: str,
        project_name: str,
        error_message: str,
        task_id: Optional[int] = None
    ) -> bool:
        """创建任务失败通知"""

        metadata = {"task_id": task_id, "error": error_message} if task_id else {"error": error_message}
        action_url = f"/app/projects/{task_id}" if task_id else None

        return await self.create_in_app_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.TASK_FAILED,
            title="任务失败",
            message=f"项目 '{project_name}' 中的任务 '{task_name}' 执行失败: {error_message}",
            action_url=action_url,
            metadata=metadata
        )

    async def create_membership_expiring_notification(
        self,
        db: Session,
        user_id: int,
        days_remaining: int
    ) -> bool:
        """创建会员即将到期通知"""

        return await self.create_in_app_notification(
            db=db,
            user_id=user_id,
            notification_type=NotificationType.MEMBERSHIP_EXPIRING,
            title="会员即将到期",
            message=f"您的会员将在 {days_remaining} 天后到期，请及时续费以继续享受服务",
            action_url="/app/profile/membership",
            metadata={"days_remaining": days_remaining}
        )
