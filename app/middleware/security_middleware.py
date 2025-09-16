"""
安全中间件
提供API限流、输入验证、XSS防护、CSRF保护等安全功能
"""

import time
import hashlib
import secrets
import re
import html
from typing import Dict, List, Optional, Any
from fastapi import Request, Response, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from loguru import logger
import json
from datetime import datetime, timedelta
from collections import defaultdict, deque
import ipaddress

from app.core.database import redis_client
from app.models.user import User, MembershipType

class RateLimitConfig:
    """限流配置"""
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        concurrent_requests: int = 10,
        burst_size: int = 10
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.concurrent_requests = concurrent_requests
        self.burst_size = burst_size

class AdvancedRateLimiter:
    """高级限流器"""
    
    def __init__(self):
        # 基于用户类型的限流配置
        self.user_limits = {
            MembershipType.FREE: RateLimitConfig(
                requests_per_minute=30,
                requests_per_hour=500,
                concurrent_requests=3,
                burst_size=5
            ),
            MembershipType.PREMIUM: RateLimitConfig(
                requests_per_minute=120,
                requests_per_hour=5000,
                concurrent_requests=10,
                burst_size=20
            ),
            MembershipType.ENTERPRISE: RateLimitConfig(
                requests_per_minute=300,
                requests_per_hour=20000,
                concurrent_requests=50,
                burst_size=100
            )
        }
        
        # 基于端点的特殊限流
        self.endpoint_limits = {
            '/api/literature/collect': RateLimitConfig(
                requests_per_minute=5,
                requests_per_hour=50,
                concurrent_requests=2
            ),
            '/api/analysis/ai-chat': RateLimitConfig(
                requests_per_minute=20,
                requests_per_hour=200,
                concurrent_requests=5
            ),
            '/api/auth/login': RateLimitConfig(
                requests_per_minute=10,
                requests_per_hour=100,
                concurrent_requests=3
            )
        }
        
        # IP黑名单
        self.ip_blacklist = set()
        self.suspicious_ips = defaultdict(int)
    
    async def check_rate_limit(
        self, 
        request: Request, 
        user: Optional[User] = None
    ) -> Optional[HTTPException]:
        """检查限流"""
        client_ip = self._get_client_ip(request)
        endpoint = request.url.path
        
        # 检查IP黑名单
        if client_ip in self.ip_blacklist:
            logger.warning(f"黑名单IP访问: {client_ip}")
            return HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="IP地址已被禁止访问"
            )
        
        # 获取限流配置
        if endpoint in self.endpoint_limits:
            config = self.endpoint_limits[endpoint]
        elif user and user.membership:
            config = self.user_limits[user.membership.membership_type]
        else:
            config = self.user_limits[MembershipType.FREE]  # 默认使用免费用户限制
        
        # 构建Redis key
        user_id = user.id if user else f"ip:{client_ip}"
        minute_key = f"rate_limit:{user_id}:{endpoint}:minute:{int(time.time() // 60)}"
        hour_key = f"rate_limit:{user_id}:{endpoint}:hour:{int(time.time() // 3600)}"
        concurrent_key = f"rate_limit:{user_id}:{endpoint}:concurrent"
        
        try:
            # 检查每分钟限制
            minute_count = await redis_client.incr(minute_key)
            if minute_count == 1:
                await redis_client.expire(minute_key, 60)
            
            if minute_count > config.requests_per_minute:
                await self._record_violation(client_ip, f"超过每分钟限制: {minute_count}")
                return HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"每分钟请求次数超限，限制: {config.requests_per_minute}次/分钟"
                )
            
            # 检查每小时限制
            hour_count = await redis_client.incr(hour_key)
            if hour_count == 1:
                await redis_client.expire(hour_key, 3600)
            
            if hour_count > config.requests_per_hour:
                await self._record_violation(client_ip, f"超过每小时限制: {hour_count}")
                return HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"每小时请求次数超限，限制: {config.requests_per_hour}次/小时"
                )
            
            # 检查并发限制
            concurrent_count = await redis_client.incr(concurrent_key)
            await redis_client.expire(concurrent_key, 30)  # 30秒过期
            
            if concurrent_count > config.concurrent_requests:
                await self._record_violation(client_ip, f"超过并发限制: {concurrent_count}")
                return HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"并发请求数超限，限制: {config.concurrent_requests}个并发"
                )
            
            return None
            
        except Exception as e:
            logger.error(f"限流检查失败: {e}")
            return None  # 限流检查失败时不阻止请求
    
    def _get_client_ip(self, request: Request) -> str:
        """获取客户端真实IP"""
        # 检查代理头部
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    async def _record_violation(self, ip: str, reason: str):
        """记录违规行为"""
        self.suspicious_ips[ip] += 1
        
        # 多次违规则加入黑名单
        if self.suspicious_ips[ip] >= 10:
            self.ip_blacklist.add(ip)
            logger.warning(f"IP {ip} 已加入黑名单，原因: 多次违规")
        
        # 记录到Redis
        violation_key = f"security_violation:{ip}:{int(time.time())}"
        violation_data = {
            "ip": ip,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat(),
            "count": self.suspicious_ips[ip]
        }
        await redis_client.setex(violation_key, 86400, json.dumps(violation_data))

class InputSanitizer:
    """输入清理器"""
    
    @staticmethod
    def sanitize_html(text: str) -> str:
        """HTML转义防止XSS"""
        if not text:
            return text
        return html.escape(text.strip())
    
    @staticmethod
    def sanitize_sql(text: str) -> str:
        """SQL注入防护"""
        if not text:
            return text
        
        # 移除危险的SQL关键词
        dangerous_patterns = [
            r'\b(DROP|DELETE|UPDATE|INSERT|CREATE|ALTER|EXEC|UNION|SELECT)\b',
            r'[\'";]',
            r'--',
            r'/\*.*?\*/',
            r'\bOR\b.*\b=\b',
            r'\bAND\b.*\b=\b'
        ]
        
        sanitized = text
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE)
        
        return sanitized.strip()
    
    @staticmethod
    def validate_file_upload(filename: str, content_type: str, file_size: int) -> Dict[str, Any]:
        """文件上传验证"""
        errors = []
        
        # 文件名验证
        if not filename or '..' in filename or '/' in filename:
            errors.append("文件名不合法")
        
        # 文件扩展名验证
        allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.md', '.csv', '.xlsx']
        if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
            errors.append(f"文件类型不支持，允许的类型: {', '.join(allowed_extensions)}")
        
        # 文件大小验证
        max_size = 100 * 1024 * 1024  # 100MB
        if file_size > max_size:
            errors.append(f"文件过大，最大允许: {max_size // 1024 // 1024}MB")
        
        # MIME类型验证
        allowed_mime_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'text/plain',
            'text/markdown',
            'text/csv',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        ]
        
        if content_type not in allowed_mime_types:
            errors.append(f"MIME类型不支持: {content_type}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    @staticmethod
    def validate_search_query(query: str) -> Dict[str, Any]:
        """搜索查询验证"""
        errors = []
        
        if not query or len(query.strip()) < 2:
            errors.append("查询关键词至少需要2个字符")
        
        if len(query) > 500:
            errors.append("查询关键词过长，最大500字符")
        
        # 检查恶意模式
        malicious_patterns = [
            r'<script.*?>.*?</script>',
            r'javascript:',
            r'vbscript:',
            r'on\w+\s*=',
            r'expression\s*\(',
            r'url\s*\(',
            r'@import'
        ]
        
        for pattern in malicious_patterns:
            if re.search(pattern, query, re.IGNORECASE):
                errors.append("查询包含不安全内容")
                break
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "sanitized_query": InputSanitizer.sanitize_html(query)
        }

class CSRFProtection:
    """CSRF保护"""
    
    def __init__(self):
        self.tokens = {}  # 在生产环境中应该使用Redis
    
    def generate_token(self, user_id: int) -> str:
        """生成CSRF令牌"""
        token = secrets.token_urlsafe(32)
        self.tokens[user_id] = {
            'token': token,
            'created_at': time.time()
        }
        return token
    
    def validate_token(self, user_id: int, token: str) -> bool:
        """验证CSRF令牌"""
        if user_id not in self.tokens:
            return False
        
        stored_data = self.tokens[user_id]
        
        # 检查令牌是否匹配
        if stored_data['token'] != token:
            return False
        
        # 检查令牌是否过期（1小时）
        if time.time() - stored_data['created_at'] > 3600:
            del self.tokens[user_id]
            return False
        
        return True
    
    def cleanup_expired_tokens(self):
        """清理过期令牌"""
        now = time.time()
        expired_users = [
            user_id for user_id, data in self.tokens.items()
            if now - data['created_at'] > 3600
        ]
        
        for user_id in expired_users:
            del self.tokens[user_id]

class SecurityMiddleware(BaseHTTPMiddleware):
    """安全中间件"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = AdvancedRateLimiter()
        self.csrf_protection = CSRFProtection()
        self.input_sanitizer = InputSanitizer()
        
        # 安全头部配置
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Content-Security-Policy": (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline'; "
                "img-src 'self' data: https:; "
                "connect-src 'self' https://api.openai.com https://api.semanticscholar.org"
            ),
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
        }
    
    async def dispatch(self, request: Request, call_next):
        """安全检查和处理"""
        start_time = time.time()
        
        try:
            # 1. IP地址验证
            client_ip = self.rate_limiter._get_client_ip(request)
            if not self._is_valid_ip(client_ip):
                return JSONResponse(
                    status_code=400,
                    content={"detail": "无效的IP地址"}
                )
            
            # 2. 请求大小限制
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 50 * 1024 * 1024:  # 50MB
                return JSONResponse(
                    status_code=413,
                    content={"detail": "请求体过大"}
                )
            
            # 3. User-Agent验证（防止恶意爬虫）
            user_agent = request.headers.get("user-agent", "")
            if not self._is_valid_user_agent(user_agent):
                return JSONResponse(
                    status_code=403,
                    content={"detail": "无效的User-Agent"}
                )
            
            # 4. 获取用户信息（如果有认证）
            user = await self._extract_user_from_request(request)
            
            # 5. 限流检查
            rate_limit_error = await self.rate_limiter.check_rate_limit(request, user)
            if rate_limit_error:
                return JSONResponse(
                    status_code=rate_limit_error.status_code,
                    content={"detail": rate_limit_error.detail}
                )
            
            # 6. CSRF保护（对于状态变更操作）
            if request.method in ["POST", "PUT", "DELETE", "PATCH"]:
                csrf_error = await self._check_csrf_protection(request, user)
                if csrf_error:
                    return csrf_error
            
            # 7. 输入验证和清理
            if request.method in ["POST", "PUT", "PATCH"]:
                sanitized_request = await self._sanitize_request(request)
                if sanitized_request:
                    request = sanitized_request
            
            # 处理请求
            response = await call_next(request)
            
            # 8. 添加安全头部
            for header, value in self.security_headers.items():
                response.headers[header] = value
            
            # 9. 记录安全日志
            await self._log_security_event(request, response, user, time.time() - start_time)
            
            return response
            
        except Exception as e:
            logger.error(f"安全中间件错误: {e}")
            return JSONResponse(
                status_code=500,
                content={"detail": "安全检查失败"}
            )
    
    def _is_valid_ip(self, ip: str) -> bool:
        """验证IP地址格式"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return ip == "unknown"  # 允许未知IP（某些代理情况）
    
    def _is_valid_user_agent(self, user_agent: str) -> bool:
        """验证User-Agent"""
        if not user_agent:
            return False
        
        # 检查恶意User-Agent模式
        malicious_patterns = [
            r'sqlmap',
            r'nikto',
            r'nmap',
            r'masscan',
            r'zmap',
            r'bot.*crawler',
            r'scanner'
        ]
        
        for pattern in malicious_patterns:
            if re.search(pattern, user_agent, re.IGNORECASE):
                return False
        
        return True
    
    async def _extract_user_from_request(self, request: Request) -> Optional[User]:
        """从请求中提取用户信息"""
        try:
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None
            
            # 这里应该调用认证服务验证token
            # 为了简化，暂时返回None
            return None
        except:
            return None
    
    async def _check_csrf_protection(self, request: Request, user: Optional[User]) -> Optional[Response]:
        """检查CSRF保护"""
        if not user:
            return None  # 未认证用户不需要CSRF保护
        
        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            return JSONResponse(
                status_code=403,
                content={"detail": "缺少CSRF令牌"}
            )
        
        if not self.csrf_protection.validate_token(user.id, csrf_token):
            return JSONResponse(
                status_code=403,
                content={"detail": "无效的CSRF令牌"}
            )
        
        return None
    
    async def _sanitize_request(self, request: Request) -> Optional[Request]:
        """清理请求数据"""
        # 这里可以实现请求体的清理和验证
        # 由于FastAPI的限制，实际实现会比较复杂
        return None
    
    async def _log_security_event(
        self, 
        request: Request, 
        response: Response, 
        user: Optional[User], 
        duration: float
    ):
        """记录安全事件"""
        try:
            event_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "client_ip": self.rate_limiter._get_client_ip(request),
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration * 1000,
                "user_id": user.id if user else None,
                "user_agent": request.headers.get("user-agent", ""),
                "referer": request.headers.get("referer", "")
            }
            
            # 记录到Redis（保留7天）
            log_key = f"security_log:{int(time.time())}"
            await redis_client.setex(log_key, 604800, json.dumps(event_data))
            
            # 异常状态码记录
            if response.status_code >= 400:
                alert_key = f"security_alert:{int(time.time())}"
                await redis_client.setex(alert_key, 86400, json.dumps(event_data))
                
        except Exception as e:
            logger.error(f"安全日志记录失败: {e}")

class SecurityValidator:
    """安全验证器"""
    
    @staticmethod
    def validate_email(email: str) -> Dict[str, Any]:
        """邮箱验证"""
        errors = []
        
        if not email:
            errors.append("邮箱地址不能为空")
        elif len(email) > 254:
            errors.append("邮箱地址过长")
        elif not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            errors.append("邮箱格式不正确")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "sanitized_email": email.lower().strip() if email else ""
        }
    
    @staticmethod
    def validate_password(password: str) -> Dict[str, Any]:
        """密码强度验证"""
        errors = []
        score = 0
        
        if not password:
            errors.append("密码不能为空")
            return {"valid": False, "errors": errors, "score": 0}
        
        if len(password) < 8:
            errors.append("密码至少需要8个字符")
        else:
            score += 1
        
        if len(password) > 128:
            errors.append("密码过长，最大128个字符")
        
        if not re.search(r'[a-z]', password):
            errors.append("密码需要包含小写字母")
        else:
            score += 1
        
        if not re.search(r'[A-Z]', password):
            errors.append("密码需要包含大写字母")
        else:
            score += 1
        
        if not re.search(r'\d', password):
            errors.append("密码需要包含数字")
        else:
            score += 1
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            errors.append("密码需要包含特殊字符")
        else:
            score += 1
        
        # 检查常见弱密码
        weak_passwords = [
            'password', '12345678', 'qwerty', 'abc123', 
            'password123', '123456789', 'welcome'
        ]
        if password.lower() in weak_passwords:
            errors.append("密码过于简单，请使用更复杂的密码")
            score = 0
        
        strength_level = "很弱" if score <= 1 else "弱" if score <= 2 else "中等" if score <= 3 else "强" if score <= 4 else "很强"
        
        return {
            "valid": len(errors) == 0 and score >= 3,
            "errors": errors,
            "score": score,
            "strength": strength_level
        }

# 全局实例
rate_limiter = AdvancedRateLimiter()
input_sanitizer = InputSanitizer()
security_validator = SecurityValidator()
csrf_protection = CSRFProtection()