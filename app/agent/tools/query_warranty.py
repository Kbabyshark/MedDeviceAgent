"""query_warranty — 保修查询 Tool"""

from __future__ import annotations

import asyncio

from app.core.logger import get_logger

logger = get_logger(__name__)


def _query_sync(device_sn: str) -> list[dict]:
    """同步查 warranty_record 表 — 线程池执行。"""
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
            "SELECT id, device_sn, user_id, start_date, end_date, problem_desc, status "
            "FROM warranty_record WHERE device_sn=%s ORDER BY id DESC LIMIT 10",
            (device_sn,),
        )
        rows = cur.fetchall()
        return [
            {
                "id": r[0], "device_sn": r[1], "user_id": r[2],
                "start_date": str(r[3]) if r[3] else None,
                "end_date": str(r[4]) if r[4] else None,
                "problem_desc": r[5] or "",
                "status": r[6],
            }
            for r in rows
        ]
    finally:
        conn.close()


class QueryWarrantyTool:
    """查询设备保修信息。"""

    def __init__(self) -> None:
        self.name = "query_warranty"
        self.description = "查询指定设备的保修状态、起止日期、保修范围。"
        self.requires_confirmation = False
        self.input_schema = {
            "type": "object",
            "properties": {"device_sn": {"type": "string", "description": "设备序列号"}},
            "required": ["device_sn"],
        }

    async def execute(self, device_sn: str) -> dict:
        logger.info("query_warranty_execute", device_sn=device_sn)
        try:
            rows = await asyncio.to_thread(_query_sync, device_sn)
        except Exception as e:
            logger.error("query_warranty_db_error", error=str(e))
            return {"device_sn": device_sn, "records": [], "status": "unknown", "hint": "数据库查询失败"}

        if not rows:
            return {"device_sn": device_sn, "records": [], "status": "not_found", "hint": "未找到该设备的保修记录"}

        return {
            "device_sn": device_sn,
            "status": rows[0]["status"],
            "start_date": rows[0]["start_date"],
            "end_date": rows[0]["end_date"],
            "records": rows,
        }


query_warranty_tool = QueryWarrantyTool()
