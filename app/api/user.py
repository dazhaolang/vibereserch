"""
用户管理API路由
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from sqlalchemy.orm import Session
from pydantic import BaseModel
import os
import shutil
from pathlib import Path
from PIL import Image
import io
import hashlib
from datetime import datetime

from app.core.database import get_db
from app.core.security import get_current_active_user, get_password_hash
from app.core.config import settings
from app.models.user import User, UserMembership, MembershipType, SecurityEvent, Notification, NotificationType
from app.schemas.user_schemas import (
    UserResponse,
    UsageStatisticsResponse,
    MembershipUpgradeResponse,
    UserProfileUpdateResponse,
    PasswordUpdateResponse,
    SecurityEventResponse,
    NotificationResponse,
    NotificationUpdateRequest
)
from app.services.security_service import log_password_change_event

router = APIRouter()

class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    institution: Optional[str] = None
    research_field: Optional[str] = None

class PasswordUpdate(BaseModel):
    current_password: str
    new_password: str

class MembershipUpgrade(BaseModel):
    membership_type: str
    payment_info: Optional[dict] = None

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取用户详细资料"""
    
    membership = db.query(UserMembership).filter(
        UserMembership.user_id == current_user.id
    ).first()
    
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        institution=current_user.institution,
        research_field=current_user.research_field,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at,
        last_login=current_user.last_login,
        membership=membership
    )

@router.put("/profile", response_model=UserProfileUpdateResponse)
async def update_user_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新用户资料"""
    
    # 更新用户信息
    if user_data.full_name is not None:
        current_user.full_name = user_data.full_name
    if user_data.institution is not None:
        current_user.institution = user_data.institution
    if user_data.research_field is not None:
        current_user.research_field = user_data.research_field
    
    db.commit()
    
    return UserProfileUpdateResponse(
        success=True,
        message="用户资料更新成功"
    )

@router.put("/password", response_model=PasswordUpdateResponse)
async def update_password(
    password_data: PasswordUpdate,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新密码"""
    
    from app.core.security import verify_password
    
    # 验证当前密码
    if not verify_password(password_data.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="当前密码错误")
    
    # 更新密码
    current_user.hashed_password = get_password_hash(password_data.new_password)
    db.commit()

    # Log password change event
    log_password_change_event(db, current_user.id, request)

    return PasswordUpdateResponse(
        success=True,
        message="密码更新成功"
    )

@router.get("/usage-statistics", response_model=UsageStatisticsResponse)
async def get_usage_statistics(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取用户使用统计"""
    
    try:
        # 获取会员信息
        membership = db.query(UserMembership).filter(
            UserMembership.user_id == current_user.id
        ).first()
        
        membership_type = membership.membership_type if membership else "free"
        
        # 优化查询：分步进行，避免复杂JOIN
        from app.models.project import Project
        from app.models.literature import Literature
        from app.models.task import Task
        
        # 1. 获取用户项目
        total_projects = db.query(Project).filter(Project.owner_id == current_user.id).count()
        
        # 2. 获取文献统计（优化查询）
        try:
            total_literature = db.query(Literature).join(Project).filter(
                Project.owner_id == current_user.id
            ).count()
        except Exception:
            # 如果JOIN失败，使用备用查询
            total_literature = 0
        
        # 3. 获取任务统计（优化查询）
        try:
            total_tasks = db.query(Task).join(Project).filter(
                Project.owner_id == current_user.id
            ).count()
            completed_tasks = db.query(Task).join(Project).filter(
                Project.owner_id == current_user.id, 
                Task.status == 'completed'
            ).count()
        except Exception:
            # 如果JOIN失败，使用备用查询
            total_tasks = 0
            completed_tasks = 0
        
        # 获取月度使用量（如果membership存在）
        monthly_literature_used = membership.monthly_literature_used if membership else 0
        monthly_queries_used = membership.monthly_queries_used if membership else 0
        
        # 设置限制（基于会员类型）
        limits = {
            "literature": 500 if membership_type == "free" else 2000 if membership_type == "premium" else 10000,
            "projects": 3 if membership_type == "free" else 10 if membership_type == "premium" else 50,
            "monthly_queries": 100 if membership_type == "free" else 500 if membership_type == "premium" else 2000
        }
        
        # 计算使用百分比（安全计算，避免除零错误）
        usage_percentage = {
            "literature": min((total_literature / max(limits["literature"], 1)) * 100, 100),
            "projects": min((total_projects / max(limits["projects"], 1)) * 100, 100),
            "monthly_queries": min((monthly_queries_used / max(limits["monthly_queries"], 1)) * 100, 100)
        }
        
        usage = {
            "total_projects": total_projects,
            "total_literature": total_literature,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "monthly_literature_used": monthly_literature_used,
            "monthly_queries_used": monthly_queries_used
        }
        
        return UsageStatisticsResponse(
            membership_type=membership_type,
            usage=usage,
            limits=limits,
            usage_percentage=usage_percentage
        )
        
    except Exception as e:
        # 统一异常处理，返回基础统计信息
        logger.error(f"获取用户统计失败: {e}")
        return UsageStatisticsResponse(
            membership_type="free",
            usage={
                "total_projects": 0,
                "total_literature": 0,
                "total_tasks": 0,
                "completed_tasks": 0,
                "monthly_literature_used": 0,
                "monthly_queries_used": 0
            },
            limits={
                "literature": 500,
                "projects": 3,
                "monthly_queries": 100
            },
            usage_percentage={
                "literature": 0,
                "projects": 0,
                "monthly_queries": 0
            }
        )

@router.post("/upgrade-membership", response_model=MembershipUpgradeResponse)
async def upgrade_membership(
    upgrade_data: MembershipUpgrade,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """升级会员"""
    
    try:
        # 验证会员类型
        valid_types = ["free", "premium", "enterprise"]
        if upgrade_data.membership_type not in valid_types:
            raise HTTPException(status_code=400, detail="无效的会员类型")
        
        # 获取或创建会员记录
        membership = db.query(UserMembership).filter(
            UserMembership.user_id == current_user.id
        ).first()
        
        if not membership:
            membership = UserMembership(
                user_id=current_user.id,
                membership_type=upgrade_data.membership_type,
                monthly_literature_used=0,
                monthly_queries_used=0,
                total_projects=0,
                auto_renewal=True
            )
            db.add(membership)
        else:
            membership.membership_type = upgrade_data.membership_type
        
        # 模拟支付处理 - 在实际生产环境中需要集成真实支付系统
        if upgrade_data.payment_info:
            # 这里可以集成实际的支付处理逻辑
            # 如 Stripe, PayPal, Alipay 等
            # process_payment(upgrade_data.payment_info)
            pass
        
        db.commit()
        
        return MembershipUpgradeResponse(
            success=True,
            message=f"会员已成功升级至 {upgrade_data.membership_type}",
            new_membership_type=upgrade_data.membership_type
        )
        
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        # 处理其他异常
        db.rollback()
        logger.error(f"会员升级失败: {e}")
        return MembershipUpgradeResponse(
            success=False,
            message=f"会员升级失败: 系统错误",
            new_membership_type=upgrade_data.membership_type
        )

@router.get("/security-events", response_model=List[SecurityEventResponse])
async def get_security_events(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = 100
):
    """获取用户安全事件记录"""

    try:
        # 查询用户的安全事件，按时间倒序，限制数量
        security_events = db.query(SecurityEvent).filter(
            SecurityEvent.user_id == current_user.id
        ).order_by(
            SecurityEvent.created_at.desc()
        ).limit(limit).all()

        # 转换为响应格式
        events_response = []
        for event in security_events:
            events_response.append(SecurityEventResponse(
                id=event.id,
                user_id=event.user_id,
                event_type=event.event_type.value,
                ip_address=event.ip_address,
                location=event.location,
                device_info=event.device_info,
                user_agent=event.user_agent,
                metadata=event.event_metadata,
                created_at=event.created_at
            ))

        return events_response

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取安全事件失败: {e}")
        # 返回空列表而不是抛出异常，保证前端稳定性
        return []

@router.get("/notifications", response_model=List[NotificationResponse])
async def get_user_notifications(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = 50,
    unread_only: bool = False
):
    """获取用户通知列表"""

    try:
        query = db.query(Notification).filter(
            Notification.user_id == current_user.id
        )

        if unread_only:
            query = query.filter(Notification.status == "unread")

        notifications = query.order_by(
            Notification.created_at.desc()
        ).limit(limit).all()

        # 转换为响应格式
        notifications_response = [
            NotificationResponse(
                id=notification.id,
                user_id=notification.user_id,
                type=notification.type.value,
                title=notification.title,
                message=notification.message,
                status=notification.status.value,
                action_url=notification.action_url,
                metadata=notification.metadata_payload,
                created_at=notification.created_at,
                updated_at=notification.updated_at,
                read_at=notification.read_at
            )
            for notification in notifications
        ]

        return notifications_response

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取通知失败: {e}")
        return []

@router.put("/notifications/{notification_id}", response_model=NotificationResponse)
async def update_notification(
    notification_id: int,
    update_data: NotificationUpdateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """更新通知状态"""

    # 查找通知
    notification = db.query(Notification).filter(
        Notification.id == notification_id,
        Notification.user_id == current_user.id
    ).first()

    if not notification:
        raise HTTPException(status_code=404, detail="通知不存在")

    # 更新状态
    notification.status = update_data.status
    if update_data.status.value == "read" and not notification.read_at:
        from datetime import datetime
        notification.read_at = datetime.utcnow()

    db.commit()
    db.refresh(notification)

    return NotificationResponse(
        id=notification.id,
        user_id=notification.user_id,
        type=notification.type.value,
        title=notification.title,
        message=notification.message,
        status=notification.status.value,
        action_url=notification.action_url,
        metadata=notification.metadata_payload,
        created_at=notification.created_at,
        updated_at=notification.updated_at,
        read_at=notification.read_at
    )

@router.get("/notifications/unread-count")
async def get_unread_notifications_count(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """获取未读通知数量"""

    try:
        count = db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.status == "unread"
        ).count()

        return {"unread_count": count}

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"获取未读通知数量失败: {e}")
        return {"unread_count": 0}

@router.post("/notifications/mark-all-read")
async def mark_all_notifications_read(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """标记所有通知为已读"""

    try:
        from datetime import datetime

        # 更新所有未读通知
        db.query(Notification).filter(
            Notification.user_id == current_user.id,
            Notification.status == "unread"
        ).update({
            "status": "read",
            "read_at": datetime.utcnow()
        })

        db.commit()

        return {"message": "所有通知已标记为已读"}

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"标记所有通知已读失败: {e}")
        raise HTTPException(status_code=500, detail="操作失败")

@router.post("/profile/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """上传用户头像"""

    try:
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="只支持图片文件")

        # 支持的图片格式
        allowed_types = ['image/jpeg', 'image/png', 'image/webp']
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="支持的格式：JPEG、PNG、WebP")

        # 验证文件大小 (最大 5MB)
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件大小不能超过 5MB")

        # 重置文件指针
        await file.seek(0)

        # 验证图片完整性并获取尺寸
        try:
            image = Image.open(io.BytesIO(content))
            width, height = image.size

            # 限制图片尺寸
            max_size = 2048
            if width > max_size or height > max_size:
                raise HTTPException(status_code=400, detail=f"图片尺寸不能超过 {max_size}x{max_size}")

        except Exception as e:
            raise HTTPException(status_code=400, detail="无效的图片文件")

        # 创建头像目录
        avatar_dir = Path(settings.upload_path) / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # 生成文件名
        file_hash = hashlib.md5(content).hexdigest()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{current_user.id}_{timestamp}_{file_hash[:8]}.{file.content_type.split('/')[-1]}"
        file_path = avatar_dir / filename

        # 处理图片：调整大小并优化
        try:
            # 创建多个尺寸的头像
            sizes = [256, 128, 64]  # 大、中、小三个尺寸
            saved_files = {}

            for size in sizes:
                # 计算缩放比例，保持长宽比
                ratio = min(size / width, size / height)
                new_width = int(width * ratio)
                new_height = int(height * ratio)

                # 调整图片大小
                resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # 创建正方形背景
                square_image = Image.new('RGB', (size, size), (255, 255, 255))

                # 居中粘贴调整后的图片
                offset = ((size - new_width) // 2, (size - new_height) // 2)
                square_image.paste(resized_image, offset)

                # 保存文件
                size_filename = f"{current_user.id}_{timestamp}_{file_hash[:8]}_{size}.jpg"
                size_file_path = avatar_dir / size_filename

                square_image.save(size_file_path, "JPEG", quality=85, optimize=True)
                saved_files[f"avatar_{size}"] = f"/uploads/avatars/{size_filename}"

            # 删除用户之前的头像文件
            if current_user.avatar_url:
                try:
                    # 删除所有尺寸的旧头像
                    for size in sizes:
                        old_path = Path(settings.UPLOAD_DIR) / "avatars" / f"{current_user.id}_*_{size}.jpg"
                        for old_file in avatar_dir.glob(f"{current_user.id}_*_{size}.jpg"):
                            if old_file.exists():
                                old_file.unlink()
                except Exception:
                    pass  # 忽略删除旧文件的错误

            # 更新用户头像URL（保存最大尺寸的URL）
            current_user.avatar_url = saved_files["avatar_256"]
            db.commit()

            return {
                "success": True,
                "message": "头像上传成功",
                "avatar_urls": saved_files,
                "avatar_url": saved_files["avatar_256"]  # 主头像URL
            }

        except Exception as e:
            # 清理已保存的文件
            for size in sizes:
                try:
                    size_file_path = avatar_dir / f"{current_user.id}_{timestamp}_{file_hash[:8]}_{size}.jpg"
                    if size_file_path.exists():
                        size_file_path.unlink()
                except:
                    pass
            raise HTTPException(status_code=500, detail=f"图片处理失败: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"头像上传失败: {e}")
        raise HTTPException(status_code=500, detail="头像上传失败")

@router.delete("/profile/avatar")
async def delete_avatar(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """删除用户头像"""

    try:
        if not current_user.avatar_url:
            raise HTTPException(status_code=404, detail="用户未设置头像")

        # 删除头像文件
        avatar_dir = Path(settings.upload_path) / "avatars"
        sizes = [256, 128, 64]

        for size in sizes:
            try:
                # 查找并删除对应尺寸的头像文件
                for avatar_file in avatar_dir.glob(f"{current_user.id}_*_{size}.jpg"):
                    if avatar_file.exists():
                        avatar_file.unlink()
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"删除头像文件失败: {e}")

        # 清空数据库中的头像URL
        current_user.avatar_url = None
        db.commit()

        return {
            "success": True,
            "message": "头像删除成功"
        }

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"头像删除失败: {e}")
        raise HTTPException(status_code=500, detail="头像删除失败")
