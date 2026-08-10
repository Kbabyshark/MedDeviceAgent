"""
LangSmith Studio 专用图模块。
与生产 graph.py 结构完全一致，但独立编译，不依赖 graph.py。
"""

from __future__ import annotations

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


# ---- 路由函数 ----

def _route_after_safety(state: AgentState) -> str:
    return "high" if state.get("risk_level") == "high" else "normal"


def _route_after_query_router(state: AgentState) -> str:
    return state.get("route_type", "rag")


def _route_after_tool(state: AgentState) -> str:
    pending = state.get("pending_action")
    return "confirm" if (pending and pending.get("status") == "waiting_confirm") else "done"


def _route_after_confirm(state: AgentState) -> str:
    return "execute" if state.get("pending_action", {}).get("status") == "confirmed" else "cancel"


def _human_confirm_node(state: AgentState) -> dict:
    pending = state.get("pending_action", {})
    action_type = pending.get("type", "unknown")
    trace_id = state.get("trace_id", "")
    user_decision = interrupt({
        "message": f"请确认操作: {action_type}",
        "action_type": action_type,
        "params": pending.get("params", {}),
        "trace_id": trace_id, "status": "waiting_human_input",
    })
    confirmed = user_decision.get("confirm", False) if isinstance(user_decision, dict) else False
    if confirmed:
        return {"pending_action": {**pending, "status": "confirmed",
                "confirmed_params": user_decision.get("params", {}) if isinstance(user_decision, dict) else {}}}
    return {"pending_action": {**pending, "status": "cancelled"}, "response": "操作已取消。如有其他问题，请随时咨询。"}


async def _execute_confirmed_tool(state: AgentState) -> dict:
    pending = state.get("pending_action", {})
    if pending.get("status") != "confirmed":
        return {}
    action_type = pending.get("type", "")
    params = pending.get("confirmed_params", {})
    user_id = state.get("user_id", "")
    query = state.get("query", "")
    if action_type == "create_ticket":
        from app.agent.tools.create_ticket import create_ticket_tool
        result = await create_ticket_tool.execute(
            user_id=user_id, device_sn=params.get("device_sn", ""),
            fault_desc=params.get("fault_desc", query),
            contact_name=params.get("contact_name", ""),
            contact_phone=params.get("contact_phone", ""),
            priority=params.get("priority", "medium"),
        )
        return {"response": f"工单已创建成功！\n工单编号：{result.get('ticket_id', '')}\n状态：{result.get('status', '')}\n我们的售后工程师将尽快与您联系。",
                "pending_action": {"status": "executed"}}
    elif action_type == "transfer_human":
        from app.agent.tools.transfer_human import transfer_human_tool
        result = await transfer_human_tool.execute(
            user_id=user_id, reason=params.get("reason", "用户主动请求"),
            summary=params.get("summary", query),
        )
        return {"response": f"已为您转接人工客服。\n当前排队位置：第 {result.get('queue_position', 1)} 位\n预计等待：{result.get('estimated_wait_seconds', 60)} 秒\n对话摘要已同步给客服，无需重复描述。",
                "pending_action": {"status": "executed"}}
    return {}


async def _safe_reply(state: AgentState) -> dict:
    risk_detail = state.get("risk_detail", {})
    risk_type = risk_detail.get("type", "unknown") if risk_detail else "unknown"
    messages = {
        "medical_diagnosis": "您的问题涉及医疗诊断范畴。作为设备售后服务助手，我无法提供疾病诊断。\n如果您需要设备故障排查或使用指导，请描述设备的具体型号和异常现象。\n健康相关问题，建议您咨询专业医疗机构。",
        "treatment_advice": "您的问题涉及治疗建议。设备的售后技术支持无法替代医生诊断。\n如需设备操作指导或故障排查，请告诉我设备型号和具体问题。",
        "medication_advice": "您的问题涉及用药建议，已超出设备售后服务范围。\n用药请遵循医嘱。如需设备技术支持，请描述设备问题。",
        "privacy": "您请求的信息涉及隐私数据。为保护信息安全，此类问题无法通过在线客服处理。\n如需查询个人隐私信息，请通过官方渠道验证身份后处理。",
        "unauthorized": "您请求的操作需要特定权限。\n如需修改账号数据或设备信息，请联系人工客服并验证身份。",
    }
    response = messages.get(risk_type, "您的问题涉及医疗安全范畴，作为设备售后助手无法直接回答。\n如果您需要设备技术支持或故障排查，请告诉我设备的具体情况。\n健康相关问题请咨询专业医疗机构。")
    return {"response": response, "route_type": "safe_reply", "risk_level": "high"}


# ---- 构建图 ----

def build_studio_graph() -> StateGraph:
    workflow = StateGraph(AgentState)

    # 注册所有节点
    workflow.add_node("input_safety_check", input_safety_check_node)
    workflow.add_node("intent_classify", intent_classify_node)
    workflow.add_node("context_load", context_load_node)
    workflow.add_node("query_router", query_router_node)
    workflow.add_node("query_rewrite", query_rewrite_node)
    workflow.add_node("rag_retrieve", rag_retrieve_node)
    workflow.add_node("fault_code_lookup", fault_code_lookup_node)
    workflow.add_node("rag_rerank", rag_rerank_node)
    workflow.add_node("rag_answer", rag_answer_node)
    workflow.add_node("tool_execute", tool_execute_node)
    workflow.add_node("human_confirm", _human_confirm_node)
    workflow.add_node("execute_tool", _execute_confirmed_tool)
    workflow.add_node("answer_generate", answer_generate_node)
    workflow.add_node("output_safety_check", output_safety_check_node)
    workflow.add_node("memory_update", memory_update_node)
    workflow.add_node("safe_reply", _safe_reply)

    # 入口
    workflow.set_entry_point("input_safety_check")

    # 边 — 带 path_map，Studio 可渲染所有分支
    workflow.add_conditional_edges("input_safety_check", _route_after_safety, {
        "high": "safe_reply",
        "normal": "intent_classify",
    })
    workflow.add_edge("intent_classify", "context_load")
    workflow.add_edge("context_load", "query_router")
    workflow.add_conditional_edges("query_router", _route_after_query_router, {
        "rag": "query_rewrite",
        "tool": "tool_execute",
        "direct": "answer_generate",
        "safe_reply": "safe_reply",
        "fault_code_lookup": "fault_code_lookup",
    })

    workflow.add_edge("query_rewrite", "rag_retrieve")
    workflow.add_edge("rag_retrieve", "rag_rerank")
    workflow.add_edge("rag_rerank", "rag_answer")
    workflow.add_edge("rag_answer", "answer_generate")
    workflow.add_edge("fault_code_lookup", "answer_generate")

    workflow.add_conditional_edges("tool_execute", _route_after_tool, {
        "confirm": "human_confirm",
        "done": "answer_generate",
    })
    workflow.add_conditional_edges("human_confirm", _route_after_confirm, {
        "execute": "execute_tool",
        "cancel": "answer_generate",
    })
    workflow.add_edge("execute_tool", "answer_generate")

    workflow.add_edge("answer_generate", "output_safety_check")
    workflow.add_edge("output_safety_check", "memory_update")
    workflow.add_edge("memory_update", END)
    workflow.add_edge("safe_reply", "answer_generate")

    return workflow.compile()


graph = build_studio_graph()
