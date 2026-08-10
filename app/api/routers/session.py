"""
/api/v1/session — 会话管理接口

所有接口强制 user_id 隔离（从 JWT Token 解析）。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_current_user_id
from app.schemas.common import APIResponse, PaginatedData, PaginatedResponse
from app.schemas.session import MessageItem, SessionCreateRequest, SessionResponse
from app.services.session_service import SessionService
from app.core.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["session"])

_session_service = SessionService()


@router.post("/session/create", response_model=APIResponse[SessionResponse])
async def create_session(
    req: SessionCreateRequest,
    user_id: int = Depends(get_current_user_id),
) -> APIResponse[SessionResponse]:
    """创建新的 Agent 会话。

    user_id 从 JWT Token 解析，无需在请求体中传入。
    """
    result = await _session_service.create(user_id=user_id)
    return APIResponse(
        message="会话创建成功",
        data=SessionResponse(
            session_id=result["session_id"],
            created_at=result.get("created_at"),
        ),
    )


@router.get("/session/{session_id}", response_model=APIResponse[SessionResponse])
async def get_session(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
) -> APIResponse[SessionResponse]:
    """查询会话信息。

    校验 session 所有权（user_id 隔离）。
    """
    session = await _session_service.get(session_id=session_id, user_id=user_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在或无权访问")

    return APIResponse(data=SessionResponse(**session))


@router.get("/session/{session_id}/messages", response_model=PaginatedResponse[MessageItem])
async def get_messages(
    session_id: str,
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    user_id: int = Depends(get_current_user_id),
) -> PaginatedResponse[MessageItem]:
    """获取会话历史消息（分页）。

    user_id 隔离：非会话所有者无法访问。
    消息按时间正序排列。
    """
    result = await _session_service.get_messages(
        session_id=session_id,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )

    items = [
        MessageItem(
            role=m["role"],
            content=m["content"],
            created_at=m.get("created_at"),
        )
        for m in result["items"]
    ]

    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        ),
    )


@router.get("/sessions", response_model=PaginatedResponse[SessionResponse])
async def list_sessions(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
) -> PaginatedResponse[SessionResponse]:
    """列出当前用户的所有会话。

    user_id 隔离：只返回当前用户的会话。
    """
    result = await _session_service.list_user_sessions(
        user_id=user_id,
        page=page,
        page_size=page_size,
    )

    items = [SessionResponse(**s) for s in result["items"]]

    return PaginatedResponse(
        data=PaginatedData(
            items=items,
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        ),
    )


@router.get("/session/{session_id}/support-status")
async def get_session_support_status(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """查询会话是否已转人工（查 support_ticket 表）。"""
    import pymysql
    from app.core.config import get_settings
    s = get_settings().mysql
    conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                           password=s.password, database=s.database, charset="utf8mb4")
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT status FROM support_ticket WHERE session_id=%s ORDER BY id DESC LIMIT 1",
            (session_id,),
        )
        row = cur.fetchone()
        if not row:
            return {"code": 0, "message": "", "data": {"is_support": False, "is_completed": False}}
        status = row[0]
        return {"code": 0, "message": "", "data": {
            "is_support": status in ("pending", "claimed", "processing"),
            "is_completed": status == "completed",
        }}
    finally:
        conn.close()


@router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """删除会话（同时清除关联消息）。

    user_id 隔离：只能删除自己的会话。
    """
    deleted = await _session_service.delete(session_id=session_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在或无权删除")
    return {"code": 0, "message": "已删除", "data": None}
