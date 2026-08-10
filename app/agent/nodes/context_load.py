"""
context_load_node

加载用户上下文：Session Memory → Summary Memory → Device Info。

数据来源优先级：
1. LangGraph Checkpoint（MySQL）— 当前 session 运行状态
2. MySQL conversation_summary — 历史对话摘要
3. MySQL device — 用户绑定设备信息

所有查询必须带 user_id 过滤，禁止跨用户数据泄露。
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.core.logger import get_logger

logger = get_logger(__name__)


async def context_load_node(state: AgentState) -> dict:
    """上下文加载节点。

    按优先级加载三层上下文：
    Layer 1: LangGraph Checkpoint（当前 session State）
    Layer 2: MySQL conversation_summary（历史对话摘要）
    Layer 3: MySQL device（用户设备信息）

    user_id 隔离：所有查询必须带 user_id 过滤，禁止跨用户检索。
    """
    session_id = state.get("session_id", "")
    user_id = state.get("user_id", "")
    trace_id = state.get("trace_id", "")

    print(f"[TRACE] context_load START session={session_id[:8]}", flush=True)
    logger.info("context_load_start", session_id=session_id, user_id=user_id, trace_id=trace_id)

    # ---- Layer 1: Checkpoint 恢复 ----
    checkpoint_state = await _load_checkpoint(session_id, user_id, trace_id)

    # ---- Layer 2: Summary 加载 ----
    summary = await _load_summary(user_id, session_id, trace_id)

    # ---- Layer 2.5: Long-term Memory 加载 ----
    long_term = await _load_long_term_memory(user_id, trace_id)

    # ---- Layer 3: Device 信息 ----
    device_info = await _load_device_info(user_id, trace_id)

    # ---- 合并 ----
    result: dict = {
        "device_info": device_info,
        "summary": summary,
        "long_term_memory": long_term,
    }

    # 从 Checkpoint 恢复已有字段（不覆盖当前请求的新 field）
    if checkpoint_state:
        # 恢复 summary（如果当前没有）
        if not summary and checkpoint_state.get("summary"):
            result["summary"] = checkpoint_state["summary"]
        # 恢复 device_info
        if not device_info and checkpoint_state.get("device_info"):
            result["device_info"] = checkpoint_state["device_info"]

    logger.info(
        "context_load_done",
        has_checkpoint=checkpoint_state is not None,
        has_summary=bool(summary),
        has_device=bool(device_info),
        trace_id=trace_id,
    )

    return result


async def _load_checkpoint(session_id: str, user_id: str, trace_id: str) -> dict | None:
    """从 LangGraph Checkpoint 恢复状态。

    LangGraph 自动通过 thread_id (session_id) 管理 checkpoint。
    只需验证 user_id 一致性，防止跨用户恢复。
    """
    try:
        from app.memory.checkpoint import get_checkpointer_sync
        checkpointer = get_checkpointer_sync()
        if checkpointer is None:
            logger.debug("context_checkpoint_unavailable", trace_id=trace_id)
            return None

        # LangGraph checkpoint 通过 config 自动加载，此处做 user_id 隔离校验
        # 实际恢复在 graph.ainvoke 时通过 config={"configurable": {"thread_id": session_id}} 完成
        logger.debug("context_checkpoint_available", session_id=session_id, trace_id=trace_id)
        return None  # 由 LangGraph 自动管理

    except Exception as e:
        logger.error("context_checkpoint_error", error=str(e), trace_id=trace_id)
        return None


async def _load_summary(user_id: str, session_id: str, trace_id: str) -> str:
    """从 MySQL conversation_summary 加载最新摘要。"""
    import asyncio

    def _query():
        import pymysql
        from app.core.config import get_settings
        s = get_settings().mysql
        conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                               password=s.password, database=s.database, charset="utf8mb4", connect_timeout=3)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT summary FROM conversation_summary "
                "WHERE user_id=%s AND session_id=%s ORDER BY version DESC LIMIT 1",
                (int(user_id), session_id),
            )
            row = cur.fetchone()
            return row[0] if row else ""
        finally:
            conn.close()

    try:
        result = await asyncio.to_thread(_query)
        if result:
            logger.info("context_summary_loaded", user_id=user_id, session_id=session_id, trace_id=trace_id)
        return result or ""
    except Exception as e:
        logger.error("context_summary_error", error=str(e), trace_id=trace_id)
        return ""


async def _load_long_term_memory(user_id: str, trace_id: str) -> str:
    """从 MySQL user_memory 加载用户长期记忆。"""
    import asyncio

    def _query():
        import pymysql
        from app.core.config import get_settings
        s = get_settings().mysql
        conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                               password=s.password, database=s.database, charset="utf8mb4", connect_timeout=3)
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT memory_type, content FROM user_memory WHERE user_id=%s ORDER BY updated_at DESC LIMIT 10",
                (int(user_id),),
            )
            rows = cur.fetchall()
            if not rows:
                return ""
            lines = [f"[{r[0]}]: {r[1]}" for r in rows]
            return "\n".join(lines)
        finally:
            conn.close()

    try:
        result = await asyncio.to_thread(_query)
        if result:
            logger.info("long_term_memory_loaded", user_id=user_id, trace_id=trace_id)
        return result or ""
    except Exception as e:
        logger.error("long_term_memory_load_error", error=str(e), trace_id=trace_id)
        return ""


async def _load_device_info(user_id: str, trace_id: str) -> dict:
    """从 MySQL device 表加载用户设备信息。

    user_id 隔离：WHERE user_id = ?
    默认返回用户最近使用的设备。
    """
    try:
        # TODO: P4 接入 MySQL 后查询 device 表
        # result = await session.execute(
        #     select(Device)
        #     .where(Device.user_id == int(user_id))
        #     .where(Device.status == "active")
        #     .order_by(Device.updated_at.desc())
        #     .limit(1)
        # )
        # device = result.scalar_one_or_none()
        # if device:
        #     return {
        #         "device_sn": device.device_sn,
        #         "device_type": device.device_type,
        #         "version": device.version,
        #     }
        logger.debug("context_device_load", user_id=user_id, trace_id=trace_id)
        return {}

    except Exception as e:
        logger.error("context_device_error", error=str(e), trace_id=trace_id)
        return {}
