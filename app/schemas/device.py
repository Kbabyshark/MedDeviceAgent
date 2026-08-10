"""设备 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    """新增设备。"""

    device_sn: str = Field(..., max_length=64)
    device_type: str = Field(..., max_length=64)
    version: str | None = Field(default=None, max_length=32)
    user_id: int
    status: str = Field(default="active", pattern=r"^(active|inactive|repairing)$")


class DeviceUpdate(BaseModel):
    """更新设备（全部字段可选）。"""

    device_sn: str | None = Field(default=None, max_length=64)
    device_type: str | None = Field(default=None, max_length=64)
    version: str | None = Field(default=None, max_length=32)
    user_id: int | None = None
    status: str | None = Field(default=None, pattern=r"^(active|inactive|repairing)$")


class DeviceItem(BaseModel):
    """设备条目。"""

    id: int
    device_sn: str
    device_type: str
    version: str | None = None
    user_id: int
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
