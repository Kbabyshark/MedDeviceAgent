"""保修记录 Schema。"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field


class WarrantyCreate(BaseModel):
    """新增保修记录。"""

    device_sn: str = Field(..., max_length=64)
    user_id: int
    start_date: date | None = None
    end_date: date | None = None
    problem_desc: str | None = Field(default=None, max_length=2000)
    status: str = Field(default="valid", pattern=r"^(valid|expired)$")


class WarrantyUpdate(BaseModel):
    """更新保修记录（全部字段可选）。"""

    device_sn: str | None = Field(default=None, max_length=64)
    user_id: int | None = None
    start_date: date | None = None
    end_date: date | None = None
    problem_desc: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, pattern=r"^(valid|expired)$")


class WarrantyItem(BaseModel):
    """保修记录条目。"""

    id: int
    device_sn: str
    user_id: int
    start_date: date | None = None
    end_date: date | None = None
    problem_desc: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
