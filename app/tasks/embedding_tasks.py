"""
Embedding 异步任务 — 文档 Chunk → Embedding → Qdrant 入库。

Celery Queue: embedding
"""

from __future__ import annotations

from app.tasks.celery_app import celery_app
from app.rag.embedding import EmbeddingService
from app.core.qdrant import COLLECTION_ENTERPRISE, get_qdrant_client
from app.core.logger import get_logger

logger = get_logger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60, queue="embedding")
def batch_embed_document(self, document_id: str, chunk_ids: list[str]) -> dict:
    """批量对文档 Chunk 做 Embedding 并写入 Qdrant。

    Args:
        document_id: 文档 ID
        chunk_ids: 待处理的 chunk_id 列表

    Returns:
        {"document_id": "...", "processed": N, "failed": N}
    """
    logger.info("celery_embed_start", document_id=document_id, chunks=len(chunk_ids))

    # TODO: 从 MySQL knowledge_chunk 表读取 chunks
    # 当前使用内存存储（通过 KnowledgeService 共享）
    try:
        from app.services.knowledge_service import _chunks, _documents

        if document_id not in _chunks:
            return {"document_id": document_id, "error": "chunks not found"}

        emb_service = EmbeddingService(mock_mode=False)
        qdrant = get_qdrant_client()

        points = []
        processed = 0
        failed = 0

        for chunk in _chunks[document_id]:
            if chunk["status"] != "pending_embedding":
                continue

            try:
                vector = emb_service._mock_embed(chunk["content"])  # P6 使用 mock embedding
                vector_id = f"vec_{chunk['chunk_id']}"

                # 构建 Qdrant point
                payload = {
                    "content": chunk["content"],
                    "document_id": document_id,
                    "chunk_index": chunk["chunk_index"],
                    **chunk.get("metadata", {}),
                }

                points.append({
                    "id": vector_id,
                    "vector": vector,
                    "payload": payload,
                })

                chunk["vector_id"] = vector_id
                chunk["status"] = "embedded"
                processed += 1

            except Exception as e:
                chunk["status"] = "failed"
                failed += 1
                logger.error("embed_chunk_failed", chunk_id=chunk["chunk_id"], error=str(e))

        # 批量写入 Qdrant（Mock 模式下只记录日志，不实际写入）
        if points:
            try:
                qdrant.upsert(
                    collection_name=COLLECTION_ENTERPRISE,
                    points=points,
                )
                logger.info("qdrant_upsert_done", doc_id=document_id, points=len(points))
            except Exception as e:
                logger.error("qdrant_upsert_failed", doc_id=document_id, error=str(e))
                raise self.retry(exc=e)

        # 更新文档状态
        if document_id in _documents:
            _documents[document_id]["status"] = "ready"

        return {
            "document_id": document_id,
            "processed": processed,
            "failed": failed,
        }

    except Exception as e:
        logger.error("celery_embed_error", document_id=document_id, error=str(e))
        raise self.retry(exc=e)
