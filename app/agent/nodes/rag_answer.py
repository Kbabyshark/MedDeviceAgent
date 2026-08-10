"""
rag_answer_node

基于检索文档 + Prompt 模板 + DeepSeek-R1 生成最终答案。

要求：
- 回答必须基于检索内容，不编造
- 保留引用信息（Citation）
- 低置信度时提示用户
"""

from __future__ import annotations

from app.agent.state import AgentState, get_stream_queue
from app.core.llm import ModelType, get_llm_client
from app.core.prompt_manager import get_prompt_manager
from app.core.logger import get_logger

logger = get_logger(__name__)


async def rag_answer_node(state: AgentState) -> dict:
    """RAG 回答生成节点。

    使用 DeepSeek-R1 基于检索文档生成回答。
    """
    query = state.get("query", "")
    retrieved_docs = state.get("retrieved_docs", [])
    device_info = state.get("device_info", {})
    summary = state.get("summary", "")
    long_term_memory = state.get("long_term_memory", "")
    low_confidence = state.get("low_confidence", False)
    trace_id = state.get("trace_id", "")

    logger.info("rag_answer_start", doc_count=len(retrieved_docs), trace_id=trace_id)

    # ---- 无知识库文档时，让 LLM 自由回答 ----
    if not retrieved_docs:
        logger.info("rag_answer_no_docs_freestyle", trace_id=trace_id)

    # ---- 构建上下文 ----
    context = _build_context(retrieved_docs)
    citations = _build_citations(retrieved_docs[:3])

    # ---- 调用 LLM 生成回答 ----
    llm = get_llm_client()

    if llm.mock_mode:
        if not retrieved_docs:
            return {"response": "请说出你的问题，我会尽力为你解答。", "citations": []}
        top_doc = retrieved_docs[0]
        mock_response = (
            f"根据知识库检索结果，为您提供以下信息：\n\n"
            f"{top_doc.get('content', '')[:500]}\n\n"
            f"---\n"
            f"来源：{top_doc.get('metadata', {}).get('name', '知识库')}\n"
            f"[Mock 模式 — 未连接 DeepSeek API]"
        )
        if low_confidence:
            mock_response = "⚠️ 检索置信度较低，以下信息仅供参考：\n\n" + mock_response
        return {"response": mock_response, "citations": citations}

    try:
        pm = get_prompt_manager()
        template = pm.get("rag", "v2")
        system, user_prompt = template.render(
            query=query,
            context=context,
            summary=summary or "无历史摘要",
            long_term_memory=long_term_memory or "无",
            device_info=str(device_info) if device_info else "未知设备",
        )

        stream_queue = get_stream_queue()
        total_tokens = 0
        if stream_queue is not None:
            response = ""
            async for token in llm.chat_stream(
                prompt=user_prompt, system=system,
                model=ModelType.V3, temperature=0.3, max_tokens=2048,
            ):
                response += token
                await stream_queue.put(token)
            await stream_queue.put(None)
        else:
            result = await llm.chat(
                prompt=user_prompt, system=system,
                model=ModelType.V3, temperature=0.3, max_tokens=2048,
            )
            response = result.content
            total_tokens = result.total_tokens

        # 低置信度提示
        if low_confidence:
            response = "⚠️ 知识库中未找到完全匹配的信息，以下内容仅供参考：\n\n" + response

        logger.info(
            "rag_answer_done",
            response_len=len(response),
            citations=len(citations),
            tokens=total_tokens,
            trace_id=trace_id,
        )

        return {"response": response, "citations": citations}

    except Exception as e:
        logger.error("rag_answer_error", error=str(e), trace_id=trace_id)
        if stream_queue is not None:
            await stream_queue.put(None)
        return {
            "response": "抱歉，回答生成失败。请稍后重试或转接人工客服。",
            "citations": citations,
        }


def _build_context(docs: list[dict]) -> str:
    """将检索文档拼接为 LLM 上下文。"""
    parts = []
    for i, doc in enumerate(docs, 1):
        meta = doc.get("metadata", {})
        parts.append(
            f"[文档{i}] 来源: {meta.get('name', '未知')} | "
            f"设备: {meta.get('device_type', '')} | "
            f"版本: {meta.get('version', '')}\n"
            f"{doc.get('content', '')}"
        )
    return "\n\n".join(parts)


def _build_citations(docs: list[dict]) -> list[dict]:
    """构建引用列表。"""
    citations = []
    for doc in docs:
        meta = doc.get("metadata", {})
        citations.append({
            "source": meta.get("name", "未知文档"),
            "device_type": meta.get("device_type", ""),
            "version": meta.get("version", ""),
            "score": doc.get("score", 0),
            "snippet": doc.get("content", "")[:200],
        })
    return citations
