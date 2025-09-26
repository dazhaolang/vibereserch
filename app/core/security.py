"""
安全认证相关功能
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from loguru import logger

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.core.exceptions import ErrorFactory, AuthenticationError, ErrorCode
from app.core.time_utils import utc_now

# 密码加密上下文 - 优化性能：使用rounds=10平衡安全性和速度
pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=10  # 降低rounds以提高性能，10rounds约200-400ms
)

# JWT认证
security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """创建访问令牌"""
    to_encode = data.copy()
    if expires_delta:
        expire = utc_now() + expires_delta
    else:
        expire = utc_now() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """验证令牌，支持主密钥与备用密钥"""
    last_error: Optional[JWTError] = None

    for idx, secret_key in enumerate(settings.jwt_decode_keys):
        try:
            payload = jwt.decode(token, secret_key, algorithms=[settings.jwt_algorithm])
            if idx > 0:
                logger.warning("JWT 使用备用密钥完成验证 (index=%s)", idx)
            return payload
        except JWTError as exc:  # 记录最后一次错误，尝试下一把钥匙
            last_error = exc
            continue

    if last_error:
        logger.error("JWT 验证失败: %s", last_error)
    return None

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """获取当前用户"""
    
    try:
        token = credentials.credentials
        payload = verify_token(token)
        
        if payload is None:
            raise AuthenticationError(ErrorCode.TOKEN_EXPIRED, "令牌无效或已过期")
        
        user_identifier = payload.get("sub")
        if user_identifier is None:
            raise AuthenticationError(ErrorCode.INVALID_CREDENTIALS, "令牌中缺少用户信息")
        
        # 尝试通过ID或邮箱查找用户
        user = None
        if isinstance(user_identifier, int) or str(user_identifier).isdigit():
            # 如果是数字，按ID查找
            user = db.query(User).filter(User.id == int(user_identifier)).first()
        else:
            # 否则按邮箱查找
            user = db.query(User).filter(User.email == user_identifier).first()
        
        if user is None:
            raise AuthenticationError(ErrorCode.USER_NOT_FOUND, f"用户不存在: {user_identifier}")
        
        # 更新最后登录时间
        user.last_login = utc_now()
        db.commit()
        
        return user
        
    except AuthenticationError:
        raise
    except Exception as e:
        logger.error(f"获取当前用户失败: {e}")
        raise AuthenticationError(ErrorCode.INVALID_CREDENTIALS, "身份验证失败")

async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """获取当前活跃用户"""
    if not current_user.is_active:
        raise AuthenticationError(ErrorCode.ACCOUNT_DISABLED, "账户已被禁用")
    return current_user

async def get_current_user_from_token(token: str, db: Session) -> Optional[User]:
    """从token直接获取用户信息，用于WebSocket认证"""
    try:
        payload = verify_token(token)
        
        if payload is None:
            return None
        
        user_identifier = payload.get("sub")
        if user_identifier is None:
            return None
        
        # 尝试通过ID或邮箱查找用户
        user = None
        if isinstance(user_identifier, int) or str(user_identifier).isdigit():
            # 如果是数字，按ID查找
            user = db.query(User).filter(User.id == int(user_identifier)).first()
        else:
            # 否则按邮箱查找
            user = db.query(User).filter(User.email == user_identifier).first()
        
        return user if user and user.is_active else None
        
    except Exception as e:
        logger.error(f"从token获取用户失败: {e}")
        return None
