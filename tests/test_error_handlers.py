"""
错误处理模块单元测试
"""

import pytest
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from unittest.mock import Mock, patch
from app.core.error_handlers import (
    AppException,
    AuthenticationError,
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
    RateLimitError,
    ExternalServiceError,
    DatabaseError,
    ErrorHandler,
    handle_errors
)


class TestExceptions:
    """测试自定义异常类"""

    def test_app_exception(self):
        """测试基础应用异常"""
        exc = AppException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=400,
            detail={"key": "value"}
        )

        assert exc.message == "Test error"
        assert exc.error_code == "TEST_ERROR"
        assert exc.status_code == 400
        assert exc.detail == {"key": "value"}

    def test_authentication_error(self):
        """测试认证异常"""
        exc = AuthenticationError(message="Invalid credentials")
        assert exc.message == "Invalid credentials"
        assert exc.error_code == "AUTH_ERROR"
        assert exc.status_code == 401

    def test_authorization_error(self):
        """测试授权异常"""
        exc = AuthorizationError(message="Forbidden")
        assert exc.message == "Forbidden"
        assert exc.error_code == "PERMISSION_DENIED"
        assert exc.status_code == 403

    def test_resource_not_found_error(self):
        """测试资源不存在异常"""
        exc = ResourceNotFoundError(resource="用户")
        assert exc.message == "用户不存在"
        assert exc.error_code == "RESOURCE_NOT_FOUND"
        assert exc.status_code == 404

    def test_validation_error(self):
        """测试验证异常"""
        exc = ValidationError(message="Invalid data")
        assert exc.message == "Invalid data"
        assert exc.error_code == "VALIDATION_ERROR"
        assert exc.status_code == 422

    def test_rate_limit_error(self):
        """测试频率限制异常"""
        exc = RateLimitError()
        assert exc.error_code == "RATE_LIMIT_EXCEEDED"
        assert exc.status_code == 429

    def test_external_service_error(self):
        """测试外部服务异常"""
        exc = ExternalServiceError(service="OpenAI", message="API timeout")
        assert exc.message == "OpenAI: API timeout"
        assert exc.error_code == "EXTERNAL_SERVICE_ERROR"
        assert exc.status_code == 503

    def test_database_error(self):
        """测试数据库异常"""
        exc = DatabaseError(message="Connection failed")
        assert exc.message == "Connection failed"
        assert exc.error_code == "DATABASE_ERROR"
        assert exc.status_code == 500


class TestErrorHandler:
    """测试错误处理器"""

    def test_create_error_response(self):
        """测试创建错误响应"""
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/test"

        response = ErrorHandler.create_error_response(
            status_code=400,
            message="Bad request",
            error_code="BAD_REQUEST",
            detail={"field": "value"},
            request=mock_request
        )

        assert response.status_code == 400

        import json
        body = json.loads(response.body)
        assert body["success"] is False
        assert body["message"] == "Bad request"
        assert body["error_code"] == "BAD_REQUEST"
        assert body["detail"] == {"field": "value"}
        assert body["path"] == "/api/test"
        assert "error_id" in body
        assert "timestamp" in body

    @pytest.mark.asyncio
    async def test_handle_app_exception(self):
        """测试处理应用异常"""
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/test"

        exc = AppException(
            message="Test error",
            error_code="TEST_ERROR",
            status_code=400
        )

        response = await ErrorHandler.handle_app_exception(mock_request, exc)

        assert response.status_code == 400
        import json
        body = json.loads(response.body)
        assert body["error_code"] == "TEST_ERROR"

    @pytest.mark.asyncio
    async def test_handle_http_exception(self):
        """测试处理HTTP异常"""
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/test"

        exc = HTTPException(status_code=404, detail="Not found")

        response = await ErrorHandler.handle_http_exception(mock_request, exc)

        assert response.status_code == 404
        import json
        body = json.loads(response.body)
        assert body["message"] == "Not found"
        assert body["error_code"] == "HTTP_404"

    @pytest.mark.asyncio
    async def test_handle_validation_exception(self):
        """测试处理验证异常"""
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/test"

        # 模拟验证错误
        exc = Mock(spec=RequestValidationError)
        exc.errors.return_value = [
            {
                "loc": ["body", "email"],
                "msg": "invalid email format",
                "type": "value_error.email"
            },
            {
                "loc": ["body", "age"],
                "msg": "ensure this value is greater than 0",
                "type": "value_error.number.not_gt"
            }
        ]

        response = await ErrorHandler.handle_validation_exception(mock_request, exc)

        assert response.status_code == 422
        import json
        body = json.loads(response.body)
        assert body["error_code"] == "VALIDATION_ERROR"
        assert len(body["detail"]["errors"]) == 2
        assert body["detail"]["errors"][0]["field"] == "body.email"

    @pytest.mark.asyncio
    async def test_handle_database_exception(self):
        """测试处理数据库异常"""
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/test"

        # 测试完整性约束冲突
        exc = IntegrityError("statement", "params", "orig")
        response = await ErrorHandler.handle_database_exception(mock_request, exc)

        assert response.status_code == 409
        import json
        body = json.loads(response.body)
        assert body["error_code"] == "DATABASE_INTEGRITY_ERROR"

        # 测试一般数据库错误
        exc = SQLAlchemyError("Database connection failed")
        response = await ErrorHandler.handle_database_exception(mock_request, exc)

        assert response.status_code == 500
        body = json.loads(response.body)
        assert body["error_code"] == "DATABASE_ERROR"

    @pytest.mark.asyncio
    async def test_handle_generic_exception(self):
        """测试处理通用异常"""
        mock_request = Mock(spec=Request)
        mock_request.url.path = "/api/test"

        exc = Exception("Unexpected error")

        response = await ErrorHandler.handle_generic_exception(mock_request, exc)

        assert response.status_code == 500
        import json
        body = json.loads(response.body)
        assert body["error_code"] == "INTERNAL_SERVER_ERROR"
        assert body["message"] == "服务器内部错误"
        # 不应暴露详细错误信息
        assert "Unexpected error" not in body.get("detail", "")


class TestErrorDecorator:
    """测试错误处理装饰器"""

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_success(self):
        """测试装饰器成功执行"""
        @handle_errors
        async def test_function():
            return {"result": "success"}

        result = await test_function()
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_app_exception(self):
        """测试装饰器处理应用异常"""
        @handle_errors
        async def test_function():
            raise AuthenticationError("Invalid token")

        with pytest.raises(AuthenticationError) as exc_info:
            await test_function()

        assert exc_info.value.message == "Invalid token"

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_database_exception(self):
        """测试装饰器处理数据库异常"""
        @handle_errors
        async def test_function():
            raise IntegrityError("statement", "params", "orig")

        with pytest.raises(DatabaseError) as exc_info:
            await test_function()

        assert exc_info.value.error_code == "DATABASE_ERROR"

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_generic_exception(self):
        """测试装饰器处理通用异常"""
        @handle_errors
        async def test_function():
            raise ValueError("Unexpected error")

        with pytest.raises(AppException) as exc_info:
            await test_function()

        assert exc_info.value.error_code == "OPERATION_FAILED"
        assert exc_info.value.status_code == 500


if __name__ == "__main__":
    pytest.main([__file__, "-v"])