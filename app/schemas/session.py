"""
Session 请求/响应 Schema。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SessionCreateRequest(BaseModel):
    """创建会话 — user_id 从 JWT 解析，无需传入。"""
    pass


class SessionResponse(BaseModel):
    """会话信息。"""

    session_id: str
    title: str | None = None
    summary: str | None = None
    status: str = "active"
    created_at: datetime | None = None


class MessageItem(BaseModel):
    """消息条目。"""

    role: str
    content: str
    created_at: datetime | None = None
