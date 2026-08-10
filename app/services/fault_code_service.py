"""故障码服务：CRUD + Excel 导入。"""

from __future__ import annotations

import io

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session_factory
from app.models.fault_code import FaultCode
from app.core.logger import get_logger

logger = get_logger(__name__)


class FaultCodeService:

    def _db(self) -> AsyncSession:
        return get_session_factory()()

    async def list(self, search: str = "", device_model: str = "",
                   page: int = 1, page_size: int = 20) -> dict:
        db = self._db()
        async with db:
            q = select(FaultCode)
            if search:
                q = q.where(
                    (FaultCode.fault_code.contains(search)) |
                    (FaultCode.device_name.contains(search)) |
                    (FaultCode.fault_symptom.contains(search))
                )
            if device_model:
                q = q.where(FaultCode.device_model.contains(device_model))

            total = (await db.execute(select(func.count()).select_from(q.subquery()))).scalar() or 0
            rows = (await db.execute(q.order_by(FaultCode.id.desc()).offset((page - 1) * page_size).limit(page_size))).scalars().all()
            return {"items": rows, "total": total, "page": page, "page_size": page_size}

    async def create(self, data: dict) -> FaultCode:
        db = self._db()
        async with db:
            obj = FaultCode(**data)
            db.add(obj); await db.commit(); await db.refresh(obj)
            return obj

    async def update(self, id: int, data: dict) -> FaultCode | None:
        db = self._db()
        async with db:
            obj = await db.get(FaultCode, id)
            if not obj: return None
            for k, v in data.items():
                if v: setattr(obj, k, v)
            await db.commit(); await db.refresh(obj)
            return obj

    async def delete(self, id: int) -> bool:
        db = self._db()
        async with db:
            result = await db.execute(delete(FaultCode).where(FaultCode.id == id))
            await db.commit()
            return result.rowcount > 0

    async def import_excel(self, file_bytes: bytes) -> dict:
        """从 Excel 导入故障码。期望列：设备名称,设备型号,故障码,故障现象,故障原因,解决方法。"""
        try:
            import openpyxl
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes))
            ws = wb.active
            rows = list(ws.iter_rows(min_row=2, values_only=True))  # 跳过表头
            total, success, skipped = 0, 0, 0

            db = self._db()
            async with db:
                for row in rows:
                    if not row or not row[0]: continue
                    total += 1
                    name = str(row[0]).strip() if row[0] else ""
                    model = str(row[1]).strip() if len(row) > 1 and row[1] else ""
                    code = str(row[2]).strip() if len(row) > 2 and row[2] else ""
                    if not name or not model or not code:
                        skipped += 1; continue
                    obj = FaultCode(
                        device_name=name, device_model=model, fault_code=code,
                        fault_symptom=str(row[3]).strip() if len(row) > 3 and row[3] else "",
                        fault_cause=str(row[4]).strip() if len(row) > 4 and row[4] else "",
                        solution=str(row[5]).strip() if len(row) > 5 and row[5] else "",
                    )
                    db.add(obj); success += 1
                await db.commit()
            return {"total": total, "success": success, "skipped": skipped}
        except Exception as e:
            logger.error("fault_code_import_failed", error=str(e))
            raise
