"""
AgentState — LangGraph Workflow 全局状态定义。

所有节点通过 State 通信，禁止全局变量、隐式传递。
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 全局状态（LangGraph StateGraph 使用）。"""

    # ---- 会话标识 ----
    user_id: str
    session_id: str
    trace_id: str
    username: str
    role: str                     # 用户角色: admin/support/user

    # ---- 用户输入 ----
    query: str

    # ---- 意图 & 路由 ----
    intent: str                    # 当前意图
    intents: list[dict]            # 多意图 [{intent, confidence}]
    route_type: str                # rag / tool / direct / safe_reply

    # ---- 上下文 ----
    device_info: dict              # 用户设备信息
    messages: Annotated[list[Any], add_messages]  # 对话消息（LangGraph 消息合并）

    # ---- RAG ----
    retrieved_docs: list[dict]     # 召回文档列表

    # ---- Tool ----
    tool_calls: list[dict]         # LLM 生成的工具调用
    pending_action: dict           # 待用户确认的操作

    # ---- 输出 ----
    summary: str                   # 对话摘要
    long_term_memory: str          # 长期记忆（用户偏好等）
    response: str                  # 最终回复
    citations: list[dict]          # 引用来源

    # ---- 安全 ----
    risk_level: str                # none / low / medium / high
    risk_detail: dict | None       # 风险详情 {type, source, reason}

    # ---- 错误 ----
    error: str                     # 当前错误信息（如有）

    # ---- 流式 ----
    # stream_queue 不能序列化，不放入 checkpoint State
    # 改用 contextvars 传递


import contextvars
_stream_ctx: contextvars.ContextVar = contextvars.ContextVar("stream_queue", default=None)


def get_stream_queue():
    """获取当前请求的 stream_queue（不经过 State，避免 checkpoint 序列化失败）。"""
    return _stream_ctx.get()
