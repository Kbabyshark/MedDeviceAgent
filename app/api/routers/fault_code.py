"""故障码管理 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File

from app.core.deps import get_current_user_id, require_admin
from app.schemas.common import APIResponse, PaginatedData, PaginatedResponse
from app.schemas.fault_code import FaultCodeCreate, FaultCodeUpdate, FaultCodeItem
from app.services.fault_code_service import FaultCodeService

router = APIRouter(tags=["fault-codes"])
_svc = FaultCodeService()


@router.get("/fault-codes")
async def list_fault_codes(
    search: str = Query(default="", description="搜索关键词"),
    device_model: str = Query(default="", description="设备型号筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
):
    result = await _svc.list(search=search, device_model=device_model, page=page, page_size=page_size)
    return PaginatedResponse(data=PaginatedData(
        items=[FaultCodeItem.model_validate(r).model_dump() for r in result["items"]],
        total=result["total"], page=result["page"], page_size=result["page_size"],
    ))


@router.post("/fault-codes")
async def create_fault_code(body: FaultCodeCreate, user_id: int = Depends(require_admin)):
    obj = await _svc.create(body.model_dump())
    return APIResponse(message="创建成功", data=FaultCodeItem.model_validate(obj).model_dump())


@router.put("/fault-codes/{id}")
async def update_fault_code(id: int, body: FaultCodeUpdate, user_id: int = Depends(require_admin)):
    obj = await _svc.update(id, body.model_dump(exclude_defaults=True))
    if not obj: raise HTTPException(status_code=404, detail="不存在")
    return APIResponse(message="更新成功", data=FaultCodeItem.model_validate(obj).model_dump())


@router.delete("/fault-codes/{id}")
async def delete_fault_code(id: int, user_id: int = Depends(require_admin)):
    ok = await _svc.delete(id)
    if not ok: raise HTTPException(status_code=404, detail="不存在")
    return APIResponse(message="已删除")


@router.post("/fault-codes/import")
async def import_fault_codes(file: UploadFile = File(...), user_id: int = Depends(require_admin)):
    if not file.filename or not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx/.xls 文件")
    content = await file.read()
    result = await _svc.import_excel(content)
    return APIResponse(message=f"导入完成：成功{result['success']}条，跳过{result['skipped']}条", data=result)
