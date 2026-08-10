"""
/api/v1/trace — Trace 查询与分析接口
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_current_user_id, require_admin
from app.core.tracer import (
    get_trace,
    get_trace_nodes,
    get_trace_llm_calls,
    list_traces,
    replay_trace,
    get_cost_summary,
)
from app.schemas.common import APIResponse, PaginatedData, PaginatedResponse

router = APIRouter(tags=["trace"])


@router.get("/trace/{trace_id}")
async def query_trace(
    trace_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """查询完整 Trace（含所有 Node + LLM 调用记录）。"""
    trace = get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="Trace 不存在")
    return APIResponse(data=trace)


@router.get("/trace/{trace_id}/nodes")
async def query_trace_nodes(
    trace_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """查询 Trace 节点记录。"""
    nodes = get_trace_nodes(trace_id)
    return APIResponse(data={"trace_id": trace_id, "nodes": nodes, "count": len(nodes)})


@router.get("/trace/{trace_id}/llm")
async def query_trace_llm_calls(
    trace_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """查询 Trace 中的 LLM 调用记录。"""
    records = get_trace_llm_calls(trace_id)
    return APIResponse(data={"trace_id": trace_id, "llm_calls": records, "count": len(records)})


@router.get("/trace/{trace_id}/replay")
async def replay_trace_api(
    trace_id: str,
    user_id: int = Depends(get_current_user_id),
):
    """按 trace_id 回放完整 Workflow 执行过程。

    返回每一步的状态变化序列：
    {steps: [{step, node, input_summary, output_summary, latency_ms, error}]}
    """
    result = replay_trace(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Trace 不存在")
    return APIResponse(data=result)


@router.get("/traces")
async def query_traces(
    session_id: str = Query(default="", description="按会话筛选"),
    status: str = Query(default="", description="按状态筛选: success/failed/running"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _user_id: int = Depends(get_current_user_id),
):
    """列出当前用户的 Trace 记录。"""
    result = list_traces(
        user_id=str(_user_id),
        session_id=session_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=result["items"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        ),
    )


@router.get("/admin/traces")
async def query_all_traces(
    session_id: str = Query(default="", description="按会话筛选"),
    status: str = Query(default="", description="按状态筛选"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    _admin_id: int = Depends(require_admin),
):
    """管理员查看所有用户的 Trace 记录。"""
    result = list_traces(
        session_id=session_id,
        status=status,
        page=page,
        page_size=page_size,
    )
    return PaginatedResponse(
        data=PaginatedData(
            items=result["items"],
            total=result["total"],
            page=result["page"],
            page_size=result["page_size"],
        ),
    )


@router.get("/admin/cost")
async def get_cost_dashboard(
    days: int = Query(default=30, ge=1, le=365, description="统计天数"),
    user_id: int = Depends(require_admin),
):
    """成本分析仪表板（管理员）。

    返回 Token 消耗、调用次数、费用估算、每日明细。
    """
    summary = get_cost_summary(days=days)
    return APIResponse(data=summary)
