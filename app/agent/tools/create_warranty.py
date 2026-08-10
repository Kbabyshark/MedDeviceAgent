"""create_warranty — 新增保修记录 Tool（需 Human Confirm）"""

from __future__ import annotations

import asyncio

from app.core.logger import get_logger

logger = get_logger(__name__)


def _insert_sync(device_sn: str, user_id: int, problem_desc: str = "") -> dict:
    """同步写入 warranty_record 表 — 线程池执行。"""
    import pymysql
    from datetime import date
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
            "INSERT INTO warranty_record (device_sn, user_id, start_date, end_date, problem_desc, status) "
            "VALUES (%s, %s, %s, %s, %s, 'valid')",
            (device_sn, user_id, date.today(), None, problem_desc or ""),
        )
        conn.commit()
        return {"id": cur.lastrowid, "device_sn": device_sn, "status": "valid"}
    finally:
        conn.close()


class CreateWarrantyTool:
    """新增设备保修记录。写操作，需 Human-in-the-loop 确认。"""

    def __init__(self) -> None:
        self.name = "create_warranty"
        self.description = "为用户设备新增保修记录，包含设备序列号、问题描述。"
        self.requires_confirmation = True
        self.input_schema = {
            "type": "object",
            "properties": {
                "device_sn": {"type": "string", "description": "设备序列号"},
                "user_id": {"type": "string", "description": "用户 ID"},
                "problem_desc": {"type": "string", "description": "设备问题描述"},
            },
            "required": ["device_sn", "user_id"],
        }

    async def execute(self, device_sn: str, user_id: str, problem_desc: str = "") -> dict:
        logger.info("create_warranty_execute", device_sn=device_sn, user_id=user_id)
        try:
            result = await asyncio.to_thread(
                _insert_sync, device_sn, int(user_id), problem_desc,
            )
            return result
        except Exception as e:
            logger.error("create_warranty_db_error", error=str(e))
            return {"error": str(e), "status": "failed"}


create_warranty_tool = CreateWarrantyTool()
