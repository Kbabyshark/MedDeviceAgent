"""故障码 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class FaultCodeCreate(BaseModel):
    device_name: str = Field(..., max_length=128)
    device_model: str = Field(..., max_length=64)
    fault_code: str = Field(..., max_length=32)
    fault_symptom: str
    fault_cause: str
    solution: str


class FaultCodeUpdate(BaseModel):
    device_name: str = Field(default="", max_length=128)
    device_model: str = Field(default="", max_length=64)
    fault_code: str = Field(default="", max_length=32)
    fault_symptom: str = Field(default="")
    fault_cause: str = Field(default="")
    solution: str = Field(default="")


class FaultCodeItem(BaseModel):
    id: int
    device_name: str
    device_model: str
    fault_code: str
    fault_symptom: str
    fault_cause: str
    solution: str
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}
