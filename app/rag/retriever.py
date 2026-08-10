"""
RAG Retriever — Qdrant 向量检索 + Metadata 过滤。

只负责检索，不负责生成答案。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class RagRetriever:
    """RAG 检索器。

    流程：Embedding → Metadata Filter → Qdrant Search → Top-K
    """

    collection_name: str = "enterprise_knowledge"
    default_top_k: int = 20

    async def retrieve(
        self,
        query: str,
        device_type: str = "",
        doc_type: str = "",
        version: str = "",
        permission: str = "public",
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """执行语义检索。

        Args:
            query: 改写后的搜索 query
            device_type: 设备型号过滤
            doc_type: 文档类型过滤
            version: 文档版本过滤
            permission: 权限级别过滤
            top_k: 返回数量

        Returns:
            检索结果列表 [{content, metadata, score}]
        """
        k = top_k or self.default_top_k

        # 构建 metadata 过滤条件
        must_conditions: list[dict] = []
        if device_type:
            must_conditions.append({"key": "device_type", "match": {"value": device_type}})
        if doc_type:
            must_conditions.append({"key": "doc_type", "match": {"value": doc_type}})
        if permission:
            must_conditions.append({"key": "permission", "match": {"value": permission}})

        logger.info(
            "rag_retrieve",
            query=query[:100],
            filters={"device_type": device_type, "doc_type": doc_type, "permission": permission},
            top_k=k,
        )

        # TODO: 对接 Qdrant
        # embedding = await embedding_service.embed(query)
        # results = await qdrant_client.search(
        #     collection_name=self.collection_name,
        #     query_vector=embedding,
        #     query_filter=qdrant.models.Filter(must=must_conditions),
        #     limit=k,
        # )

        return []

    async def retrieve_with_user_context(
        self,
        query: str,
        user_id: str,
        device_info: dict,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """带用户上下文的检索（便捷方法）。"""
        return await self.retrieve(
            query=query,
            device_type=device_info.get("device_type", ""),
            top_k=top_k,
        )
