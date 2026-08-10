"""
GET  /api/v1/admin/users       — 用户列表
PUT  /api/v1/admin/user/{id}   — 更新用户（禁用/启用/改角色）

所有接口需管理员权限。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.deps import require_admin
from app.core.logger import get_logger
from app.core.security import hash_password
from app.models.repositories import UserRepository
from app.schemas.user import UserResponse, UserUpdateRequest
from app.schemas.common import APIResponse
from pydantic import BaseModel, Field

logger = get_logger(__name__)
router = APIRouter(tags=["user"])
_user_repo = UserRepository()


@router.get("/admin/users", response_model=APIResponse[dict])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: int | None = Query(default=None, description="1=正常 0=禁用"),
    username: str = Query(default="", description="用户名模糊搜索"),
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[dict]:
    """用户列表（管理员）。"""
    result = await _user_repo.list_users(
        session, page=page, page_size=page_size, status=status, username=username,
    )
    return APIResponse(data=result)


@router.put("/admin/user/{user_id}", response_model=APIResponse[UserResponse])
async def update_user(
    user_id: int,
    req: UserUpdateRequest,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
) -> APIResponse[UserResponse]:
    """更新用户（管理员）。

    可操作：修改角色（admin/user/support）、禁用/启用（status=0/1）。
    """
    if req.role is None and req.status is None:
        raise HTTPException(status_code=400, detail="至少指定 role 或 status")

    user = await _user_repo.update(
        session, user_id, role=req.role, status=req.status,
    )
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    logger.info(
        "user_updated",
        target_user_id=user_id,
        new_role=user["role"],
        new_status=user["status"],
        operator_id=_admin_id,
    )

    return APIResponse(
        message="更新成功",
        data=UserResponse(
            user_id=user["user_id"],
            username=user["username"],
            role=user["role"],
            phone=user["phone"],
            email=user["email"],
            status=user["status"],
            created_at=user["created_at"],
        ),
    )


class ResetPasswordRequest(BaseModel):
    """管理员重置用户密码。"""
    password: str = Field(..., min_length=6, max_length=64)


@router.put("/admin/user/{user_id}/password")
async def reset_password(
    user_id: int,
    req: ResetPasswordRequest,
    _admin_id: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
):
    """管理员重置任意用户密码。"""
    ok = await _user_repo.update_password(session, user_id, hash_password(req.password))
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")

    logger.info("password_reset_by_admin", target_user_id=user_id, operator_id=_admin_id)
    return APIResponse(message="密码已重置")
