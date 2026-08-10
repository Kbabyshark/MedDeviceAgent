"""
Trace / Eval 可观测服务。

每次 Agent 请求自动记录：
- agent_trace: 请求级链路概要
- agent_trace_node: 每节点执行详情
- llm_call_record: 每次 LLM 调用详情

支持 trace_id 完整回放。
"""

from __future__ import annotations

import contextvars
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from app.core.logger import get_logger

logger = get_logger(__name__)

# 内存存储（P7 接入 MySQL 后切换）
_traces: dict[str, dict] = {}
_trace_nodes: dict[str, list[dict]] = {}  # trace_id → list of node records
_llm_records: dict[str, list[dict]] = {}  # trace_id → list of llm call records

# 当前请求的 TraceRecorder（contextvar，协程安全）
_current_trace: contextvars.ContextVar = contextvars.ContextVar("trace_recorder", default=None)


class TraceRecorder:
    """Trace 记录器。

    使用方式：
        recorder = TraceRecorder(trace_id, session_id, user_id, query)

        # 记录节点
        async with recorder.node("intent_classify") as ctx:
            ctx.output = await intent_classify_node(...)

        # 记录 LLM 调用
        recorder.llm_call(task_type="rag_answer", model="deepseek-r1", ...)

        # 完成
        recorder.finish(status="success")
    """

    def __init__(
        self,
        trace_id: str,
        session_id: str = "",
        user_id: str = "",
        query: str = "",
    ) -> None:
        self.trace_id = trace_id
        self.session_id = session_id
        self.user_id = user_id
        self.query = query
        self._start_time = time.monotonic()
        self._node_index = 0

        # 创建 trace 记录
        _traces[trace_id] = {
            "trace_id": trace_id,
            "session_id": session_id,
            "user_id": user_id,
            "query": query,
            "start_time": datetime.now(timezone.utc).isoformat(),
            "end_time": None,
            "total_latency": 0,
            "status": "running",
            "node_count": 0,
            "llm_call_count": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "total_tokens": 0,
        }
        _trace_nodes[trace_id] = []
        _llm_records[trace_id] = []

    @asynccontextmanager
    async def node(self, node_name: str) -> AsyncIterator["NodeContext"]:
        """记录一个节点的执行。

        Usage:
            async with recorder.node("intent_classify") as ctx:
                result = await do_something()
                ctx.output = result
        """
        t0 = time.monotonic()
        ctx = NodeContext(node_name=node_name, index=self._node_index)
        self._node_index += 1

        try:
            yield ctx
        except Exception as e:
            ctx.error = str(e)
            raise
        finally:
            latency = (time.monotonic() - t0) * 1000
            node_record = {
                "trace_id": self.trace_id,
                "node_name": node_name,
                "index": ctx.index,
                "input": ctx.input,
                "output": ctx.output,
                "latency": round(latency, 2),
                "error": ctx.error,
            }
            _trace_nodes[self.trace_id].append(node_record)
            _traces[self.trace_id]["node_count"] = len(_trace_nodes[self.trace_id])

            logger.debug(
                "trace_node_recorded",
                trace_id=self.trace_id,
                node=node_name,
                latency_ms=round(latency, 2),
            )

    def llm_call(
        self,
        task_type: str,
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        latency: float = 0,
        error: str | None = None,
    ) -> None:
        """记录一次 LLM 调用。"""
        record = {
            "trace_id": self.trace_id,
            "task_type": task_type,
            "model_name": model_name,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens or (prompt_tokens + completion_tokens),
            "latency": round(latency, 2) if latency else 0,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        _llm_records[self.trace_id].append(record)

        trace = _traces[self.trace_id]
        trace["llm_call_count"] += 1
        trace["total_prompt_tokens"] += prompt_tokens
        trace["total_completion_tokens"] += completion_tokens
        trace["total_tokens"] += (total_tokens or (prompt_tokens + completion_tokens))

    def finish(self, status: str = "success", error: str | None = None) -> dict:
        """标记 Trace 完成。"""
        total_latency = (time.monotonic() - self._start_time) * 1000
        trace = _traces[self.trace_id]
        trace["end_time"] = datetime.now(timezone.utc).isoformat()
        trace["total_latency"] = round(total_latency, 2)
        trace["status"] = "failed" if error else status
        if error:
            trace["error"] = error

        logger.info(
            "trace_completed",
            trace_id=self.trace_id,
            status=trace["status"],
            nodes=trace["node_count"],
            llm_calls=trace["llm_call_count"],
            tokens=trace["total_tokens"],
            latency_ms=trace["total_latency"],
        )

        return trace


class NodeContext:
    """节点执行上下文。"""

    def __init__(self, node_name: str, index: int) -> None:
        self.node_name = node_name
        self.index = index
        self.input: Any = None
        self.output: Any = None
        self.error: str | None = None


# ================================================================
# 查询接口
# ================================================================


def get_trace(trace_id: str) -> dict | None:
    """查询完整 Trace（含所有 node 和 LLM 记录）。"""
    trace = _traces.get(trace_id)
    if trace is None:
        return None

    return {
        **trace,
        "nodes": _trace_nodes.get(trace_id, []),
        "llm_calls": _llm_records.get(trace_id, []),
    }


def get_trace_nodes(trace_id: str) -> list[dict]:
    """查询 Trace 中的所有节点记录。"""
    return _trace_nodes.get(trace_id, [])


def get_trace_llm_calls(trace_id: str) -> list[dict]:
    """查询 Trace 中的所有 LLM 调用记录。"""
    return _llm_records.get(trace_id, [])


def list_traces(
    user_id: str = "",
    session_id: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """列出 Trace 记录（支持筛选 + 分页）。"""
    items = list(_traces.values())

    if user_id:
        items = [t for t in items if t.get("user_id") == user_id]
    if session_id:
        items = [t for t in items if t.get("session_id") == session_id]
    if status:
        items = [t for t in items if t.get("status") == status]

    items.sort(key=lambda x: x.get("start_time", ""), reverse=True)
    total = len(items)
    start = (page - 1) * page_size

    return {
        "items": items[start : start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def replay_trace(trace_id: str) -> dict | None:
    """按 trace_id 回放完整 Workflow 执行过程。

    返回每一步的状态变化序列。
    """
    trace = get_trace(trace_id)
    if trace is None:
        return None

    nodes = trace.get("nodes", [])
    replay_steps = []
    for node in sorted(nodes, key=lambda n: n.get("index", 0)):
        replay_steps.append({
            "step": node.get("index", 0),
            "node": node.get("node_name", ""),
            "input_summary": _summarize(node.get("input")),
            "output_summary": _summarize(node.get("output")),
            "latency_ms": node.get("latency", 0),
            "error": node.get("error"),
        })

    return {
        "trace_id": trace_id,
        "query": trace.get("query", ""),
        "status": trace.get("status", ""),
        "total_latency_ms": trace.get("total_latency", 0),
        "steps": replay_steps,
        "llm_calls": trace.get("llm_calls", []),
    }


def get_cost_summary(days: int = 30) -> dict:
    """获取 Token 消耗和费用汇总。

    DeepSeek 定价（参考）:
    - V3: 输入 ¥2/1M tokens, 输出 ¥8/1M tokens
    - R1: 输入 ¥4/1M tokens, 输出 ¥16/1M tokens
    """
    now = datetime.now(timezone.utc)
    all_records = []
    for records in _llm_records.values():
        all_records.extend(records)

    # 按天分组统计
    daily_stats: dict[str, dict] = {}
    total_input = 0
    total_output = 0

    for r in all_records:
        day = r.get("timestamp", "")[:10]
        if day not in daily_stats:
            daily_stats[day] = {"prompt_tokens": 0, "completion_tokens": 0, "calls": 0}
        daily_stats[day]["prompt_tokens"] += r.get("prompt_tokens", 0)
        daily_stats[day]["completion_tokens"] += r.get("completion_tokens", 0)
        daily_stats[day]["calls"] += 1
        total_input += r.get("prompt_tokens", 0)
        total_output += r.get("completion_tokens", 0)

    # 简单费用估算（按 V3 价格，实际应按 model_name 区分）
    cost_input = total_input / 1_000_000 * 2   # ¥2/M
    cost_output = total_output / 1_000_000 * 8  # ¥8/M
    total_cost = cost_input + cost_output

    return {
        "period_days": days,
        "total_calls": len(all_records),
        "total_prompt_tokens": total_input,
        "total_completion_tokens": total_output,
        "total_tokens": total_input + total_output,
        "estimated_cost_cny": round(total_cost, 4),
        "daily_breakdown": [
            {
                "date": day,
                "prompt_tokens": stats["prompt_tokens"],
                "completion_tokens": stats["completion_tokens"],
                "calls": stats["calls"],
            }
            for day, stats in sorted(daily_stats.items())
        ],
    }


def _summarize(data: Any, max_len: int = 200) -> str:
    """摘要化数据（用于回放展示）。"""
    if data is None:
        return "null"
    text = str(data)
    return text[:max_len] + "..." if len(text) > max_len else text
