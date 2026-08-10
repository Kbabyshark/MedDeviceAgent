"""
answer_generate_node

汇总 RAG / Tool / Safe Reply 各路径的结果，生成最终用户回答。
"""

from __future__ import annotations

from app.agent.state import AgentState, get_stream_queue
from app.core.logger import get_logger

logger = get_logger(__name__)


async def answer_generate_node(state: AgentState) -> dict:
    """回答生成节点。

    根据 route_type 处理不同来源的结果：
    - rag → 知识回答（来自 rag_answer_node）
    - tool → 业务结果（来自 tool_execute_node）
    - safe_reply → 安全兜底回复
    - direct → 直接回答

    如果存在 pending_action，在回答末尾附加确认提示。
    """
    response = state.get("response", "")
    route_type = state.get("route_type", "rag")
    pending_action = state.get("pending_action")
    trace_id = state.get("trace_id", "")

    # ---- 有待确认操作 → 追加确认提示 ----
    if pending_action and pending_action.get("status") == "waiting_confirm":
        action_type = pending_action.get("type", "")
        confirm_messages = {
            "create_ticket": (
                "\n\n---\n"
                "📋 **待确认操作：创建维修工单**\n"
                "请回复「确认」提交工单，回复「取消」放弃申请。"
            ),
            "transfer_human": (
                "\n\n---\n"
                "👤 **待确认操作：转人工客服**\n"
                "确认后将为您转接。"
            ),
        }
        response += confirm_messages.get(action_type, "\n\n---\n请确认以上操作。")

    # ---- 闲聊 / direct 模式：LLM 自由回复 ----
    query = state.get("query", "")
    if route_type == "direct" and not response:
        response = await _chitchat_reply(query, state.get("long_term_memory", ""), state.get("session_id", ""), trace_id)

    # ---- 空响应兜底 ----
    if not response:
        response = "您好，请问有什么可以帮您的？"

    # ---- 流式模式：确保发送 None 哨兵结束 SSE 流 ----
    # 无论上游节点（rag_answer / fault_code_lookup / tool_execute）
    # 是否已发送 None，answer_generate 作为所有路径的汇聚点，
    # 统一兜底发送 None，防止 run_stream 永久 hang。
    stream_queue = get_stream_queue()
    if stream_queue is not None:
        await stream_queue.put(None)

    logger.info(
        "answer_generate_done",
        route_type=route_type,
        response_len=len(response),
        has_pending=bool(pending_action),
        trace_id=trace_id,
    )

    return {"response": response}


def _load_recent_for_chitchat(session_id: str) -> str:
    """加载最近 10 条会话消息作为上下文。"""
    if not session_id:
        return ""
    import pymysql
    from app.core.config import get_settings
    s = get_settings().mysql
    try:
        conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                               password=s.password, database=s.database, charset="utf8mb4", connect_timeout=3)
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM conversation_message WHERE session_id=%s ORDER BY created_at DESC LIMIT 10",
            (session_id,),
        )
        rows = cur.fetchall()
        conn.close()
        return "\n".join(f"[{r[0]}]: {r[1][:200]}" for r in reversed(rows))
    except Exception:
        return ""


async def _chitchat_reply(query: str, memory: str, session_id: str, trace_id: str) -> str:
    """闲聊模式：用 LLM 生成简短亲切的回复。"""
    from app.core.llm import ModelType, get_llm_client
    llm = get_llm_client()
    mem_hint = f"已知用户信息：{memory}\n" if memory and memory != "无" else ""

    # 加载最近消息做上下文
    history = _load_recent_for_chitchat(session_id)

    try:
        result = await llm.chat(
            prompt=f"{mem_hint}最近对话：\n{history}\n\n用户最新消息：{query}\n请用售后客服的口吻简短回复（1-2句话）。",
            system="你是医疗设备售后客服助手，回复亲切专业。记得对话历史和用户告诉你的名字。不要编造设备信息。",
            model=ModelType.V3,
            temperature=0.7,
            max_tokens=128,
        )
        return result.content.strip()
    except Exception as e:
        logger.warning("chitchat_reply_failed", error=str(e), trace_id=trace_id)
        return "您好，请问有什么可以帮您的？"
