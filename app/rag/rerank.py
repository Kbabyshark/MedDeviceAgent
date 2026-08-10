"""
Rerank 重排序服务。

使用 BGE-Reranker 或 DeepSeek-R1 对检索结果重排序。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class Reranker:
    """Rerank 重排序器。"""

    top_n: int = 5

    async def rerank(
        self,
        query: str,
        documents: list[dict],
        top_n: int | None = None,
    ) -> list[dict]:
        """对检索结果进行重排序。

        Args:
            query: 原始查询
            documents: 检索结果列表
            top_n: 返回数量（默认使用初始化值）

        Returns:
            重排序后的结果列表
        """
        n = top_n or self.top_n

        logger.info("rerank_start", doc_count=len(documents), top_n=n)

        # TODO: 实际 Rerank
        # scores = await rerank_model.compute_scores(query, [d["content"] for d in documents])
        # ranked = sorted(zip(documents, scores), key=lambda x: x[1], reverse=True)

        return documents[:n]
