"""
WebSocket 实时聊天 — 客服与用户直连消息。
连接: ws://host:8000/api/v1/ws/chat/{session_id}?token=xxx
"""

from __future__ import annotations

import json
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["ws"])

# session_id → list of WebSocket connections
_rooms: dict[str, list[WebSocket]] = {}


def _save_message(session_id: str, role: str, content: str):
    """消息持久化到 MySQL。"""
    import pymysql
    from app.core.config import get_settings
    s = get_settings().mysql
    conn = pymysql.connect(
        host="127.0.0.1", port=s.port, user=s.user,
        password=s.password, database=s.database,
        charset="utf8mb4", connect_timeout=3,
    )
    try:
        now = datetime.now()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversation_message (session_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
            (session_id, role, content, now),
        )
        cur.execute("UPDATE conversation SET updated_at=%s WHERE session_id=%s", (now, session_id))
        conn.commit()
    finally:
        conn.close()


@router.websocket("/ws/support-chat/{session_id}")
async def ws_chat(websocket: WebSocket, session_id: str):
    """WebSocket 聊天端点。按 session_id 分组广播。"""
    # 从查询参数获取 JWT token
    token = websocket.query_params.get("token", "")
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub", "")
    except Exception as e:
        logger.warning("ws_auth_failed", error=str(e))
        await websocket.close(code=4001, reason="Invalid token")
        return

    await websocket.accept()
    logger.info("ws_connected", session_id=session_id, user_id=user_id)

    # 加入房间
    if session_id not in _rooms:
        _rooms[session_id] = []
    _rooms[session_id].append(websocket)

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            msg_type = data.get("type", "message")

            if msg_type == "message":
                role = data.get("role", "user")
                content = data.get("content", "")
                if not content:
                    continue

                logger.info("ws_msg_received", session_id=session_id, role=role, content=content[:50])

                # 持久化
                _save_message(session_id, role, content)

                # 广播给房间内其他人
                room_count = len(_rooms.get(session_id, []))
                logger.info("ws_broadcast", session_id=session_id, room_size=room_count)
                payload = json.dumps({
                    "type": "message",
                    "role": role,
                    "content": content,
                    "session_id": session_id,
                }, ensure_ascii=False)

                for conn in _rooms.get(session_id, []):
                    if conn is not websocket:
                        try:
                            await conn.send_text(payload)
                        except Exception:
                            pass

    except WebSocketDisconnect:
        logger.info("ws_disconnected", session_id=session_id, user_id=user_id)
    finally:
        # 离开房间
        room = _rooms.get(session_id, [])
        if websocket in room:
            room.remove(websocket)
        if not room:
            _rooms.pop(session_id, None)
            logger.info("ws_room_empty", session_id=session_id)
