"""保修记录管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.deps import get_current_user_id, require_admin
from app.core.logger import get_logger
from app.models.warranty import WarrantyRecord
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.warranty import WarrantyCreate, WarrantyUpdate, WarrantyItem
from pydantic import BaseModel, Field


class WarrantyConfirmRequest(BaseModel):
    """用户确认/取消保修登记。"""
    device_sn: str = Field(..., max_length=64)
    user_id: int
    problem_desc: str = Field(default="")
    confirm: bool = Field(...)

logger = get_logger(__name__)
router = APIRouter(tags=["warranty"])


@router.get("/admin/warranties")
async def list_warranties(
    device_sn: str = Query(default=""),
    status: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user_id: int = Depends(get_current_user_id),
    authorization: str = Header(default=""),
):
    """保修记录列表。"""
    import asyncio, pymysql
    from app.core.config import get_settings

    is_support = False
    if authorization.startswith("Bearer "):
        try:
            from app.core.security import decode_access_token
            is_support = decode_access_token(authorization[7:]).get("role") == "support"
        except Exception: pass

    def _query():
        s = get_settings().mysql
        conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                               password=s.password, database=s.database, charset="utf8mb4", connect_timeout=3)
        try:
            cur = conn.cursor()
            where = []
            params = []
            if device_sn:
                if is_support:
                    where.append("device_sn=%s"); params.append(device_sn)
                else:
                    where.append("device_sn LIKE %s"); params.append(f"%{device_sn}%")
            if status:
                where.append("status=%s"); params.append(status)
            where_clause = ("WHERE " + " AND ".join(where)) if where else ""

            cur.execute(f"SELECT COUNT(*) FROM warranty_record {where_clause}", params)
            total = cur.fetchone()[0]

            offset = (page - 1) * page_size
            cur.execute(
                f"SELECT id, device_sn, user_id, start_date, end_date, problem_desc, status, created_at, updated_at "
                f"FROM warranty_record {where_clause} ORDER BY updated_at DESC LIMIT %s OFFSET %s",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
            return total, [
                {"id": r[0], "device_sn": r[1], "user_id": r[2],
                 "start_date": str(r[3]) if r[3] else None, "end_date": str(r[4]) if r[4] else None,
                 "problem_desc": r[5], "status": r[6],
                 "created_at": r[7].isoformat() if r[7] else None, "updated_at": r[8].isoformat() if r[8] else None}
                for r in rows
            ]
        finally:
            conn.close()

    total, items = await asyncio.to_thread(_query)
    return APIResponse(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/admin/warranties")
async def create_warranty(
    body: WarrantyCreate,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """新增保修记录。"""
    record = WarrantyRecord(
        device_sn=body.device_sn,
        user_id=body.user_id,
        start_date=body.start_date,
        end_date=body.end_date,
        problem_desc=body.problem_desc,
        status=body.status,
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)

    logger.info("warranty_created", id=record.id, device_sn=body.device_sn)
    return APIResponse(message="创建成功", data=WarrantyItem.model_validate(record).model_dump())


@router.put("/admin/warranties/{warranty_id}")
async def update_warranty(
    warranty_id: int,
    body: WarrantyUpdate,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """更新保修记录。"""
    result = await session.execute(
        select(WarrantyRecord).where(WarrantyRecord.id == warranty_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="保修记录不存在")

    updates = body.model_dump(exclude_defaults=True)
    for key, value in updates.items():
        setattr(record, key, value)

    await session.flush()
    await session.refresh(record)

    logger.info("warranty_updated", id=warranty_id)
    return APIResponse(message="更新成功", data=WarrantyItem.model_validate(record).model_dump())


@router.post("/warranty/confirm")
async def confirm_warranty(
    body: WarrantyConfirmRequest,
    _user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """用户确认/取消保修登记。"""
    if not body.confirm:
        return APIResponse(message="已取消")

    from datetime import date
    record = WarrantyRecord(
        device_sn=body.device_sn,
        user_id=body.user_id,
        start_date=date.today(),
        end_date=None,
        problem_desc=body.problem_desc,
        status="valid",
    )
    session.add(record)
    await session.flush()
    await session.refresh(record)

    logger.info("warranty_confirmed", id=record.id, device_sn=body.device_sn, user_id=body.user_id)

    data = WarrantyItem.model_validate(record).model_dump()
    return APIResponse(message="保修记录已创建", data=data)


@router.delete("/admin/warranties/{warranty_id}")
async def delete_warranty(
    warranty_id: int,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """删除保修记录。"""
    result = await session.execute(
        select(WarrantyRecord).where(WarrantyRecord.id == warranty_id)
    )
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="保修记录不存在")

    await session.delete(record)
    await session.flush()

    logger.info("warranty_deleted", id=warranty_id)
    return APIResponse(message="已删除")
