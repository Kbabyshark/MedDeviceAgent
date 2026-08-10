"""
LangGraph Workflow 图定义。

支持 Human-in-the-loop：写操作前触发 interrupt，等待用户确认后继续。
"""

from __future__ import annotations

try:
    from langgraph.checkpoint.mysql.aio import AsyncMySQLSaver
except ImportError:
    AsyncMySQLSaver = None  # type: ignore[assignment]

from langgraph.graph import END, StateGraph
from langgraph.types import interrupt

from app.agent.state import AgentState
from app.agent.nodes import (
    answer_generate_node,
    context_load_node,
    input_safety_check_node,
    intent_classify_node,
    memory_update_node,
    output_safety_check_node,
    query_router_node,
    query_rewrite_node,
    rag_answer_node,
    rag_rerank_node,
    rag_retrieve_node,
    tool_execute_node,
    fault_code_lookup_node,
)


def _route_after_safety(state: AgentState) -> str:
    """安全检测后路由。"""
    r = "safe_reply" if state.get("risk_level") == "high" else "intent_classify"
    print(f"[TRACE] route_after_safety → {r}", flush=True)
    return r


def _route_after_query_router(state: AgentState) -> str:
    """根据 route_type 路由。"""
    route = state.get("route_type", "rag")
    routes = {
        "rag": "query_rewrite",
        "tool": "tool_execute",
        "direct": "answer_generate",
        "safe_reply": "safe_reply",
        "fault_code_lookup": "fault_code_lookup",
    }
    return routes.get(route, "query_rewrite")


def _route_after_tool(state: AgentState) -> str:
    """工具执行后路由。"""
    return "answer_generate"


def _human_confirm_node(state: AgentState) -> dict:
    """Human Confirm 节点 — 触发 LangGraph interrupt。

    工作流在此暂停，等待外部通过 `graph.invoke(Command(resume=...))` 恢复。

    resume 数据结构：
        {"confirm": true, "params": {...}}
        {"confirm": false}
    """
    pending = state.get("pending_action", {})
    action_type = pending.get("type", "unknown")
    trace_id = state.get("trace_id", "")

    # LangGraph interrupt —— 暂停工作流，等待恢复
    user_decision = interrupt({
        "message": f"请确认操作: {action_type}",
        "action_type": action_type,
        "params": pending.get("params", {}),
        "trace_id": trace_id,
        "status": "waiting_human_input",
    })

    # 用户已确认/取消
    confirmed = user_decision.get("confirm", False) if isinstance(user_decision, dict) else False

    if confirmed:
        return {
            "pending_action": {
                **pending,
                "status": "confirmed",
                "confirmed_params": user_decision.get("params", {}) if isinstance(user_decision, dict) else {},
            },
        }
    else:
        return {
            "pending_action": {
                **pending,
                "status": "cancelled",
            },
            "response": f"操作已取消。如有其他问题，请随时咨询。",
        }


async def _execute_confirmed_tool(state: AgentState) -> dict:
    """执行已确认的 Tool。

    仅在 human_confirm_node 中用户确认后调用。
    """
    pending = state.get("pending_action", {})

    if pending.get("status") != "confirmed":
        return {}

    # 根据 action_type 调用对应的 Tool
    action_type = pending.get("type", "")
    # confirmed_params（从 human_confirm 来）优先，否则用原始 params
    params = pending.get("confirmed_params") or pending.get("params", {})
    user_id = state.get("user_id", "")
    device_info = state.get("device_info", {})
    query = state.get("query", "")

    if action_type == "create_ticket":
        from app.agent.tools.create_ticket import create_ticket_tool
        from app.agent.nodes.tool_execute import _execute_with_lock
        result = await _execute_with_lock(
            create_ticket_tool,
            {"user_id": user_id,
             "device_sn": params.get("device_sn", device_info.get("device_sn", "")),
             "fault_desc": params.get("fault_desc", query),
             "contact_name": params.get("contact_name", ""),
             "contact_phone": params.get("contact_phone", ""),
             "priority": params.get("priority", "medium")},
            user_id, state.get("trace_id", ""),
        )
        return {
            "response": (
                f"工单已创建成功！\n"
                f"工单编号：{result.get('ticket_id', '')}\n"
                f"状态：{result.get('status', '')}\n"
                f"我们的售后工程师将尽快与您联系。"
            ),
            "pending_action": {"status": "executed"},
        }

    elif action_type == "create_warranty":
        from app.agent.tools.create_warranty import create_warranty_tool
        from app.agent.nodes.tool_execute import _execute_with_lock
        result = await _execute_with_lock(
            create_warranty_tool,
            {"device_sn": params.get("device_sn", device_info.get("device_sn", "")),
             "user_id": str(user_id),
             "problem_desc": params.get("query", query)},
            user_id, state.get("trace_id", ""),
        )
        return {
            "response": (
                f"保修记录已创建成功！\n"
                f"设备：{result.get('device_sn', '')}\n"
                f"状态：{'在保' if result.get('status') == 'valid' else result.get('status', '')}\n"
            ),
            "pending_action": {"status": "executed"},
        }

    elif action_type == "transfer_human":
        from app.agent.tools.transfer_human import transfer_human_tool
        from app.agent.nodes.tool_execute import _execute_with_lock
        result = await _execute_with_lock(
            transfer_human_tool,
            {"user_id": user_id,
             "reason": params.get("reason", "用户主动请求"),
             "summary": params.get("summary", query),
             "session_id": state.get("session_id", ""),
             "username": state.get("username", "")},
            user_id, state.get("trace_id", ""),
        )
        return {
            "response": (
                f"已为您转接人工客服。\n"
                f"当前排队位置：第 {result.get('queue_position', 1)} 位\n"
                f"预计等待：{result.get('estimated_wait_seconds', 60)} 秒\n"
                f"对话摘要已同步给客服，无需重复描述。"
            ),
            "pending_action": {"status": "executed"},
        }

    return {}


def _trace_node(name: str, fn):
    """包装节点函数，自动记录 Trace 节点级信息。"""
    from app.core.tracer import _current_trace

    async def wrapper(state: AgentState) -> dict:
        import time as _time
        tracer = _current_trace.get()
        t0 = _time.monotonic()
        error = None
        result = {}
        try:
            result = await fn(state) if callable(fn) else fn(state)
            return result
        except Exception as e:
            error = str(e)
            raise
        finally:
            if tracer is not None:
                latency = (_time.monotonic() - t0) * 1000
                node_record = {
                    "trace_id": tracer.trace_id,
                    "node_name": name,
                    "index": tracer._node_index,
                    "input": {"query": state.get("query", "")[:200], "intent": state.get("intent", "")},
                    "output": {k: str(v)[:200] for k, v in (result or {}).items()},
                    "latency": round(latency, 2),
                    "error": error,
                }
                from app.core.tracer import _trace_nodes
                _trace_nodes.setdefault(tracer.trace_id, []).append(node_record)
                tracer._node_index += 1
    return wrapper


def build_graph(checkpointer=None) -> StateGraph:  # checkpointer: AsyncMySQLSaver | None
    """构建 LangGraph Workflow。

    Workflow:
        input → safety_check → pending_router → intent_classify → context_load
        → query_router → [rag / tool / direct / safe_reply]
        → answer_generate → output_safety → memory_update → END

    Human-in-the-loop（无 interrupt，基于状态机）：
        1. tool_execute 生成 pending_action(waiting_confirm) → answer_generate 输出确认提示
        2. 用户下一条消息 → pending_router 检测到 waiting_confirm + 确认/取消词
           → 确认: execute_tool → answer_generate
           → 取消: answer_generate (取消消息)
    """
    workflow = StateGraph(AgentState)

    # ---- 注册节点 ----
    workflow.add_node("input_safety_check", _trace_node("input_safety_check", input_safety_check_node))
    workflow.add_node("intent_classify", _trace_node("intent_classify", intent_classify_node))
    workflow.add_node("context_load", _trace_node("context_load", context_load_node))
    workflow.add_node("query_router", _trace_node("query_router", query_router_node))

    # RAG
    workflow.add_node("query_rewrite", _trace_node("query_rewrite", query_rewrite_node))
    workflow.add_node("rag_retrieve", _trace_node("rag_retrieve", rag_retrieve_node))

    # Fault Code 精确查询
    workflow.add_node("fault_code_lookup", _trace_node("fault_code_lookup", fault_code_lookup_node))
    workflow.add_node("rag_rerank", _trace_node("rag_rerank", rag_rerank_node))
    workflow.add_node("rag_answer", _trace_node("rag_answer", rag_answer_node))

    # Tool + Human Confirm
    workflow.add_node("tool_execute", _trace_node("tool_execute", tool_execute_node))
    workflow.add_node("human_confirm", _trace_node("human_confirm", _human_confirm_node))
    workflow.add_node("execute_tool", _trace_node("execute_tool", _execute_confirmed_tool))

    # 输出
    workflow.add_node("answer_generate", _trace_node("answer_generate", answer_generate_node))
    workflow.add_node("output_safety_check", _trace_node("output_safety_check", output_safety_check_node))
    workflow.add_node("memory_update", _trace_node("memory_update", memory_update_node))

    # 终端
    workflow.add_node("safe_reply", _trace_node("safe_reply", _safe_reply_wrapper))

    # ---- 入口 ----
    workflow.set_entry_point("input_safety_check")

    # ---- 边 ----
    workflow.add_conditional_edges("input_safety_check", _route_after_safety)
    workflow.add_edge("intent_classify", "context_load")
    workflow.add_edge("context_load", "query_router")
    workflow.add_conditional_edges("query_router", _route_after_query_router)

    # RAG 链
    workflow.add_edge("query_rewrite", "rag_retrieve")
    workflow.add_edge("rag_retrieve", "rag_rerank")
    workflow.add_edge("rag_rerank", "rag_answer")
    workflow.add_edge("rag_answer", "answer_generate")
    workflow.add_edge("fault_code_lookup", "answer_generate")

    # Tool 链：tool_execute → answer_generate
    workflow.add_edge("tool_execute", "answer_generate")

    # 输出链
    workflow.add_edge("answer_generate", "output_safety_check")
    workflow.add_edge("output_safety_check", "memory_update")
    workflow.add_edge("memory_update", END)

    workflow.add_edge("safe_reply", "answer_generate")

    if checkpointer:
        return workflow.compile(checkpointer=checkpointer)
    return workflow.compile()


def _route_after_confirm(state: AgentState) -> str:
    """确认后的路由。"""
    pending = state.get("pending_action", {})
    if pending.get("status") == "confirmed":
        return "execute"
    return "cancel"


async def _safe_reply_wrapper(state: AgentState) -> dict:
    """高风险问题统一安全回复。"""
    risk_detail = state.get("risk_detail", {})
    risk_type = risk_detail.get("type", "unknown") if risk_detail else "unknown"

    messages = {
        "medical_diagnosis": (
            "您的问题涉及医疗诊断范畴。作为设备售后服务助手，我无法提供疾病诊断。\n"
            "如果您需要设备故障排查或使用指导，请描述设备的具体型号和异常现象。\n"
            "健康相关问题，建议您咨询专业医疗机构。"
        ),
        "treatment_advice": (
            "您的问题涉及治疗建议。设备的售后技术支持无法替代医生诊断。\n"
            "如需设备操作指导或故障排查，请告诉我设备型号和具体问题。"
        ),
        "medication_advice": (
            "您的问题涉及用药建议，已超出设备售后服务范围。\n"
            "用药请遵循医嘱。如需设备技术支持，请描述设备问题。"
        ),
        "privacy": (
            "您请求的信息涉及隐私数据。为保护信息安全，此类问题无法通过在线客服处理。\n"
            "如需查询个人隐私信息，请通过官方渠道验证身份后处理。"
        ),
        "unauthorized": (
            "您请求的操作需要特定权限。\n"
            "如需修改账号数据或设备信息，请联系人工客服并验证身份。"
        ),
    }

    response = messages.get(risk_type, (
        "您的问题涉及医疗安全范畴，作为设备售后助手无法直接回答。\n"
        "如果您需要设备技术支持或故障排查，请告诉我设备的具体情况。\n"
        "健康相关问题请咨询专业医疗机构。"
    ))

    return {
        "response": response,
        "route_type": "safe_reply",
        "risk_level": "high",
    }
