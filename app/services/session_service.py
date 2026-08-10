"""
SessionService — MySQL 持久化会话和消息，内存作缓存加速。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.core.logger import get_logger

logger = get_logger(__name__)


def _conn():
    """MySQL 连接。"""
    import pymysql
    from app.core.config import get_settings
    s = get_settings().mysql
    return pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                           password=s.password, database=s.database, charset="utf8mb4")


class SessionService:

    async def create(self, user_id: int) -> dict:
        sid = f"sess_{uuid.uuid4().hex[:16]}"
        now = datetime.now()
        try:
            c = _conn(); cur = c.cursor()
            cur.execute(
                "INSERT INTO conversation (user_id, session_id, status, created_at, updated_at) "
                "VALUES (%s, %s, 'active', %s, %s)",
                (user_id, sid, now, now))
            c.commit(); c.close()
        except Exception as e:
            logger.error("session_create_failed", error=str(e))
        return {"session_id": sid, "created_at": now.isoformat()}

    async def get(self, session_id: str, user_id: int) -> dict | None:
        try:
            c = _conn(); cur = c.cursor()
            cur.execute(
                "SELECT session_id, title, status, created_at FROM conversation "
                "WHERE session_id=%s AND user_id=%s", (session_id, user_id))
            row = cur.fetchone(); c.close()
            if not row:
                return None
            return {"session_id": row[0], "title": row[1], "status": row[2],
                    "created_at": row[3].isoformat() if row[3] else None}
        except Exception as e:
            logger.error("session_get_failed", error=str(e))
            return None

    async def add_message(self, session_id: str, role: str, content: str, token_usage: int | None = None) -> None:
        """写入 MySQL + 更新 conversation.updated_at。"""
        try:
            now = datetime.now()
            c = _conn(); cur = c.cursor()
            cur.execute(
                "INSERT INTO conversation_message (session_id, role, content, token_usage, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (session_id, role, content, token_usage, now))
            cur.execute(
                "UPDATE conversation SET updated_at=%s WHERE session_id=%s",
                (now, session_id))
            c.commit(); c.close()
        except Exception as e:
            logger.error("message_save_failed", error=str(e))

    async def get_messages(self, session_id: str, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        """从 MySQL 读取消息（分页）。同时校验 user_id 隔离。"""
        try:
            c = _conn(); cur = c.cursor()
            # 校验会话属于该用户
            cur.execute(
                "SELECT user_id FROM conversation WHERE session_id=%s", (session_id,))
            row = cur.fetchone()
            if not row or row[0] != user_id:
                c.close()
                return {"items": [], "total": 0, "page": page, "page_size": page_size}

            cur.execute(
                "SELECT COUNT(*) FROM conversation_message WHERE session_id=%s",
                (session_id,))
            total = cur.fetchone()[0]

            offset = (page - 1) * page_size
            cur.execute(
                "SELECT role, content, created_at FROM conversation_message "
                "WHERE session_id=%s ORDER BY created_at ASC LIMIT %s OFFSET %s",
                (session_id, page_size, offset))
            items = [{"role": r[0], "content": r[1], "created_at": r[2].isoformat() if r[2] else None}
                     for r in cur.fetchall()]
            c.close()
            return {"items": items, "total": total, "page": page, "page_size": page_size}
        except Exception as e:
            logger.error("messages_load_failed", error=str(e))
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    async def list_user_sessions(self, user_id: int, page: int = 1, page_size: int = 20) -> dict:
        """从 MySQL 列出会话。"""
        try:
            c = _conn(); cur = c.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM conversation WHERE user_id=%s", (user_id,))
            total = cur.fetchone()[0]

            offset = (page - 1) * page_size
            cur.execute(
                "SELECT session_id, title, status, created_at FROM conversation "
                "WHERE user_id=%s ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                (user_id, page_size, offset))
            items = [{"session_id": r[0], "title": r[1], "status": r[2],
                      "created_at": r[3].isoformat() if r[3] else None}
                     for r in cur.fetchall()]
            c.close()
            return {"items": items, "total": total, "page": page, "page_size": page_size}
        except Exception as e:
            logger.error("sessions_list_failed", error=str(e))
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    async def delete(self, session_id: str, user_id: int) -> bool:
        try:
            c = _conn(); cur = c.cursor()
            cur.execute(
                "SELECT user_id FROM conversation WHERE session_id=%s", (session_id,))
            row = cur.fetchone()
            if not row or row[0] != user_id:
                c.close(); return False
            cur.execute("DELETE FROM conversation_message WHERE session_id=%s", (session_id,))
            cur.execute("DELETE FROM conversation WHERE session_id=%s", (session_id,))
            c.commit(); c.close()
            return True
        except Exception as e:
            logger.error("session_delete_failed", error=str(e))
            return False
