"""
query_router_node

根据 intent + risk_level 决定后续执行路径。
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.core.logger import get_logger

logger = get_logger(__name__)

# Intent → Route 映射表
_INTENT_ROUTE_MAP: dict[str, str] = {
    "faq_query":         "rag",
    "device_info_query": "rag",
    "fault_code_query":  "fault_code_lookup",
    "troubleshooting":   "rag",
    "policy_query":      "rag",
    "warranty_query":    "tool",
    "device_binding":    "tool",
    "create_ticket":     "tool",   # + human_confirm
    "create_warranty":   "tool",   # + human_confirm
    "transfer_human":    "tool",   # + human_confirm
    "medical_risk":      "safe_reply",
    "chitchat":          "direct",
}


async def query_router_node(state: AgentState) -> dict:
    """查询路由节点。

    根据意图和风险等级决定：
    - rag → RAG 检索
    - tool → Tool 调用
    - safe_reply → 安全回复
    - direct → 直接回答
    """
    intent = state.get("intent", "faq_query")
    risk_level = state.get("risk_level", "none")

    # 优先处理高风险
    if risk_level == "high":
        return {"route_type": "safe_reply"}

    # 多意图场景：包含写操作的走串行流程
    intents = state.get("intents", [])
    intent_names = [i["intent"] for i in intents]
    if "create_ticket" in intent_names or "transfer_human" in intent_names:
        # 先 RAG 后 Tool（串行）
        if any(i in intent_names for i in ["faq_query", "fault_code_query", "troubleshooting"]):
            return {"route_type": "rag"}  # RAG 先执行，后续再 Tool

    route_type = _INTENT_ROUTE_MAP.get(intent, "rag")

    print(f"[TRACE] query_router intent={intent} → route={route_type}", flush=True)
    logger.info(
        "query_router",
        intent=intent,
        route_type=route_type,
        trace_id=state.get("trace_id", ""),
    )

    return {"route_type": route_type}
