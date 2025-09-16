"""
统一异常处理系统
提供标准化的错误定义和处理机制
"""

from fastapi import HTTPException, status
from typing import Dict, Any, Optional
from enum import Enum
import traceback
from datetime import datetime
from loguru import logger

class ErrorCode(Enum):
    """标准错误码定义"""

    # 认证相关 (1000-1099)
    INVALID_CREDENTIALS = "AUTH_1001"
    TOKEN_EXPIRED = "AUTH_1002"
    INSUFFICIENT_PERMISSIONS = "AUTH_1003"
    ACCOUNT_DISABLED = "AUTH_1004"
    EMAIL_ALREADY_EXISTS = "AUTH_1005"
    USERNAME_ALREADY_EXISTS = "AUTH_1006"

    # 用户相关 (1100-1199)
    USER_NOT_FOUND = "USER_1101"
    INVALID_USER_DATA = "USER_1102"
    MEMBERSHIP_LIMIT_EXCEEDED = "USER_1103"
    UPGRADE_REQUIRED = "USER_1104"

    # 项目相关 (1200-1299)
    PROJECT_NOT_FOUND = "PROJECT_1201"
    PROJECT_ACCESS_DENIED = "PROJECT_1202"
    PROJECT_NAME_EXISTS = "PROJECT_1203"
    INVALID_PROJECT_STATUS = "PROJECT_1204"
    PROJECT_LIMIT_EXCEEDED = "PROJECT_1205"

    # 文献相关 (1300-1399)
    LITERATURE_NOT_FOUND = "LITERATURE_1301"
    INVALID_LITERATURE_DATA = "LITERATURE_1302"
    LITERATURE_LIMIT_EXCEEDED = "LITERATURE_1303"
    PARSING_FAILED = "LITERATURE_1304"
    DUPLICATE_LITERATURE = "LITERATURE_1305"

    # 任务相关 (1400-1499)
    TASK_NOT_FOUND = "TASK_1401"
    TASK_ALREADY_RUNNING = "TASK_1402"
    TASK_FAILED = "TASK_1403"
    INVALID_TASK_STATUS = "TASK_1404"

    # AI服务相关 (1500-1599)
    AI_SERVICE_UNAVAILABLE = "AI_1501"
    AI_QUOTA_EXCEEDED = "AI_1502"
    AI_RESPONSE_INVALID = "AI_1503"
    AI_PROCESSING_FAILED = "AI_1504"

    # 文件相关 (1600-1699)
    FILE_NOT_FOUND = "FILE_1601"
    FILE_TOO_LARGE = "FILE_1602"
    INVALID_FILE_TYPE = "FILE_1603"
    FILE_UPLOAD_FAILED = "FILE_1604"
    FILE_PROCESSING_FAILED = "FILE_1605"

    # 系统相关 (1700-1799)
    DATABASE_ERROR = "SYSTEM_1701"
    REDIS_ERROR = "SYSTEM_1702"
    EXTERNAL_API_ERROR = "SYSTEM_1703"
    RATE_LIMIT_EXCEEDED = "SYSTEM_1704"
    MAINTENANCE_MODE = "SYSTEM_1705"

    # 业务逻辑相关 (1800-1899)
    INVALID_OPERATION = "BUSINESS_1801"
    WORKFLOW_ERROR = "BUSINESS_1802"
    DATA_INCONSISTENCY = "BUSINESS_1803"
    VALIDATION_FAILED = "BUSINESS_1804"
    PROCESSING_ERROR = "BUSINESS_1805"  # 添加缺失的处理错误

class ApplicationError(Exception):
    """应用程序基础异常类"""

    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        http_status: int = 500
    ):
        self.error_code = error_code
        self.message = message
        self.details = details or {}
        self.http_status = http_status
        super().__init__(message)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "timestamp": datetime.utcnow().isoformat()
        }

class ValidationError(ApplicationError):
    """验证错误"""

    def __init__(self, message: str, field_errors: Optional[Dict[str, str]] = None):
        super().__init__(
            ErrorCode.VALIDATION_FAILED,
            message,
            {"field_errors": field_errors or {}},
            400
        )

class AuthenticationError(ApplicationError):
    """认证错误"""

    def __init__(self, error_code: ErrorCode, message: str):
        super().__init__(error_code, message, {}, 401)

class AuthorizationError(ApplicationError):
    """授权错误"""

    def __init__(self, message: str = "权限不足"):
        super().__init__(
            ErrorCode.INSUFFICIENT_PERMISSIONS,
            message,
            {},
            403
        )

class NotFoundError(ApplicationError):
    """资源不存在错误"""

    def __init__(self, resource_type: str, resource_id: Any):
        super().__init__(
            ErrorCode.PROJECT_NOT_FOUND,  # 根据资源类型选择合适的错误码
            f"{resource_type}不存在: {resource_id}",
            {"resource_type": resource_type, "resource_id": str(resource_id)},
            404
        )

class BusinessLogicError(ApplicationError):
    """业务逻辑错误"""

    def __init__(self, error_code: ErrorCode, message: str, details: Optional[Dict] = None):
        super().__init__(error_code, message, details, 400)

class ExternalServiceError(ApplicationError):
    """外部服务错误"""

    def __init__(self, service_name: str, message: str, status_code: Optional[int] = None):
        super().__init__(
            ErrorCode.EXTERNAL_API_ERROR,
            f"{service_name}服务错误: {message}",
            {"service_name": service_name, "external_status_code": status_code},
            502
        )

class AIServiceError(ApplicationError):
    """AI服务错误"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            ErrorCode.AI_PROCESSING_FAILED,
            message,
            details or {},
            502
        )

# ============================================
# 错误处理装饰器
# ============================================

def handle_exceptions(error_code: ErrorCode = None):
    """
    统一异常处理装饰器
    将应用程序异常转换为标准HTTP响应
    """
    def decorator(func):
        import functools

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except ApplicationError as e:
                logger.error(f"应用程序错误: {e.error_code.value} - {e.message}")
                raise HTTPException(
                    status_code=e.http_status,
                    detail=e.to_dict()
                )
            except HTTPException:
                # 重新抛出HTTP异常
                raise
            except Exception as e:
                logger.error(f"未处理的异常: {str(e)}")
                logger.error(f"异常堆栈: {traceback.format_exc()}")

                # 如果指定了默认错误码，使用它
                if error_code:
                    error_detail = ApplicationError(
                        error_code,
                        f"处理请求时发生错误: {str(e)}",
                        {"original_error": str(e)}
                    ).to_dict()
                else:
                    error_detail = {
                        "error_code": "SYSTEM_1700",
                        "message": "内部服务器错误",
                        "details": {"original_error": str(e)},
                        "timestamp": datetime.utcnow().isoformat()
                    }

                raise HTTPException(
                    status_code=500,
                    detail=error_detail
                )

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ApplicationError as e:
                logger.error(f"应用程序错误: {e.error_code.value} - {e.message}")
                raise HTTPException(
                    status_code=e.http_status,
                    detail=e.to_dict()
                )
            except HTTPException:
                # 重新抛出HTTP异常
                raise
            except Exception as e:
                logger.error(f"未处理的异常: {str(e)}")
                logger.error(f"异常堆栈: {traceback.format_exc()}")

                # 如果指定了默认错误码，使用它
                if error_code:
                    error_detail = ApplicationError(
                        error_code,
                        f"处理请求时发生错误: {str(e)}",
                        {"original_error": str(e)}
                    ).to_dict()
                else:
                    error_detail = {
                        "error_code": "SYSTEM_1700",
                        "message": "内部服务器错误",
                        "details": {"original_error": str(e)},
                        "timestamp": datetime.utcnow().isoformat()
                    }

                raise HTTPException(
                    status_code=500,
                    detail=error_detail
                )

        # 检查函数是否是异步的
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# ============================================
# 错误工厂
# ============================================

class ErrorFactory:
    """错误工厂类，用于创建标准化的错误实例"""

    @staticmethod
    def authentication_failed(message: str = "认证失败") -> AuthenticationError:
        """创建认证失败错误"""
        return AuthenticationError(ErrorCode.INVALID_CREDENTIALS, message)

    @staticmethod
    def token_expired(message: str = "令牌已过期") -> AuthenticationError:
        """创建令牌过期错误"""
        return AuthenticationError(ErrorCode.TOKEN_EXPIRED, message)

    @staticmethod
    def insufficient_permissions(message: str = "权限不足") -> AuthorizationError:
        """创建权限不足错误"""
        return AuthorizationError(message)

    @staticmethod
    def user_not_found(user_id: Any) -> NotFoundError:
        """创建用户不存在错误"""
        return NotFoundError("用户", user_id)

    @staticmethod
    def project_not_found(project_id: Any) -> NotFoundError:
        """创建项目不存在错误"""
        return NotFoundError("项目", project_id)

    @staticmethod
    def literature_not_found(literature_id: Any) -> NotFoundError:
        """创建文献不存在错误"""
        return NotFoundError("文献", literature_id)

    @staticmethod
    def validation_error(message: str, field_errors: Optional[Dict[str, str]] = None) -> ValidationError:
        """创建验证错误"""
        return ValidationError(message, field_errors)

    @staticmethod
    def ai_service_error(message: str, details: Optional[Dict[str, Any]] = None) -> AIServiceError:
        """创建AI服务错误"""
        return AIServiceError(message, details)

    @staticmethod
    def external_service_error(service_name: str, message: str, status_code: Optional[int] = None) -> ExternalServiceError:
        """创建外部服务错误"""
        return ExternalServiceError(service_name, message, status_code)

    @staticmethod
    def business_logic_error(error_code: ErrorCode, message: str, details: Optional[Dict] = None) -> BusinessLogicError:
        """创建业务逻辑错误"""
        return BusinessLogicError(error_code, message, details)


# ============================================
# FastAPI异常处理器设置
# ============================================

def setup_exception_handlers(app):
    """
    为FastAPI应用设置全局异常处理器
    """
    from fastapi import Request
    from fastapi.responses import JSONResponse

    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError):
        """处理应用程序自定义异常"""
        logger.error(f"应用程序错误 [{exc.error_code.value}]: {exc.message}")
        return JSONResponse(
            status_code=exc.http_status,
            content=exc.to_dict()
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError):
        """处理验证错误"""
        logger.warning(f"验证错误: {exc.message}")
        return JSONResponse(
            status_code=400,
            content=exc.to_dict()
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        """处理值错误"""
        logger.warning(f"值错误: {str(exc)}")
        error = ApplicationError(
            ErrorCode.VALIDATION_FAILED,
            f"输入值无效: {str(exc)}",
            {"original_error": str(exc)},
            400
        )
        return JSONResponse(
            status_code=400,
            content=error.to_dict()
        )

    @app.exception_handler(500)
    async def internal_server_error_handler(request: Request, exc):
        """处理内部服务器错误"""
        logger.error(f"内部服务器错误: {str(exc)}")
        logger.error(f"异常堆栈: {traceback.format_exc()}")

        error = ApplicationError(
            ErrorCode.DATABASE_ERROR,
            "内部服务器错误，请稍后再试",
            {"path": str(request.url), "method": request.method},
            500
        )
        return JSONResponse(
            status_code=500,
            content=error.to_dict()
        )