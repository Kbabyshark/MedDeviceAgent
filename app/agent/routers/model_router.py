"""
model_router_node

根据 task_type 动态选择 DeepSeek 模型。
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# Task → Model 路由表
_TASK_MODEL_MAP: dict[str, str] = {
    "intent_classify":  "deepseek_v3",
    "safety_check":     "deepseek_v3",
    "query_rewrite":    "deepseek_v3",
    "summary":          "deepseek_v3",
    "memory_extract":   "deepseek_v3",
    "rag_answer":       "deepseek_r1",
    "troubleshooting":  "deepseek_r1",
    "decision":         "deepseek_r1",
    "rerank":           "deepseek_r1",
}


async def model_router_node(state: AgentState) -> dict:
    """模型路由节点。

    根据 task_type 选择：
    - DeepSeek-V3：轻量任务（低延迟）
    - DeepSeek-R1：复杂推理任务（高推理能力）

    模型选择记录到 Trace。
    """
    settings = get_settings()

    task_type = state.get("route_type", "rag_answer")
    model_key = _TASK_MODEL_MAP.get(task_type, "deepseek_v3")

    model_name = settings.deepseek.v3_model if model_key == "deepseek_v3" else settings.deepseek.r1_model

    logger.info(
        "model_router_select",
        task_type=task_type,
        model=model_name,
        trace_id=state.get("trace_id", ""),
    )

    return {
        "selected_model": model_name,
        "selected_model_key": model_key,
    }
