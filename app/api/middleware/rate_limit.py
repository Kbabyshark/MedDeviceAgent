"""
Rate Limit 限流中间件。

基于 Redis 滑动窗口实现三维限流：
- 按接口（action）
- 按用户（user_id）
- 按 IP
"""

from __future__ import annotations

import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.redis import RedisKeys, get_redis_client
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# 各接口限流配置（次/分钟）
ACTION_LIMITS: dict[str, int] = {
    "chat": 20,           # 普通聊天 20 次/分钟
    "chat_stream": 20,    # 流式聊天
    "create_ticket": 3,   # 创建工单 3 次/分钟
    "transfer_human": 2,  # 转人工 2 次/分钟
    "create_session": 10, # 创建会话
}


def _get_action_from_path(path: str) -> str:
    """从请求路径提取 action 名称。"""
    path = path.rstrip("/")
    if "/chat/stream" in path:
        return "chat_stream"
    if "/chat" in path:
        return "chat"
    if "/ticket/draft" in path:
        return "create_ticket"
    if "/transfer" in path:
        return "transfer_human"
    if "/session/create" in path:
        return "create_session"
    return "default"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis 滑动窗口限流中间件。

    固定窗口实现：每分钟允许 N 次请求。
    超限返回 429 Too Many Requests。
    """

    async def dispatch(self, request: Request, call_next):
        # 健康检查不限制
        if request.url.path == "/api/health":
            return await call_next(request)

        # 获取限流维度
        action = _get_action_from_path(request.url.path)
        limit = ACTION_LIMITS.get(action, 30)

        # user_id 从 JWT Token 解析（未认证的用 IP）
        user_id = getattr(request.state, "user_id", None) or request.client.host if request.client else "unknown"
        ip = request.client.host if request.client else "unknown"

        try:
            redis = await get_redis_client()
            # 快速检查 Redis 是否可用（1 秒超时）
            import asyncio
            await asyncio.wait_for(redis.ping(), timeout=1.0)
        except Exception:
            # Redis 不可用，直接放行
            return await call_next(request)

        try:
            user_key = RedisKeys.rate_limit(action, str(user_id))
            current = await redis.incr(user_key)
            if current == 1:
                await redis.expire(user_key, 60)
            if current > limit:
                ttl = await redis.ttl(user_key)
                return JSONResponse(status_code=429, content={
                    "code": 429, "message": f"请求频繁，{ttl}秒后重试", "data": None,
                })
        except Exception:
            pass  # Redis 操作失败，放行

        return await call_next(request)
