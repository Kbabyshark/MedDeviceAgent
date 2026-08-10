"""
FastAPI 依赖注入模块。

提供请求级单例：数据库 session、Redis 客户端、当前用户等。
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException, Request

from app.core.security import decode_access_token


async def get_current_user_id(
    request: Request,
    authorization: str = Header(..., description="Bearer <token>"),
) -> int:
    """从 JWT Token 中解析 user_id。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
        return int(payload["sub"])
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e


async def require_admin(
    request: Request,
    authorization: str = Header(..., description="Bearer <token>"),
) -> int:
    """要求管理员权限。

    从 JWT Token 解析 user_id + role。
    仅 admin 角色可访问。
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
        role = payload.get("role", "user")

        if role != "admin":
            raise HTTPException(status_code=403, detail="需要管理员权限")

        return user_id
    except (ValueError, KeyError, TypeError) as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e
    except HTTPException:
        raise


async def get_trace_id(request: Request) -> str:
    """获取或生成 trace_id。"""
    return getattr(request.state, "trace_id", "")
