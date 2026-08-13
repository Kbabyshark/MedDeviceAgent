"""
请求超时中间件。

为每个请求设置最大执行时间，超时自动返回 504。
不同接口设置不同超时：
- chat: 60s
- chat/stream: 120s
- knowledge/upload: 120s
- 其他: 30s
"""

from __future__ import annotations

import asyncio
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.logger import get_logger

logger = get_logger(__name__)

# 各路径前缀对应的超时（秒）
_PATH_TIMEOUTS: dict[str, int] = {
    "/api/v1/chat/stream": 120,
    "/api/v1/chat": 60,
    "/api/v1/admin/knowledge/upload": 120,
    "/api/v1/admin/knowledge/reindex": 300,
    "/api/v1/ws/chat": 3600,  # WebSocket 由自己的超时管理
    "/api/health": 5,
}

DEFAULT_TIMEOUT = 30


class TimeoutMiddleware(BaseHTTPMiddleware):
    """请求超时中间件。

    超时后返回 504 Gateway Timeout。
    """

    async def dispatch(self, request: Request, call_next):
        timeout = DEFAULT_TIMEOUT

        for path_prefix, t in _PATH_TIMEOUTS.items():
            if request.url.path.startswith(path_prefix):
                timeout = t
                break

        try:
            return await asyncio.wait_for(call_next(request), timeout=timeout)
        except asyncio.TimeoutError:
            logger.warning(
                "request_timeout",
                path=request.url.path,
                timeout=timeout,
                trace_id=getattr(request.state, "trace_id", ""),
            )
            return JSONResponse(
                status_code=504,
                content={
                    "code": 504,
                    "message": f"请求超时（{timeout}s），请稍后重试",
                    "data": None,
                },
            )
