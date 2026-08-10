"""设备管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.deps import get_current_user_id, require_admin
from fastapi import Header
from app.core.logger import get_logger
from app.models.device import Device
from app.models.user import User
from app.schemas.common import APIResponse, PaginatedData
from app.schemas.device import DeviceCreate, DeviceUpdate, DeviceItem

logger = get_logger(__name__)
router = APIRouter(tags=["device"])


@router.get("/my/devices")
async def my_devices(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """当前用户的设备列表。"""
    result = await session.execute(
        select(Device).where(Device.user_id == user_id).order_by(Device.updated_at.desc())
    )
    records = result.scalars().all()
    items = []
    for r in records:
        d = DeviceItem.model_validate(r).model_dump()
        d["username"] = ""  # 自己的设备不需要显示用户名
        items.append(d)
    return APIResponse(data={"items": items, "total": len(items)})


@router.get("/admin/devices")
async def list_devices(
    device_sn: str = Query(default=""),
    device_type: str = Query(default=""),
    user_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user_id: int = Depends(get_current_user_id),
    authorization: str = Header(default=""),
):
    """设备列表。"""
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
            where, params = [], []
            if device_sn:
                if is_support:
                    where.append("d.device_sn=%s"); params.append(device_sn)
                else:
                    where.append("d.device_sn LIKE %s"); params.append(f"%{device_sn}%")
            if device_type and not is_support:
                where.append("d.device_type LIKE %s"); params.append(f"%{device_type}%")
            if user_id is not None:
                where.append("d.user_id=%s"); params.append(user_id)
            where_clause = ("WHERE " + " AND ".join(where)) if where else ""

            cur.execute(f"SELECT COUNT(*) FROM device d {where_clause}", params)
            total = cur.fetchone()[0]

            offset = (page - 1) * page_size
            cur.execute(
                f"SELECT d.id, d.device_sn, d.device_type, d.version, d.user_id, d.status, "
                f"d.created_at, d.updated_at, u.username "
                f"FROM device d LEFT JOIN user u ON d.user_id=u.id "
                f"{where_clause} ORDER BY d.updated_at DESC LIMIT %s OFFSET %s",
                params + [page_size, offset],
            )
            rows = cur.fetchall()
            return total, [
                {"id": r[0], "device_sn": r[1], "device_type": r[2], "version": r[3],
                 "user_id": r[4], "status": r[5],
                 "created_at": r[6].isoformat() if r[6] else None,
                 "updated_at": r[7].isoformat() if r[7] else None,
                 "username": r[8] or ""}
                for r in rows
            ]
        finally:
            conn.close()

    total, items = await asyncio.to_thread(_query)
    return APIResponse(data={"items": items, "total": total, "page": page, "page_size": page_size})


@router.post("/admin/devices")
async def create_device(
    body: DeviceCreate,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """新增设备。"""
    # SN 唯一性检测
    exist = await session.execute(
        select(Device).where(Device.device_sn == body.device_sn)
    )
    if exist.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="设备SN已存在")

    device = Device(
        device_sn=body.device_sn,
        device_type=body.device_type,
        version=body.version,
        user_id=body.user_id,
        status=body.status,
    )
    session.add(device)
    await session.flush()
    await session.refresh(device)

    logger.info("device_created", id=device.id, device_sn=body.device_sn)
    return APIResponse(message="创建成功", data=DeviceItem.model_validate(device).model_dump())


@router.put("/admin/devices/{device_id}")
async def update_device(
    device_id: int,
    body: DeviceUpdate,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """更新设备。"""
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    updates = body.model_dump(exclude_defaults=True)
    for key, value in updates.items():
        setattr(device, key, value)

    await session.flush()
    await session.refresh(device)

    logger.info("device_updated", id=device_id)
    return APIResponse(message="更新成功", data=DeviceItem.model_validate(device).model_dump())


@router.delete("/admin/devices/{device_id}")
async def delete_device(
    device_id: int,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """删除设备。"""
    result = await session.execute(
        select(Device).where(Device.id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        raise HTTPException(status_code=404, detail="设备不存在")

    await session.delete(device)
    await session.flush()

    logger.info("device_deleted", id=device_id)
    return APIResponse(message="已删除")
