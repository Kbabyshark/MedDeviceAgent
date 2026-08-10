"""
rag_rerank_node

对 Top-K 检索结果进行重排序，按相似度阈值策略决策。
Rerank 模型：BGE-Reranker 或 DeepSeek-R1。
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.rag.rerank import Reranker
from app.core.logger import get_logger

logger = get_logger(__name__)

# Rerank 后保留数量
_RERANK_TOP_N = 5
# 跳过 Rerank 的置信度阈值
_SKIP_THRESHOLD = 0.9
# 低置信度阈值
_LOW_CONFIDENCE_THRESHOLD = 0.6


async def rag_rerank_node(state: AgentState) -> dict:
    """RAG Rerank 节点。

    策略：
    | 场景 | Top-1 ≥ 0.9 | 0.6 ≤ Top-1 < 0.9 | Top-1 < 0.6 | 多来源混合 |
    |------|------------|-------------------|-------------|-----------|
    | Rerank | 跳过 | 执行 | 执行 + 降级 | 执行去重 |
    """
    retrieved_docs = state.get("retrieved_docs", [])
    query = state.get("query", "")
    trace_id = state.get("trace_id", "")

    if not retrieved_docs:
        logger.info("rag_rerank_skip_empty", trace_id=trace_id)
        return {"retrieved_docs": [], "low_confidence": False}

    top_score = retrieved_docs[0].get("score", 0)
    doc_count = len(retrieved_docs)

    # ---- 判断是否需要 Rerank ----
    # Case 1: 高置信度 + 少量结果 → 跳过
    if top_score >= _SKIP_THRESHOLD and doc_count <= 3:
        logger.info("rag_rerank_skip_high_confidence", score=top_score, trace_id=trace_id)
        return {"retrieved_docs": retrieved_docs[:_RERANK_TOP_N], "low_confidence": False}

    # Case 2: 低置信度标记
    low_confidence = top_score < _LOW_CONFIDENCE_THRESHOLD

    # Case 3: 多来源混合 → 需要去重
    doc_ids = {d.get("metadata", {}).get("document_id") for d in retrieved_docs}
    need_dedup = len(doc_ids) < doc_count

    logger.info(
        "rag_rerank_start",
        doc_count=doc_count,
        top_score=top_score,
        low_confidence=low_confidence,
        need_dedup=need_dedup,
        trace_id=trace_id,
    )

    # ---- 执行 Rerank ----
    try:
        reranker = Reranker(top_n=_RERANK_TOP_N)
        reranked = await reranker.rerank(query=query, documents=retrieved_docs, top_n=_RERANK_TOP_N)
        logger.info("rag_rerank_done", final_count=len(reranked), trace_id=trace_id)
        return {"retrieved_docs": reranked, "low_confidence": low_confidence}

    except Exception as e:
        logger.error("rag_rerank_error", error=str(e), trace_id=trace_id)
        # Rerank 失败 → 降级返回原始 Top-N
        return {"retrieved_docs": retrieved_docs[:_RERANK_TOP_N], "low_confidence": True}
