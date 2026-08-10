"""
通用响应 Schema。
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """统一 API 响应格式。"""

    code: int = Field(default=0, description="状态码，0 表示成功")
    message: str = Field(default="success", description="提示信息")
    data: T | None = Field(default=None, description="响应数据")


class PaginatedData(BaseModel, Generic[T]):
    """分页数据容器。"""

    items: list[T] = Field(default_factory=list)
    total: int = Field(default=0)
    page: int = Field(default=1)
    page_size: int = Field(default=20)


class PaginatedResponse(BaseModel, Generic[T]):
    """分页响应。"""

    code: int = Field(default=0)
    message: str = Field(default="success")
    data: PaginatedData[T]
