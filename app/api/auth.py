"""
认证相关API路由
"""

from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token,
    get_current_active_user
)
from app.models.user import User, UserMembership, MembershipType
from app.schemas.user_schemas import (
    UserRegisterRequest, UserLoginRequest, TokenResponse, UserResponse, UserMembershipResponse
)
from app.core.config import settings

router = APIRouter()

# 使用统一的Schema定义，删除重复定义

@router.post("/register", response_model=TokenResponse)
async def register(user_data: UserRegisterRequest, db: Session = Depends(get_db)):
    """用户注册"""
    
    # 检查邮箱是否已存在
    if db.query(User).filter(User.email == user_data.email).first():
        raise HTTPException(
            status_code=400,
            detail="邮箱已被注册"
        )
    
    # 检查用户名是否已存在
    if db.query(User).filter(User.username == user_data.username).first():
        raise HTTPException(
            status_code=400,
            detail="用户名已被使用"
        )
    
    # 创建用户
    hashed_password = get_password_hash(user_data.password)
    user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        full_name=user_data.full_name,
        institution=user_data.institution,
        research_field=user_data.research_field
    )
    
    db.add(user)
    db.flush()  # 获取用户ID
    
    # 创建会员信息
    membership = UserMembership(
        user_id=user.id,
        membership_type=MembershipType.FREE
    )
    
    db.add(membership)
    db.commit()
    db.refresh(user)
    
    # 生成访问令牌
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    # 构造完整的用户响应对象
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        institution=user.institution,
        research_field=user.research_field,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        membership=membership
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user_info=user_response
    )

@router.post("/login", response_model=TokenResponse)
async def login(login_data: UserLoginRequest, db: Session = Depends(get_db)):
    """用户登录"""
    
    # 验证用户
    user = db.query(User).filter(User.email == login_data.email).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="账户已被禁用"
        )
    
    # 更新最后登录时间
    from datetime import datetime
    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)
    
    # 获取会员信息
    membership = user.membership
    membership_response = None
    if membership:
        membership_response = UserMembershipResponse(
            id=membership.id,
            user_id=membership.user_id,
            membership_type=membership.membership_type.value,
            monthly_literature_used=membership.monthly_literature_used,
            monthly_queries_used=membership.monthly_queries_used,
            total_projects=membership.total_projects,
            subscription_start=membership.subscription_start,
            subscription_end=membership.subscription_end,
            auto_renewal=membership.auto_renewal,
            created_at=membership.created_at,
            updated_at=membership.updated_at
        )
    
    # 生成访问令牌
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)}, expires_delta=access_token_expires
    )
    
    # 构造用户响应对象
    user_response = UserResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        institution=user.institution,
        research_field=user.research_field,
        is_active=user.is_active,
        is_verified=user.is_verified,
        created_at=user.created_at,
        updated_at=user.updated_at,
        last_login=user.last_login,
        membership=membership_response
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.access_token_expire_minutes * 60,
        user_info=user_response
    )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_active_user)):
    """获取当前用户信息"""
    
    membership = current_user.membership
    
    # 构造会员信息响应
    membership_response = None
    if membership:
        membership_response = UserMembershipResponse(
            id=membership.id,
            user_id=membership.user_id,
            membership_type=membership.membership_type.value,
            monthly_literature_used=membership.monthly_literature_used,
            monthly_queries_used=membership.monthly_queries_used,
            total_projects=membership.total_projects,
            subscription_start=membership.subscription_start,
            subscription_end=membership.subscription_end,
            auto_renewal=membership.auto_renewal,
            created_at=membership.created_at,
            updated_at=membership.updated_at
        )
    
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
        membership=membership_response
    )

@router.post("/logout")
async def logout():
    """用户登出"""
    return {"message": "登出成功"}