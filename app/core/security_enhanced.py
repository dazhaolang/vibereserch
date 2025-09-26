"""
安全增强模块 - 实现认证、授权和安全防护
"""

from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# slowapi is optional; fall back to a no-op limiter when unavailable
try:
    from slowapi import Limiter  # type: ignore
    from slowapi.util import get_remote_address  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - executed only when dependency missing
    class _FallbackLimiter:
        """Minimal limiter stub ensuring imports succeed without slowapi."""

        def __init__(self, key_func=None):
            self.key_func = key_func

        def limit(self, *_args, **_kwargs):
            def decorator(func):
                return func

            return decorator

    def get_remote_address(request):
        return getattr(getattr(request, "client", None), "host", "127.0.0.1")

    Limiter = _FallbackLimiter
from passlib.context import CryptContext
import secrets
import re
import sys
from types import ModuleType
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from loguru import logger
from app.core.time_utils import utc_now

# pyotp is optional in some environments; provide a lightweight fallback
try:
    import pyotp  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - executed only when dependency missing
    import base64
    import hashlib
    import hmac
    import struct
    import time
    import urllib.parse

    def _normalize_base32(secret: str) -> str:
        normalized = secret.replace(" ", "").upper()
        padding = (-len(normalized)) % 8
        return normalized + "=" * padding

    def random_base32(length: int = 32) -> str:
        alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567"
        return "".join(secrets.choice(alphabet) for _ in range(length))

    class _SimpleTOTP:
        def __init__(self, secret: str, interval: int = 30, digits: int = 6, digest=hashlib.sha1):
            self.secret = secret
            self.interval = interval
            self.digits = digits
            self.digest = digest

        def _timecode(self, for_time: Optional[float] = None) -> int:
            current = time.time() if for_time is None else for_time
            return int(current // self.interval)

        def _generate_otp(self, for_time: Optional[float] = None) -> str:
            key = base64.b32decode(_normalize_base32(self.secret), casefold=True)
            counter = struct.pack("!Q", self._timecode(for_time))
            digest = hmac.new(key, counter, self.digest).digest()
            offset = digest[-1] & 0x0F
            code = (
                ((digest[offset] & 0x7F) << 24)
                | ((digest[offset + 1] & 0xFF) << 16)
                | ((digest[offset + 2] & 0xFF) << 8)
                | (digest[offset + 3] & 0xFF)
            )
            return str(code % (10 ** self.digits)).zfill(self.digits)

        def now(self) -> str:
            return self._generate_otp()

        def verify(self, token: str, valid_window: int = 0) -> bool:
            expected_token = str(token).zfill(self.digits)
            current_time = time.time()
            for offset in range(-valid_window, valid_window + 1):
                candidate_time = current_time + (offset * self.interval)
                if self._generate_otp(candidate_time) == expected_token:
                    return True
            return False

        def provisioning_uri(self, name: str, issuer_name: Optional[str] = None) -> str:
            label = urllib.parse.quote(name)
            issuer = urllib.parse.quote(issuer_name) if issuer_name else None
            params = [f"secret={self.secret}", f"period={self.interval}"]
            if issuer:
                params.append(f"issuer={issuer}")
            return f"otpauth://totp/{label}?" + "&".join(params)

    pyotp_module = ModuleType("pyotp")
    pyotp_module.random_base32 = random_base32
    pyotp_module.TOTP = _SimpleTOTP
    totp_module = ModuleType("pyotp.totp")
    totp_module.TOTP = _SimpleTOTP
    pyotp_module.totp = totp_module
    sys.modules["pyotp"] = pyotp_module
    sys.modules["pyotp.totp"] = totp_module
    pyotp = pyotp_module

# 密码加密上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# API速率限制器
limiter = Limiter(key_func=get_remote_address)

class SecurityManager:
    """安全管理器"""

    # 密码强度规则
    PASSWORD_MIN_LENGTH = 8
    SPECIAL_CHARACTERS = "!@#$%^&*()_+-=[]{}|;:'\",.<>/?`~"
    PASSWORD_PATTERN = re.compile(
        rf"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[{re.escape(SPECIAL_CHARACTERS)}])"
        rf"[A-Za-z\d{re.escape(SPECIAL_CHARACTERS)}]{{{PASSWORD_MIN_LENGTH},}}$"
    )

    # 登录失败锁定策略
    MAX_LOGIN_ATTEMPTS = 5
    LOCKOUT_DURATION_MINUTES = 30

    # Session配置
    SESSION_DURATION_HOURS = 24
    SESSION_REFRESH_HOURS = 1

    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, str]:
        """
        验证密码强度
        要求：至少8位，包含大小写字母、数字和特殊字符
        """
        if not SecurityManager.PASSWORD_PATTERN.match(password):
            return False, (
                f"密码必须至少{SecurityManager.PASSWORD_MIN_LENGTH}位，并包含大小写字母、数字和特殊字符"
                f"({SecurityManager.SPECIAL_CHARACTERS})"
            )
        return True, "密码强度符合要求"

    @staticmethod
    def hash_password(password: str) -> str:
        """哈希密码"""
        return pwd_context.hash(password)

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """验证密码"""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def generate_session_token() -> str:
        """生成安全的会话令牌"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def generate_2fa_secret() -> str:
        """生成2FA密钥"""
        return pyotp.random_base32()

    @staticmethod
    def generate_2fa_qr_code(secret: str, email: str) -> str:
        """生成2FA二维码URL"""
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=email,
            issuer_name='VibeSearch'
        )
        return totp_uri

    @staticmethod
    def verify_2fa_token(secret: str, token: str) -> bool:
        """验证2FA令牌"""
        totp = pyotp.TOTP(secret)
        return totp.verify(token, valid_window=1)

    @staticmethod
    def check_account_lockout(user, db: Session) -> bool:
        """检查账户是否被锁定"""
        if user.locked_until and user.locked_until > utc_now():
            remaining_minutes = int((user.locked_until - utc_now()).total_seconds() / 60)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"账户已被锁定，请在{remaining_minutes}分钟后重试"
            )
        return False

    @staticmethod
    def handle_failed_login(user, db: Session):
        """处理登录失败"""
        user.failed_login_attempts += 1

        if user.failed_login_attempts >= SecurityManager.MAX_LOGIN_ATTEMPTS:
            user.locked_until = utc_now() + timedelta(
                minutes=SecurityManager.LOCKOUT_DURATION_MINUTES
            )
            logger.warning(f"User {user.email} locked due to too many failed login attempts")

        db.commit()

    @staticmethod
    def handle_successful_login(user, request: Request, db: Session):
        """处理登录成功"""
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = utc_now()
        user.last_login_ip = request.client.host
        db.commit()

    @staticmethod
    def create_session(user_id: int, request: Request, db: Session) -> str:
        """创建用户会话"""
        from app.models.user import UserSession

        # 清理过期会话
        db.query(UserSession).filter(
            UserSession.user_id == user_id,
            UserSession.expires_at < utc_now()
        ).delete()

        # 创建新会话
        session_token = SecurityManager.generate_session_token()
        session = UserSession(
            user_id=user_id,
            session_token=session_token,
            ip_address=request.client.host,
            user_agent=request.headers.get('user-agent'),
            expires_at=utc_now() + timedelta(hours=SecurityManager.SESSION_DURATION_HOURS),
            last_activity=utc_now()
        )
        db.add(session)
        db.commit()

        return session_token

    @staticmethod
    def validate_session(session_token: str, db: Session) -> Optional[int]:
        """验证会话并返回用户ID"""
        from app.models.user import UserSession

        session = db.query(UserSession).filter(
            UserSession.session_token == session_token,
            UserSession.expires_at > utc_now()
        ).first()

        if not session:
            return None

        # 更新最后活动时间
        session.last_activity = utc_now()

        # 如果需要，刷新会话过期时间
        if (session.expires_at - utc_now()).total_seconds() < SecurityManager.SESSION_REFRESH_HOURS * 3600:
            session.expires_at = utc_now() + timedelta(hours=SecurityManager.SESSION_DURATION_HOURS)

        db.commit()
        return session.user_id

    @staticmethod
    def log_api_access(
        user_id: Optional[int],
        endpoint: str,
        method: str,
        request: Request,
        response_time_ms: int,
        status_code: int,
        error_message: Optional[str],
        db: Session
    ):
        """记录API访问日志"""
        from app.models.user import APIAccessLog

        log = APIAccessLog(
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            ip_address=request.client.host,
            response_time_ms=response_time_ms,
            status_code=status_code,
            error_message=error_message
        )
        db.add(log)
        db.commit()

# XSS防护函数
def sanitize_html(text: str) -> str:
    """清理HTML内容，防止XSS攻击"""

    allowed_tags = {"p", "br", "strong", "em", "u", "a", "ul", "ol", "li", "blockquote", "code", "pre"}
    allowed_attributes = {"a": {"href", "title"}}
    allowed_protocols = {"http", "https", "mailto"}

    class _Sanitizer(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_starttag(self, tag, attrs):
            if tag not in allowed_tags:
                return

            cleaned_attrs = []
            for name, value in attrs:
                if name not in allowed_attributes.get(tag, set()) or value is None:
                    continue

                if name == "href":
                    parsed = urlparse(value)
                    scheme = parsed.scheme.lower()
                    if scheme and scheme not in allowed_protocols:
                        continue
                    if scheme == "javascript":
                        continue

                cleaned_attrs.append((name, escape(value, quote=True)))

            attr_text = "".join(f' {attr}="{val}"' for attr, val in cleaned_attrs)
            self.parts.append(f"<{tag}{attr_text}>")

        def handle_endtag(self, tag):
            if tag in allowed_tags:
                self.parts.append(f"</{tag}>")

        def handle_startendtag(self, tag, attrs):
            if tag not in allowed_tags:
                return
            # reuse start tag handling for simplicity
            self.handle_starttag(tag, attrs)
            if tag not in {"br"}:  # treat as self-closing only for void tags
                self.parts.append(f"</{tag}>")

        def handle_data(self, data):
            self.parts.append(escape(data))

        def handle_entityref(self, name):
            self.parts.append(f"&{name};")

        def handle_charref(self, name):
            self.parts.append(f"&#{name};")

        def get_data(self):
            return "".join(self.parts)

    sanitizer = _Sanitizer()
    sanitizer.feed(text or "")
    sanitizer.close()
    return sanitizer.get_data()

# SQL注入防护
def validate_sql_identifier(identifier: str) -> bool:
    """验证SQL标识符，防止SQL注入"""
    # 只允许字母、数字和下划线
    pattern = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
    return bool(pattern.match(identifier))

# 文件上传验证
def validate_file_upload(filename: str, content_type: str, max_size_mb: int = 50) -> tuple[bool, str]:
    """验证文件上传"""
    # 允许的文件类型
    ALLOWED_EXTENSIONS = {'.pdf', '.txt', '.doc', '.docx', '.ris', '.bib', '.json', '.xml', '.rdf'}
    ALLOWED_CONTENT_TYPES = {
        'application/pdf',
        'text/plain',
        'application/msword',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/json',
        'text/xml',
        'application/xml'
    }

    # 检查文件扩展名
    import os
    _, ext = os.path.splitext(filename)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        return False, f"不允许的文件类型: {ext}"

    # 检查Content-Type
    if content_type not in ALLOWED_CONTENT_TYPES:
        return False, f"不允许的Content-Type: {content_type}"

    return True, "文件验证通过"

# CSRF保护
class CSRFProtect:
    """CSRF保护"""

    @staticmethod
    def generate_csrf_token() -> str:
        """生成CSRF令牌"""
        return secrets.token_urlsafe(32)

    @staticmethod
    def validate_csrf_token(token: str, session_token: str) -> bool:
        """验证CSRF令牌"""
        # 这里可以实现更复杂的验证逻辑
        return token == session_token

# 加密工具
class EncryptionUtil:
    """数据加密工具"""

    @staticmethod
    def encrypt_sensitive_data(data: str, key: str) -> str:
        """加密敏感数据"""
        from cryptography.fernet import Fernet
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.encrypt(data.encode()).decode()

    @staticmethod
    def decrypt_sensitive_data(encrypted_data: str, key: str) -> str:
        """解密敏感数据"""
        from cryptography.fernet import Fernet
        f = Fernet(key.encode() if isinstance(key, str) else key)
        return f.decrypt(encrypted_data.encode()).decode()

# 导出安全管理实例
security_manager = SecurityManager()
