"""
User 请求/响应 Schema。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    """注册请求。"""

    username: str = Field(..., min_length=2, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")
    phone: str | None = Field(default=None, max_length=20, description="手机号")
    email: str | None = Field(default=None, max_length=128, description="邮箱")


class LoginRequest(BaseModel):
    """登录请求。"""

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=64)


class UserResponse(BaseModel):
    """用户信息。"""

    user_id: int
    username: str
    role: str
    phone: str | None = None
    email: str | None = None
    status: int = 1  # 1=正常 0=禁用
    created_at: str | None = None


class UserUpdateRequest(BaseModel):
    """管理员更新用户（禁用/启用/改角色）。"""

    role: str | None = Field(default=None, pattern=r"^(admin|user|support)$")
    status: int | None = Field(default=None, ge=0, le=1)  # 0=禁用 1=正常


class LoginResponse(BaseModel):
    """登录响应。"""

    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: str
    username: str
