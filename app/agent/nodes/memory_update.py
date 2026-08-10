"""
memory_update_node

更新三级 Memory：Session / Summary / Long-term。

执行顺序：
1. Session Memory — LangGraph Checkpoint 自动保存
2. Summary Memory — 超阈值时生成摘要并持久化
3. Long-term Memory — 提取用户设备偏好、服务记录等持久信息
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.memory.summary import SummaryService
from app.core.llm import ModelType, get_llm_client
from app.core.prompt_manager import get_prompt_manager
from app.core.logger import get_logger

logger = get_logger(__name__)

_summary_service = SummaryService()


async def memory_update_node(state: AgentState) -> dict:
    """记忆更新节点。

    1. Session Memory：由 LangGraph Checkpoint 自动保存（无需手动操作）
    2. Summary Memory：Token 超 4000 或轮数超 15 → 触发摘要压缩
    3. Long-term Memory：提取设备偏好、服务记录 → 持久化到 MySQL user_memory 表
    """
    user_id = state.get("user_id", "")
    session_id = state.get("session_id", "")
    trace_id = state.get("trace_id", "")
    loaded_messages = _load_messages_sync(session_id)

    logger.info("memory_update_start", user_id=user_id, session_id=session_id, trace_id=trace_id, msg_count=len(loaded_messages))

    # ---- Layer 1: Session Memory ----
    # LangGraph Checkpoint 自动在每次 graph execution 结束时保存 State
    # 无需在此手动操作

    # ---- Layer 2: Summary Memory ----
    new_summary = ""
    if _summary_service.should_summarize(loaded_messages):
        to_summarize, keep_recent = _summary_service.get_messages_to_summarize(loaded_messages)
        if to_summarize:
            new_summary = await _summary_service.summarize(to_summarize)
            await _summary_service.save(
                user_id=user_id,
                session_id=session_id,
                summary=new_summary,
                version=_get_next_version(state),
            )
            logger.info(
                "memory_summary_triggered",
                summarized=len(to_summarize),
                kept=len(keep_recent),
                trace_id=trace_id,
            )

    # ---- Layer 3: Long-term Memory ----
    await _extract_long_term_memory(user_id, loaded_messages, trace_id)

    logger.info("memory_update_done", user_id=user_id, trace_id=trace_id)
    return {"summary": new_summary} if new_summary else {}


async def _extract_long_term_memory(user_id: str, messages: list, trace_id: str) -> None:
    """从对话中提取可持久化的用户信息。

    提取类型：
    - device_preference: 用户常用设备型号、偏好设置
    - service_record: 历史服务、维修记录摘要
    - contact_info: 常用联系方式

    写入 MySQL user_memory 表（user_id 隔离）。
    """
    if len(messages) < 3:
        return  # 对话太短，不值得提取

    llm = get_llm_client()

    if llm.mock_mode:
        logger.debug("memory_extract_mock_skip", user_id=user_id, trace_id=trace_id)
        return

    try:
        pm = get_prompt_manager()
        template = pm.get("memory", "v1")

        msg_text = _format_recent_messages(messages, limit=10)
        system, user_prompt = template.render(messages=msg_text)

        result = await llm.chat_structured(
            prompt=user_prompt,
            system=system,
            model=ModelType.V3,
            temperature=0.2,
            max_tokens=512,
        )

        # 提取结果写入 MySQL
        memories = result if isinstance(result, list) else [result] if result else []

        for mem in memories:
            if mem.get("content"):
                await _save_long_term_memory(user_id, mem.get("type", "unknown"), mem.get("content", ""))
                logger.info(
                    "memory_extracted",
                    user_id=user_id,
                    memory_type=mem.get("type", "unknown"),
                    content_len=len(mem.get("content", "")),
                    trace_id=trace_id,
                )

    except Exception as e:
        logger.error("memory_extract_error", error=str(e), user_id=user_id, trace_id=trace_id)


def _format_recent_messages(messages: list, limit: int = 10) -> str:
    """格式化最近的 N 条消息。"""
    recent = messages[-limit:] if len(messages) > limit else messages
    lines = []
    for msg in recent:
        role = ""
        content = ""
        if isinstance(msg, dict):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
        elif hasattr(msg, "content"):
            role = getattr(msg, "role", "unknown")
            content = msg.content
        lines.append(f"[{role}]: {str(content)[:300]}")
    return "\n".join(lines)


def _load_messages_sync(session_id: str) -> list[dict]:
    """从 MySQL 加载会话消息。"""
    import pymysql
    from app.core.config import get_settings
    s = get_settings().mysql
    conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                           password=s.password, database=s.database, charset="utf8mb4", connect_timeout=3)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT role, content FROM conversation_message WHERE session_id=%s ORDER BY created_at ASC",
            (session_id,),
        )
        return [{"role": r[0], "content": r[1]} for r in cur.fetchall()]
    finally:
        conn.close()


async def _save_long_term_memory(user_id: str, mem_type: str, content: str) -> None:
    """保存长期记忆到 MySQL user_memory 表。"""
    import asyncio as _aio

    def _save():
        import pymysql
        from app.core.config import get_settings
        s = get_settings().mysql
        conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                               password=s.password, database=s.database, charset="utf8mb4", connect_timeout=3)
        try:
            cur = conn.cursor()
            cur.execute(
                "INSERT IGNORE INTO user_memory (user_id, memory_type, content) VALUES (%s, %s, %s)",
                (int(user_id), mem_type, content),
            )
            conn.commit()
        finally:
            conn.close()

    try:
        await _aio.to_thread(_save)
    except Exception:
        pass


def _get_next_version(state: AgentState) -> int:
    """计算摘要版本号（递增）。"""
    # 从已有 summary 推断版本号（简化实现）
    existing = state.get("summary", "")
    if isinstance(existing, str) and existing:
        return 2  # 已有摘要 → version = 2
    return 1
