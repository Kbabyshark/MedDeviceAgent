"""
ChatService — 对话业务编排。

Service 层职责：
- 接收用户消息 → 组装 AgentState → 调用 LangGraph Workflow → 返回结果
- 自动保存用户消息和助手回复到 Session
- 不直接调 LLM，不直接写 Prompt
"""

from __future__ import annotations

import uuid
from typing import AsyncIterator

from app.agent.graph import build_graph
from app.agent.state import AgentState
from app.core.logger import get_logger
from app.core.tracer import TraceRecorder, _current_trace
from app.services.session_service import SessionService

logger = get_logger(__name__)


class ChatService:
    """对话服务。

    使用方式：
        service = ChatService()
        result = await service.run(user_id="10001", session_id="sess_xxx", message="设备故障")
    """

    def __init__(self) -> None:
        cp = None
        try:
            from app.memory.checkpoint import get_checkpointer_sync
            cp = get_checkpointer_sync()
        except Exception:
            pass
        if cp is None:
            from langgraph.checkpoint.memory import MemorySaver
            cp = MemorySaver()
        self._graph = build_graph(checkpointer=cp)
        self._checkpointer = cp

    def _start_trace(self, tid: str, sid: str, uid: str, query: str) -> TraceRecorder:
        r = TraceRecorder(tid, sid, uid, query)
        _current_trace.set(r)
        return r

    def _finish_trace(self, r: TraceRecorder, status: str = "success", error: str = ""):
        r.finish(status=status, error=error or None)
        _current_trace.set(None)

    async def run(
        self,
        user_id: str,
        session_id: str,
        message: str,
        trace_id: str = "",
    ) -> dict:
        """执行一次完整的 Agent 对话（非流式）。

        Args:
            user_id: 用户 ID
            session_id: 会话 ID
            message: 用户消息
            trace_id: 链路追踪 ID（可选，自动生成）

        Returns:
            {
                "answer": str,
                "trace_id": str,
                "intent": str,
                "citations": list,
                "pending_action": dict | None,
            }
        """
        trace_id = trace_id or str(uuid.uuid4())
        recorder = self._start_trace(trace_id, session_id, user_id, message)

        # 构建初始 State（pending_action 由 checkpoint 自动恢复）
        initial_state: AgentState = {
            "user_id": user_id,
            "session_id": session_id,
            "trace_id": trace_id,
            "username": "",
            "role": "",
            "query": message,
            "intent": "",
            "intents": [],
            "route_type": "",
            "device_info": {},
            "messages": [],
            "retrieved_docs": [],
            "tool_calls": [],
            "pending_action": {},
            "summary": "",
            "response": "",
            "citations": [],
            "risk_level": "none",
            "error": "",
        }

        logger.info(
            "chat_service_run",
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            query=message[:100],
        )

        try:
            # 调用 LangGraph Workflow（LangSmith 自动追踪）
            result = await self._graph.ainvoke(
                initial_state,
                config={
                    "metadata": {"trace_id": trace_id, "user_id": user_id, "session_id": session_id},
                    "callbacks": [],  # LangSmith 自动注入
                },
            )

            # Checkpoint 自动管理 pending_action，无需手动存储

            # 保存消息到 Session
            session_svc = SessionService()
            await session_svc.add_message(session_id, "user", message)
            answer = result.get("response", "")
            if answer:
                await session_svc.add_message(session_id, "assistant", answer)

            self._finish_trace(recorder)

            return {
                "answer": answer,
                "trace_id": trace_id,
                "intent": result.get("intent", ""),
                "citations": result.get("citations", []),
                "pending_action": result.get("pending_action") or None,
                "risk_level": result.get("risk_level", "none"),
            }

        except Exception as e:
            logger.error("chat_service_error", error=str(e), trace_id=trace_id, exc_info=True)
            self._finish_trace(recorder, status="failed", error=str(e))
            return {
                "answer": "系统处理异常，请稍后重试或转接人工客服。",
                "trace_id": trace_id,
                "intent": "",
                "citations": [],
                "pending_action": None,
                "risk_level": "none",
            }

    async def run_stream(
        self,
        user_id: str,
        session_id: str,
        message: str,
        device_type: str = "",
        trace_id: str = "",
    ) -> AsyncIterator[dict]:
        """SSE 流式问答：ainvoke 后台运行 + stream_queue 驱动 token 流。"""
        import asyncio as _aio

        trace_id = trace_id or str(uuid.uuid4())
        q: _aio.Queue = _aio.Queue()
        from app.agent.state import _stream_ctx
        _stream_ctx.set(q)
        recorder = self._start_trace(trace_id, session_id, user_id, message)

        # Checkpoint 自动恢复 pending_action

        device_info: dict[str, str] = {"device_type": device_type} if device_type else {}
        initial_state: AgentState = {
            "user_id": user_id, "session_id": session_id, "trace_id": trace_id,
            "query": message, "intent": "", "intents": [], "route_type": "",
            "device_info": device_info, "messages": [], "retrieved_docs": [],
            "tool_calls": [], "pending_action": {}, "summary": "", "long_term_memory": "",
            "response": "", "citations": [], "risk_level": "none", "error": "",
        }

        logger.info("stream_start", user_id=user_id, trace_id=trace_id)

        try:
            task = _aio.create_task(self._graph.ainvoke(
                initial_state,
                config={"configurable": {"thread_id": session_id}, "metadata": {"trace_id": trace_id, "user_id": user_id, "session_id": session_id}},
            ))

            while True:
                # 用超时避免 graph 崩了之后永远死等
                try:
                    token = await _aio.wait_for(q.get(), timeout=2.0)
                except _aio.TimeoutError:
                    if task.done():
                        break
                    continue
                if token is None:
                    break
                yield {"event": "token", "data": {"content": token}}

            result = await task
            # 如果 task 中有未捕获异常，这里会抛出
            answer = result.get("response", "")
            citations = result.get("citations", [])
            intent = result.get("intent", "")

            # Checkpoint 自动管理 pending_action

            # 持久化消息
            try:
                svc = SessionService()
                await svc.add_message(session_id, "user", message)
                await svc.add_message(session_id, "assistant", answer)
            except Exception as e:
                logger.warning("message_persist_failed", error=str(e))

            self._finish_trace(recorder)
            yield {"event": "done", "data": {"answer": answer, "citations": citations, "intent": intent}}

        except Exception as e:
            logger.error("stream_error", error=str(e), trace_id=trace_id)
            self._finish_trace(recorder, status="failed", error=str(e))
            yield {"event": "error", "data": {"detail": str(e)}}

