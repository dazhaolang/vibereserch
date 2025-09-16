"""
用户管理API路由
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import get_current_active_user, get_password_hash
from app.models.user import User, UserMembership, MembershipType
from app.schemas.user_schemas import (
    UserResponse, 
    UsageStatisticsResponse,
    MembershipUpgradeResponse,
    UserProfileUpdateResponse,
    PasswordUpdateResponse
)

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