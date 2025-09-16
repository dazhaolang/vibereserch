"""
API超时中间件
防止API请求无限等待，确保快速失败响应
"""

import asyncio
import time
from typing import Callable
from fastapi import Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class TimeoutMiddleware(BaseHTTPMiddleware):
    """API超时保护中间件"""

    def __init__(self, app, timeout: int = 30):
        super().__init__(app)
        self.timeout = timeout

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求超时"""
        start_time = time.time()

        try:
            # 使用asyncio.wait_for设置超时
            response = await asyncio.wait_for(
                call_next(request),
                timeout=self.timeout
            )

            # 记录响应时间
            process_time = time.time() - start_time
            response.headers["X-Process-Time"] = str(process_time)

            return response

        except asyncio.TimeoutError:
            # 超时处理
            process_time = time.time() - start_time
            print(f"⚠️ API超时: {request.method} {request.url.path} - {process_time:.2f}s")

            return JSONResponse(
                status_code=504,
                content={
                    "detail": "Request timeout",
                    "timeout": self.timeout,
                    "path": str(request.url.path),
                    "method": request.method
                }
            )

        except Exception as e:
            # 其他异常处理
            process_time = time.time() - start_time
            print(f"❌ API异常: {request.method} {request.url.path} - {str(e)}")

            return JSONResponse(
                status_code=500,
                content={
                    "detail": f"Internal server error: {str(e)}",
                    "path": str(request.url.path),
                    "method": request.method
                }
            )