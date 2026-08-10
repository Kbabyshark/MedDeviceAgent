"""
query_rewrite_node

对用户原始 Query 进行改写优化，提升检索精度。
使用 DeepSeek-V3 将简短/模糊问题改写为精确检索 Query。
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.core.llm import ModelType, get_llm_client
from app.core.prompt_manager import get_prompt_manager
from app.core.logger import get_logger

logger = get_logger(__name__)


async def query_rewrite_node(state: AgentState) -> dict:
    """Query 改写节点。

    改写策略：
    1. 拼接设备型号信息
    2. LLM 改写为完整检索语句
    3. Mock 模式：仅拼接设备信息，不做 LLM 改写

    例如：
        "E101是什么" → "[设备型号: Monitor-X1] 设备Monitor-X1出现报错代码E101的含义和故障排除步骤"
    """
    query = state.get("query", "")
    device_info = state.get("device_info", {})
    device_type = device_info.get("device_type", "")
    trace_id = state.get("trace_id", "")

    # 如果已有设备类型且未出现在 query 中，拼接设备信息
    if device_type and device_type not in query:
        query = f"[设备型号: {device_type}] {query}"

    # LLM 改写（Mock 模式下返回原 query）
    llm = get_llm_client()
    if llm.mock_mode:
        logger.info("query_rewrite_mock", original=state["query"][:50], result=query[:100], trace_id=trace_id)
        return {"query": query}

    try:
        pm = get_prompt_manager()
        template = pm.get("rag", "v1")
        system, user_prompt = template.render(
            query=query,
            device_info=str(device_info) if device_info else "未知",
        )

        result = await llm.chat(
            prompt=f"请将以下用户问题改写为更精确的检索查询语句，保留所有关键信息：\n{user_prompt}",
            system="你是一个搜索查询优化器。将用户简短的设备问题改写为完整、精确的检索语句，包含设备型号、故障现象等关键信息。只输出改写后的查询语句。",
            model=ModelType.V3,
            max_tokens=256,
        )

        rewritten = result.content.strip()
        logger.info("query_rewrite_done", original=state["query"][:50], rewritten=rewritten[:100], trace_id=trace_id)
        return {"query": rewritten or query}

    except Exception as e:
        logger.error("query_rewrite_error", error=str(e), trace_id=trace_id)
        return {"query": query}
