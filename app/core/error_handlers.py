"""
全局错误处理和异常管理
"""

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from pydantic import ValidationError
from loguru import logger
import traceback
from typing import Any, Dict
from app.core.time_utils import utc_now

class AppException(Exception):
    """应用级基础异常"""
    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 400,
        detail: Any = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.detail = detail
        super().__init__(message)

class AuthenticationError(AppException):
    """认证异常"""
    def __init__(self, message: str = "认证失败", detail: Any = None):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )

class AuthorizationError(AppException):
    """授权异常"""
    def __init__(self, message: str = "无权限访问", detail: Any = None):
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )

class ResourceNotFoundError(AppException):
    """资源不存在异常"""
    def __init__(self, resource: str, detail: Any = None):
        super().__init__(
            message=f"{resource}不存在",
            error_code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )

class ValidationError(AppException):
    """数据验证异常"""
    def __init__(self, message: str = "数据验证失败", detail: Any = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )

class RateLimitError(AppException):
    """频率限制异常"""
    def __init__(self, message: str = "请求频率过高", detail: Any = None):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail
        )

class ExternalServiceError(AppException):
    """外部服务异常"""
    def __init__(self, service: str, message: str = "外部服务异常", detail: Any = None):
        super().__init__(
            message=f"{service}: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=detail
        )

class DatabaseError(AppException):
    """数据库异常"""
    def __init__(self, message: str = "数据库操作失败", detail: Any = None):
        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )

class ErrorHandler:
    """错误处理器"""

    @staticmethod
    def create_error_response(
        status_code: int,
        message: str,
        error_code: str,
        detail: Any = None,
        request: Request = None
    ) -> JSONResponse:
        """创建统一的错误响应"""
        error_id = f"ERR-{utc_now().strftime('%Y%m%d%H%M%S')}"

        response_body = {
            "success": False,
            "message": message,
            "error_code": error_code,
            "error_id": error_id,
            "timestamp": utc_now().isoformat(),
            "path": request.url.path if request else None
        }

        if detail:
            response_body["detail"] = detail

        # 记录错误日志
        logger.error(f"Error {error_id}: {error_code} - {message}")
        if detail:
            logger.error(f"Detail: {detail}")

        return JSONResponse(
            status_code=status_code,
            content=response_body
        )

    @staticmethod
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        """处理应用级异常"""
        return ErrorHandler.create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.error_code,
            detail=exc.detail,
            request=request
        )

    @staticmethod
    async def handle_http_exception(request: Request, exc: HTTPException) -> JSONResponse:
        """处理HTTP异常"""
        return ErrorHandler.create_error_response(
            status_code=exc.status_code,
            message=str(exc.detail),
            error_code=f"HTTP_{exc.status_code}",
            request=request
        )

    @staticmethod
    async def handle_validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        """处理请求验证异常"""
        errors = []
        for error in exc.errors():
            field = ".".join(str(loc) for loc in error["loc"])
            errors.append({
                "field": field,
                "message": error["msg"],
                "type": error["type"]
            })

        return ErrorHandler.create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            message="请求数据验证失败",
            error_code="VALIDATION_ERROR",
            detail={"errors": errors},
            request=request
        )

    @staticmethod
    async def handle_database_exception(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        """处理数据库异常"""
        if isinstance(exc, IntegrityError):
            message = "数据完整性约束冲突"
            error_code = "DATABASE_INTEGRITY_ERROR"
            status_code = status.HTTP_409_CONFLICT
        else:
            message = "数据库操作失败"
            error_code = "DATABASE_ERROR"
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        # 记录详细错误但不暴露给用户
        logger.error(f"Database error: {str(exc)}")
        logger.error(traceback.format_exc())

        return ErrorHandler.create_error_response(
            status_code=status_code,
            message=message,
            error_code=error_code,
            request=request
        )

    @staticmethod
    async def handle_generic_exception(request: Request, exc: Exception) -> JSONResponse:
        """处理通用异常"""
        # 记录详细错误
        logger.error(f"Unexpected error: {str(exc)}")
        logger.error(traceback.format_exc())

        # 生产环境不暴露详细错误信息
        return ErrorHandler.create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            message="服务器内部错误",
            error_code="INTERNAL_SERVER_ERROR",
            request=request
        )

def register_error_handlers(app):
    """注册所有错误处理器到FastAPI应用"""
    from fastapi import FastAPI

    app.add_exception_handler(AppException, ErrorHandler.handle_app_exception)
    app.add_exception_handler(HTTPException, ErrorHandler.handle_http_exception)
    app.add_exception_handler(RequestValidationError, ErrorHandler.handle_validation_exception)
    app.add_exception_handler(SQLAlchemyError, ErrorHandler.handle_database_exception)
    app.add_exception_handler(Exception, ErrorHandler.handle_generic_exception)

    logger.info("Error handlers registered successfully")

# 错误处理装饰器
def handle_errors(func):
    """装饰器：自动处理函数中的异常"""
    import functools
    from typing import Callable

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except AppException:
            raise  # 应用异常直接抛出，由全局处理器处理
        except SQLAlchemyError as e:
            logger.error(f"Database error in {func.__name__}: {str(e)}")
            raise DatabaseError("数据库操作失败", detail=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {str(e)}")
            logger.error(traceback.format_exc())
            raise AppException(
                message="操作失败",
                error_code="OPERATION_FAILED",
                status_code=500,
                detail=str(e)
            )

    return wrapper