"""
/api/v1/chat — Agent 对话接口
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from starlette.responses import StreamingResponse

from app.core.deps import get_current_user_id, get_trace_id
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.common import APIResponse
from app.services.chat_service import ChatService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["chat"])

# 全局服务实例
_chat_service = ChatService()


@router.post("/chat", response_model=APIResponse[ChatResponse])
async def chat(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    trace_id: str = Depends(get_trace_id),
) -> APIResponse[ChatResponse]:
    """普通问答：执行一次完整 Agent Workflow。

    流程：
        API → ChatService → LangGraph Workflow → Response

    Workflow 路径：
        Safety Check → Intent Classify → Context Load →
        Query Router → [RAG / Tool / Safe Reply] →
        Answer Generate → Output Safety → Memory Update
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    logger.info("chat_request", session_id=req.session_id, trace_id=trace_id, user_id=user_id)

    result = await _chat_service.run(
        user_id=str(user_id),
        session_id=req.session_id,
        message=req.message.strip(),
        trace_id=trace_id,
    )

    return APIResponse(
        data=ChatResponse(
            answer=result["answer"],
            trace_id=result["trace_id"],
            citations=result.get("citations", []),
        ),
    )


@router.post("/chat/resume")
async def chat_resume(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    trace_id: str = Depends(get_trace_id),
):
    """恢复 Human-in-the-loop：用户确认/取消操作。

    前端 PendingAction 点确认/取消时调此接口。
    """
    from langgraph.types import Command

    is_confirm = req.message.strip() in ("确认", "确定", "好的", "可以", "是", "提交", "yes", "ok")
    command = Command(resume={"confirm": is_confirm, "message": req.message})
    result = await _chat_service._graph.ainvoke(
        command,
        config={"configurable": {"thread_id": req.session_id}},
    )
    answer = result.get("response", "")
    return APIResponse(data=ChatResponse(answer=answer, trace_id=trace_id, citations=result.get("citations", [])))


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    user_id: int = Depends(get_current_user_id),
    trace_id: str = Depends(get_trace_id),
):
    """SSE 流式问答：实时返回 Agent 生成过程。

    事件类型：
    - start: 请求开始
    - node: Agent 节点状态
    - token: 流式文本
    - tool_call: Tool 调用
    - tool_result: Tool 结果
    - human_confirm_required: 等待用户确认
    - error: 错误
    - heartbeat: 心跳
    - end: 请求结束
    """
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")

    async def event_generator():
        async for event in _chat_service.run_stream(
            user_id=str(user_id),
            session_id=req.session_id,
            message=req.message.strip(),
            device_type=req.device_type,
            trace_id=trace_id,
        ):
            data = json.dumps(event["data"], ensure_ascii=False)
            yield f"event: {event['event']}\ndata: {data}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
