"""
Chat 请求/响应 Schema。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """普通问答请求。"""

    session_id: str = Field(..., description="会话 ID")
    message: str = Field(..., min_length=1, max_length=4000, description="用户消息")
    device_type: str = Field(default="", max_length=64, description="设备型号（可选，用于精化检索）")


class ChatResponse(BaseModel):
    """普通问答响应。"""

    answer: str = Field(..., description="Agent 回答")
    trace_id: str = Field(..., description="链路追踪 ID")
    citations: list[dict] = Field(default_factory=list, description="引用来源")


class StreamEvent(BaseModel):
    """SSE 流式事件。"""

    event: str = Field(..., description="事件类型: start/node/token/tool_call/tool_result/human_confirm_required/error/heartbeat/end")
    data: dict = Field(default_factory=dict, description="事件数据")
    timestamp: datetime = Field(default_factory=datetime.now)
