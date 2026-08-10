"""transfer_human — 转人工客服 Tool（需 Human Confirm）"""

from __future__ import annotations

import asyncio

from app.core.logger import get_logger

logger = get_logger(__name__)


def _create_support_ticket(user_id: int, session_id: str, username: str, query: str) -> dict:
    """同步写入 support_ticket 表。"""
    import pymysql
    from app.core.config import get_settings

    s = get_settings().mysql
    conn = pymysql.connect(
        host="127.0.0.1", port=s.port, user=s.user,
        password=s.password, database=s.database,
        charset="utf8mb4", connect_timeout=3,
    )
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO support_ticket (user_id, session_id, username, query, status) "
            "VALUES (%s, %s, %s, %s, 'pending')",
            (user_id, session_id, username, query),
        )
        conn.commit()
        return {"id": cur.lastrowid, "status": "pending"}
    finally:
        conn.close()


class TransferHumanTool:
    """转人工客服。写操作，需 Human-in-the-loop 确认。"""

    def __init__(self) -> None:
        self.name = "transfer_human"
        self.description = "将当前会话转接人工客服，携带问题摘要和历史上下文。"
        self.requires_confirmation = True
        self.input_schema = {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "转人工原因"},
                "summary": {"type": "string", "description": "AI 对话摘要"},
            },
            "required": ["reason"],
        }

    async def execute(self, user_id: str, reason: str = "", summary: str = "",
                      session_id: str = "", username: str = "") -> dict:
        logger.info("transfer_human_execute", user_id=user_id, session_id=session_id)
        try:
            result = await asyncio.to_thread(
                _create_support_ticket,
                int(user_id), session_id, username or "用户", summary or reason or "用户请求人工客服",
            )
            return {"ticket_id": str(result["id"]), "status": result["status"]}
        except Exception as e:
            logger.error("transfer_human_db_error", error=str(e))
            return {"ticket_id": "error", "status": "failed", "error": str(e)}


transfer_human_tool = TransferHumanTool()
