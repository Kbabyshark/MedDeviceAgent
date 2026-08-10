"""
rag_retrieve_node

RAG 检索：Embedding → Qdrant 向量搜索 → Metadata 过滤 → Top-K。
"""

from __future__ import annotations

from app.agent.state import AgentState
from app.core.qdrant import COLLECTION_ENTERPRISE, get_qdrant_client
from app.rag.embedding import EmbeddingService
from app.core.logger import get_logger

logger = get_logger(__name__)

_DEFAULT_TOP_K = 20


async def rag_retrieve_node(state: AgentState) -> dict:
    """RAG 检索节点。

    流程：
    1. 从多意图提取 doc_type 集合，合并搜索
    2. Query Embedding
    3. Qdrant 向量检索（Top-K=20）
    4. 返回 retrieved_docs
    """
    query = state.get("query", "")
    device_info = state.get("device_info", {})
    trace_id = state.get("trace_id", "")
    intent = state.get("intent", "")
    intents = state.get("intents", [])

    # ---- 多意图 → 多 doc_type 合并 ----
    doc_types = set()
    for it in intents:
        dt = _map_intent_to_doc_type(it.get("intent", ""))
        if dt:
            doc_types.add(dt)
    if not doc_types:
        dt = _map_intent_to_doc_type(intent)
        if dt:
            doc_types.add(dt)

    device_type = device_info.get("device_type", "")
    permission = "public"

    logger.info(
        "rag_retrieve_start",
        query=query[:100],
        filter={"device_type": device_type, "doc_types": list(doc_types), "permission": permission},
        trace_id=trace_id,
    )

    try:
        # ---- Embedding ----
        emb_service = EmbeddingService()
        query_vector = await emb_service.embed(query)

        # ---- Hybrid Retrieval: 向量 + BM25 ----
        from qdrant_client.models import Filter, FieldCondition, MatchAny, MatchValue
        qdrant = get_qdrant_client()

        must_conditions = []
        if device_type:
            must_conditions.append(FieldCondition(key="device_type", match=MatchValue(value=device_type)))
        if doc_types:
            must_conditions.append(FieldCondition(key="doc_type", match=MatchAny(any=list(doc_types))))
        must_conditions.append(FieldCondition(key="permission", match=MatchValue(value=permission)))

        # 向量检索
        vector_points = qdrant.query_points(
            collection_name=COLLECTION_ENTERPRISE,
            query=query_vector,
            query_filter=Filter(must=must_conditions),
            limit=_DEFAULT_TOP_K,
            with_payload=True,
        ).points

        # BM25 检索
        from app.rag.bm25_index import search as bm25_search
        bm25_results_raw = bm25_search(query, top_k=_DEFAULT_TOP_K)
        logger.info("rag_retrieve_bm25_hits", count=len(bm25_results_raw), trace_id=trace_id)
        # BM25 结果按 metadata filter 筛选
        bm25_results = [r for r in bm25_results_raw if _match_filter(r["payload"], device_type, doc_types, permission)]

        # RRF 融合
        K = 60
        fused: dict[str, dict] = {}
        for rank, pt in enumerate(vector_points):
            pid = str(pt.id)
            fused[pid] = {"point": pt, "rrf": 1.0 / (K + rank + 1)}
        for rank, bm in enumerate(bm25_results):
            pid = str(bm["id"])
            if pid in fused:
                fused[pid]["rrf"] += 1.0 / (K + rank + 1)
            else:
                fused[pid] = {"point": bm, "rrf": 1.0 / (K + rank + 1)}

        sorted_fused = sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)[:_DEFAULT_TOP_K]

        # 精确 filter 没命中 → 放宽：去掉 doc_type，permission 也放宽
        if not sorted_fused and doc_types:
            logger.info("rag_retrieve_fallback_relax", trace_id=trace_id, doc_types=list(doc_types))
            # 只保留 device_type filter，去掉 doc_type 和 permission
            relaxed_filter = [c for c in must_conditions if c.key == "device_type"]
            vector_points = qdrant.query_points(
                collection_name=COLLECTION_ENTERPRISE,
                query=query_vector,
                query_filter=Filter(must=relaxed_filter),
                limit=_DEFAULT_TOP_K, with_payload=True,
            ).points
            bm25_results = [r for r in bm25_results_raw if _match_filter_relaxed(r["payload"], device_type)]
            fused.clear()
            for rank, pt in enumerate(vector_points):
                fused[str(pt.id)] = {"point": pt, "rrf": 1.0 / (60 + rank + 1)}
            for rank, bm in enumerate(bm25_results):
                pid = str(bm["id"])
                if pid in fused: fused[pid]["rrf"] += 1.0 / (60 + rank + 1)
                else: fused[pid] = {"point": bm, "rrf": 1.0 / (60 + rank + 1)}
            sorted_fused = sorted(fused.values(), key=lambda x: x["rrf"], reverse=True)[:_DEFAULT_TOP_K]

        logger.info("rag_retrieve_hybrid", vector_hits=len(vector_points),
                     bm25_hits=len(bm25_results), fused_count=len(sorted_fused),
                     trace_id=trace_id)

        # 转为统一格式
        results_raw = []
        for item in sorted_fused:
            p = item["point"]
            if hasattr(p, "payload"):  # Qdrant point
                results_raw.append({"id": str(p.id), "score": item["rrf"], "payload": p.payload or {}})
            else:  # BM25 dict
                results_raw.append({"id": str(p["id"]), "score": item["rrf"], "payload": p["payload"]})

        # ---- 转换为标准格式 ----
        retrieved_docs = []
        for point in results_raw:
            payload = point["payload"]
            retrieved_docs.append({
                "content": payload.get("content", ""),
                "metadata": {
                    "document_id": payload.get("document_id", ""),
                    "name": payload.get("name", ""),
                    "device_type": payload.get("device_type", ""),
                    "doc_type": payload.get("doc_type", ""),
                    "version": payload.get("version", ""),
                    "chunk_index": payload.get("chunk_index", 0),
                },
                "score": round(point["score"], 4) if point.get("score") else 0,
                "vector_id": point["id"],
            })

        for i, doc in enumerate(retrieved_docs[:5]):
            print(f"\n[CHUNK #{i}] score={doc['score']:.4f} doc={doc['metadata'].get('name','')[:50]} chunk_idx={doc['metadata'].get('chunk_index',0)}", flush=True)
            print(f"  {doc['content'][:500]}", flush=True)

        logger.info(
            "rag_retrieve_done",
            doc_count=len(retrieved_docs),
            top_score=retrieved_docs[0]["score"] if retrieved_docs else 0,
            trace_id=trace_id,
        )

        return {
            "retrieved_docs": retrieved_docs,
            "metadata_filter": {
                "device_type": device_type,
                "doc_types": list(doc_types),
                "permission": permission,
            },
        }

    except Exception as e:
        logger.error("rag_retrieve_error", error=str(e), trace_id=trace_id)
        return {"retrieved_docs": [], "metadata_filter": {}}


def _map_intent_to_doc_type(intent: str) -> str:
    """根据意图映射到知识库文档类型。"""
    mapping = {
        "faq_query": "faq",
        "device_info_query": "manual",
        "fault_code_query": "fault_code",
        "troubleshooting": "fault_code",
        "policy_query": "policy",
    }
    return mapping.get(intent, "")  # 空 = 不限制类型，全库搜索


def _match_filter(payload: dict, device_type: str, doc_types: set[str], permission: str) -> bool:
    """检查 payload 是否满足 metadata 过滤条件。"""
    if permission and payload.get("permission", "") != permission:
        return False
    if device_type and payload.get("device_type", "") != device_type:
        return False
    if doc_types and payload.get("doc_type", "") not in doc_types:
        return False
    return True


def _match_filter_relaxed(payload: dict, device_type: str) -> bool:
    """fallback filter：只检查 device_type，放弃 doc_type 和 permission。"""
    if device_type and payload.get("device_type", "") != device_type:
        return False
    return True






