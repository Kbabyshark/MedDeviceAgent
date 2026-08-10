"""
Ticket 请求/响应 Schema。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class TicketCreateRequest(BaseModel):
    """创建工单草稿请求。"""

    device_sn: str = Field(..., description="设备序列号")
    fault_desc: str = Field(..., min_length=1, max_length=2000, description="故障描述")
    contact_name: str | None = Field(default=None, max_length=64)
    contact_phone: str | None = Field(default=None, max_length=20)
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|urgent)$")


class TicketConfirmRequest(BaseModel):
    """用户确认创建工单。"""

    ticket_id: str = Field(..., description="工单草稿 ID")
    confirm: bool = Field(..., description="true=确认创建, false=取消")


class TicketResponse(BaseModel):
    """工单信息。"""

    ticket_id: str
    device_sn: str
    fault_desc: str
    status: str
    priority: str
    created_at: datetime | None = None
