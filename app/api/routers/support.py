"""人工客服 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db_session
from app.core.deps import get_current_user_id
from app.core.logger import get_logger
from app.models.support import SupportTicket
from app.schemas.common import APIResponse, PaginatedData

logger = get_logger(__name__)
router = APIRouter(tags=["support"])


class TransferRequest(BaseModel):
    user_id: int
    session_id: str = ""
    username: str = ""
    query: str = ""


class SupportMessage(BaseModel):
    session_id: str
    role: str = "assistant"
    content: str


@router.post("/support/message")
async def send_support_message(req: SupportMessage):
    """客服发送消息到用户会话。"""
    from datetime import datetime
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
            (req.session_id, req.role, req.content, now),
        )
        cur.execute(
            "UPDATE conversation SET updated_at=%s WHERE session_id=%s",
            (now, req.session_id),
        )
        conn.commit()
        return APIResponse(message="已发送")
    finally:
        conn.close()


@router.post("/support/transfer")
async def create_transfer(
    req: TransferRequest,
    session: AsyncSession = Depends(get_db_session),
):
    """用户确认转人工 → 创建 support_ticket。"""
    ticket = SupportTicket(
        user_id=req.user_id,
        session_id=req.session_id,
        username=req.username,
        query=req.query,
        status="pending",
    )
    session.add(ticket)
    # 标记会话为人工模式
    import pymysql
    from app.core.config import get_settings
    s = get_settings().mysql
    conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                           password=s.password, database=s.database, charset="utf8mb4")
    try:
        cur = conn.cursor()
        cur.execute("UPDATE conversation SET is_support=1 WHERE session_id=%s", (req.session_id,))
        conn.commit()
    finally:
        conn.close()
    await session.flush()
    await session.refresh(ticket)
    logger.info("support_transfer_created", ticket_id=ticket.id, user_id=req.user_id)
    return APIResponse(message="已转接", data={"ticket_id": ticket.id})


@router.get("/support/session/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    _user_id: int = Depends(get_current_user_id),
):
    """客服查看任意会话的消息（绕过 user_id 隔离）。"""
    from app.services.session_service import SessionService
    svc = SessionService()
    # 客服直接查消息，不做 user_id 校验
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
            "SELECT role, content, created_at FROM conversation_message "
            "WHERE session_id=%s ORDER BY created_at ASC",
            (session_id,),
        )
        items = [{"role": r[0], "content": r[1], "created_at": r[2].isoformat() if r[2] else None}
                 for r in cur.fetchall()]
        return APIResponse(data={"items": items, "total": len(items)})
    finally:
        conn.close()


@router.get("/support/queue")
async def list_queue(
    status: str = Query(default="pending", description="pending/claimed/processing/completed"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """客服队列：待处理的转人工请求。"""
    query = select(SupportTicket)
    count_q = select(func.count(SupportTicket.id))
    if status:
        query = query.where(SupportTicket.status == status)
        count_q = count_q.where(SupportTicket.status == status)

    total = (await session.execute(count_q)).scalar() or 0
    offset = (page - 1) * page_size
    result = await session.execute(
        query.order_by(SupportTicket.created_at.desc()).offset(offset).limit(page_size)
    )
    tickets = result.scalars().all()

    items = [
        {
            "id": t.id, "user_id": t.user_id, "username": t.username,
            "session_id": t.session_id, "query": t.query,
            "status": t.status, "claimed_by": t.claimed_by, "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tickets
    ]
    return APIResponse(data=PaginatedData(items=items, total=total, page=page, page_size=page_size).model_dump())


class NoteRequest(BaseModel):
    note: str = Field(..., max_length=1000)


@router.post("/support/claim/{ticket_id}")
async def claim_ticket(
    ticket_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """客服认领工单。"""
    result = await session.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.status != "pending":
        raise HTTPException(status_code=400, detail="工单已被认领或已处理")

    ticket.status = "claimed"
    ticket.claimed_by = user_id
    await session.flush()

    logger.info("support_claimed", ticket_id=ticket_id, claimed_by=user_id)
    return APIResponse(message="已认领", data={"ticket_id": ticket_id, "session_id": ticket.session_id})


@router.post("/support/complete/{ticket_id}")
async def complete_ticket(
    ticket_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """完成工单。同时结束会话的人工模式。"""
    result = await session.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")
    if ticket.claimed_by != user_id:
        raise HTTPException(status_code=403, detail="只能完成自己认领的工单")

    ticket.status = "completed"
    await session.flush()

    # 结束会话的人工模式（用户恢复 Agent 对话）
    import pymysql
    from app.core.config import get_settings
    s = get_settings().mysql
    conn = pymysql.connect(host="127.0.0.1", port=s.port, user=s.user,
                           password=s.password, database=s.database, charset="utf8mb4")
    try:
        cur = conn.cursor()
        cur.execute("UPDATE conversation SET is_support=0 WHERE session_id=%s", (ticket.session_id,))
        conn.commit()
        # 插入一条系统消息通知用户
        from datetime import datetime
        cur.execute(
            "INSERT INTO conversation_message (session_id, role, content, created_at) VALUES (%s, %s, %s, %s)",
            (ticket.session_id, "system", "客服已结束本次服务。如需继续咨询，请重新发送消息。", datetime.now()),
        )
        conn.commit()
    finally:
        conn.close()

    # 通过 WebSocket 广播完成消息
    from app.api.routers.ws_chat import _rooms
    import json as _json
    payload = _json.dumps({"type": "completed", "content": "客服已结束本次服务"}, ensure_ascii=False)
    for ws_conn in _rooms.get(ticket.session_id, []):
        try:
            await ws_conn.send_text(payload)
        except Exception:
            pass

    logger.info("support_completed", ticket_id=ticket_id, by=user_id)
    return APIResponse(message="已完成")


@router.post("/support/note/{ticket_id}")
async def add_note(
    ticket_id: int,
    req: NoteRequest,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """添加工单备注。"""
    result = await session.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )
    ticket = result.scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="工单不存在")

    ticket.note = req.note
    await session.flush()
    return APIResponse(message="备注已更新")


@router.get("/support/my")
async def my_tickets(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db_session),
):
    """当前客服正在处理的工单。"""
    result = await session.execute(
        select(SupportTicket)
        .where(SupportTicket.claimed_by == user_id)
        .where(SupportTicket.status.in_(["claimed", "processing"]))
        .order_by(SupportTicket.updated_at.desc())
    )
    tickets = result.scalars().all()
    items = [
        {
            "id": t.id, "user_id": t.user_id, "username": t.username,
            "session_id": t.session_id, "query": t.query,
            "status": t.status, "note": t.note,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tickets
    ]
    return APIResponse(data={"items": items, "total": len(items)})
