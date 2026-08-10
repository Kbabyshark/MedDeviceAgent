"""
/api/v1/ticket — 工单管理接口（含 Human Confirm 流程）
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user_id
from app.core.lock import LockAcquireError, with_ticket_lock
from app.core.logger import get_logger
from app.schemas.common import APIResponse
from app.schemas.ticket import TicketConfirmRequest, TicketCreateRequest, TicketResponse

logger = get_logger(__name__)
router = APIRouter(tags=["ticket"])

# Human Confirm 超时时间（秒）
CONFIRM_TIMEOUT_SECONDS = 1800  # 30 分钟

# 内存中的 pending 存储（P4 将迁移到 Redis + LangGraph Checkpoint）
_pending_actions: dict[str, dict] = {}


@router.post("/ticket/draft", response_model=APIResponse[TicketResponse])
async def create_ticket_draft(
    req: TicketCreateRequest,
    user_id: int = Depends(get_current_user_id),
) -> APIResponse[TicketResponse]:
    """Agent 生成维修工单草稿（待用户确认）。

    此接口生成工单草稿并返回 ticket_id。
    用户需调用 POST /api/v1/ticket/confirm 确认或取消。
    """
    try:
        # 分布式锁防重复
        async with with_ticket_lock(str(user_id), req.device_sn):
            ticket_id = f"ticket_{user_id}_{req.device_sn}_{int(asyncio.get_event_loop().time())}"

            pending_data = {
                "ticket_id": ticket_id,
                "user_id": user_id,
                "device_sn": req.device_sn,
                "fault_desc": req.fault_desc,
                "contact_name": req.contact_name,
                "contact_phone": req.contact_phone,
                "priority": req.priority,
                "status": "pending_confirm",
                "created_at": None,  # 正式创建后填入
            }

            _pending_actions[ticket_id] = pending_data

            logger.info(
                "ticket_draft_created",
                ticket_id=ticket_id,
                user_id=user_id,
                device_sn=req.device_sn,
            )

            return APIResponse(
                data=TicketResponse(
                    ticket_id=ticket_id,
                    device_sn=req.device_sn,
                    fault_desc=req.fault_desc,
                    status="pending_confirm",
                    priority=req.priority,
                ),
            )

    except LockAcquireError as e:
        raise HTTPException(status_code=429, detail=str(e))


@router.post("/ticket/confirm", response_model=APIResponse[TicketResponse])
async def confirm_ticket(
    req: TicketConfirmRequest,
    user_id: int = Depends(get_current_user_id),
) -> APIResponse[TicketResponse]:
    """用户确认或取消工单。

    - confirm=true  → 执行 Tool 创建工单
    - confirm=false → 取消工单
    - 超时 30 分钟 → 自动取消
    """
    pending = _pending_actions.get(req.ticket_id)

    if not pending:
        raise HTTPException(status_code=404, detail="工单草稿不存在或已过期")

    if pending["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="无权操作此工单")

    if not req.confirm:
        # ---- 取消 ----
        pending["status"] = "cancelled"
        logger.info("ticket_cancelled", ticket_id=req.ticket_id, user_id=user_id)
        return APIResponse(
            code=0,
            message="工单已取消",
            data=TicketResponse(
                ticket_id=req.ticket_id,
                device_sn=pending["device_sn"],
                fault_desc=pending["fault_desc"],
                status="cancelled",
                priority=pending.get("priority", ""),
            ),
        )

    # ---- 确认创建 ----
    try:
        from app.agent.tools.create_ticket import create_ticket_tool

        result = await create_ticket_tool.execute(
            user_id=str(user_id),
            device_sn=pending["device_sn"],
            fault_desc=pending["fault_desc"],
            contact_name=pending.get("contact_name", ""),
            contact_phone=pending.get("contact_phone", ""),
            priority=pending.get("priority", "medium"),
        )

        pending["status"] = "created"

        logger.info(
            "ticket_created",
            ticket_id=req.ticket_id,
            tool_result=result.get("ticket_id", ""),
            user_id=user_id,
        )

        return APIResponse(
            message="工单创建成功",
            data=TicketResponse(
                ticket_id=req.ticket_id,
                device_sn=pending["device_sn"],
                fault_desc=pending["fault_desc"],
                status="created",
                priority=pending.get("priority", ""),
            ),
        )

    except Exception as e:
        logger.error("ticket_create_error", error=str(e), ticket_id=req.ticket_id)
        pending["status"] = "failed"
        raise HTTPException(status_code=500, detail=f"工单创建失败: {e}")


@router.get("/ticket/{ticket_id}", response_model=APIResponse[TicketResponse])
async def get_ticket(
    ticket_id: str,
    user_id: int = Depends(get_current_user_id),
) -> APIResponse[TicketResponse]:
    """查询工单详情。"""
    pending = _pending_actions.get(ticket_id)

    if pending and pending["user_id"] == user_id:
        return APIResponse(
            data=TicketResponse(
                ticket_id=ticket_id,
                device_sn=pending["device_sn"],
                fault_desc=pending["fault_desc"],
                status=pending.get("status", "pending_confirm"),
                priority=pending.get("priority", ""),
            ),
        )

    # TODO: P4 接入 MySQL 后从 repair_ticket 表查询
    raise HTTPException(status_code=404, detail="工单不存在")
