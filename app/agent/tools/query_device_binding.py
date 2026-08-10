"""query_device_binding — 设备绑定查询 Tool"""

from __future__ import annotations

import asyncio

from app.core.logger import get_logger

logger = get_logger(__name__)


def _query_sync(user_id: int) -> list[dict]:
    """同步查 device 表 — 线程池执行。"""
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
            "SELECT id, device_sn, device_type, version, status "
            "FROM device WHERE user_id=%s ORDER BY id DESC LIMIT 50",
            (user_id,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "device_sn": r[1], "device_type": r[2],
                "version": r[3] or "", "status": r[4],
            }
            for r in rows
        ]
    finally:
        conn.close()


class QueryDeviceBindingTool:
    """查询用户绑定的设备列表。"""

    def __init__(self) -> None:
        self.name = "query_device_binding"
        self.description = "查询当前用户绑定的所有设备信息（序列号、型号、状态）。"
        self.requires_confirmation = False
        self.input_schema = {
            "type": "object",
            "properties": {"user_id": {"type": "string", "description": "用户ID"}},
            "required": ["user_id"],
        }

    async def execute(self, user_id: str) -> dict:
        logger.info("query_device_binding_execute", user_id=user_id)
        try:
            rows = await asyncio.to_thread(_query_sync, int(user_id))
        except Exception as e:
            logger.error("query_device_binding_db_error", error=str(e))
            return {"devices": [], "total": 0, "hint": "数据库查询失败"}

        return {"devices": rows, "total": len(rows)}


query_device_binding_tool = QueryDeviceBindingTool()
