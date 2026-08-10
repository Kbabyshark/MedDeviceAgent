"""KnowledgeService — MySQL 持久化（pymysql 同步驱动）。"""
from __future__ import annotations

import asyncio, hashlib, threading, uuid
from datetime import datetime, timezone

import pymysql

from app.core.config import get_settings
from app.rag.parser import DocumentParser
from app.rag.chunk import DocumentChunker
from app.core.logger import get_logger

logger = get_logger(__name__)
_parser = DocumentParser()
_chunker = DocumentChunker(chunk_size=512, chunk_overlap=64)


def _ensure_columns():
    """自动补全 knowledge_document 缺失的列。"""
    c = _conn(); cur = c.cursor()
    cur.execute("SHOW COLUMNS FROM knowledge_document")
    cols = {r[0] for r in cur.fetchall()}
    for col, spec in [("doc_id", "VARCHAR(32)"), ("chunk_count", "INT NOT NULL DEFAULT 0")]:
        if col not in cols:
            cur.execute(f"ALTER TABLE knowledge_document ADD COLUMN {col} {spec}")
    c.commit(); c.close()


def _conn():
    s = get_settings().mysql
    return pymysql.connect(host="127.0.0.1", port=s.port, user=s.user, password=s.password,
                           database=s.database, charset="utf8mb4")


class KnowledgeService:
    def __init__(self):
        _ensure_columns()

    async def upload(self, content: bytes, filename: str, device_type: str,
                     doc_type: str, version: str = "v1", permission: str = "public",
                     uploaded_by: str = "") -> dict:
        doc_id = f"doc_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        # 1. MinIO
        try:
            from app.core.storage import upload_file as minio_upload
            minio_upload(f"documents/{doc_id}/{filename}", content)
        except Exception as e:
            logger.warning("minio_upload_failed", error=str(e))

        # 2. MySQL
        try:
            c = _conn()
            cur = c.cursor()
            cur.execute(
                "INSERT INTO knowledge_document (doc_id, name, device_type, doc_type, version, permission, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (doc_id, filename, device_type, doc_type, version, permission, now, now))
            c.commit(); c.close()
        except Exception as e:
            logger.error("mysql_insert_failed", error=str(e))

        # 3. 后台线程
        t = threading.Thread(target=self._process_bg, args=(doc_id, content, filename, device_type, doc_type, version, permission), daemon=True)
        t.start()

        logger.info("knowledge_uploaded", doc_id=doc_id)
        return {"document_id": doc_id, "name": filename, "status": "processing", "created_at": now.isoformat(),
                "device_type": device_type, "doc_type": doc_type, "version": version,
                "permission": permission, "chunk_count": 0, "uploaded_by": uploaded_by}

    def _process_bg(self, doc_id, content, filename, device_type, doc_type, version, permission):
        _log = get_logger(__name__)
        try:
            async def _run():
                # Step 1: 解析文档
                pr = await _parser.parse(content, filename=filename)
                text_len = len(pr.text.strip())
                if text_len == 0:
                    _log.error("process_parse_empty", doc_id=doc_id)
                    self._update_mysql(doc_id, "failed")
                    return

                # Step 2: 切分
                md = {"device_type": device_type, "doc_type": doc_type, "version": version,
                      "permission": permission, "document_id": doc_id, "name": filename}
                chunks = _chunker.chunk(pr.text, metadata=md)

                # Step 3: 向量化
                from app.rag.embedding import EmbeddingService
                from app.core.qdrant import get_qdrant_client, COLLECTION_ENTERPRISE
                emb = EmbeddingService()
                texts = [c.content for c in chunks]
                vecs = await emb.embed_batch(texts)

                # Step 4: 连接 Qdrant
                qd = get_qdrant_client()
                from qdrant_client.models import Distance, VectorParams, PointStruct
                try:
                    qd.create_collection(COLLECTION_ENTERPRISE, vectors_config=VectorParams(size=emb.dim, distance=Distance.COSINE))
                    _log.info("qdrant_collection_created", collection=COLLECTION_ENTERPRISE)
                except Exception:
                    pass

                # Step 5: 入库 Qdrant（local 模式要求 point id 为合法 UUID）
                _ns = uuid.uuid5(uuid.NAMESPACE_DNS, "smart-voice-agent")
                pts = [PointStruct(
                    id=str(uuid.uuid5(_ns, f"{doc_id}:{i}")),
                    vector=vecs[i],
                    payload={
                        "content": c.content, "document_id": doc_id, "chunk_index": i,
                        "name": filename, "device_type": device_type, "doc_type": doc_type,
                        "version": version, "permission": permission,
                    },
                ) for i, c in enumerate(chunks)]
                qd.upsert(COLLECTION_ENTERPRISE, pts)

                # Step 6: 更新 MySQL 状态
                self._update_mysql(doc_id, "ready", len(chunks))
                _log.info("process_done", doc_id=doc_id, chunks=len(chunks), chars=text_len)

                # BM25 增量追加（不扫全库）
                from app.rag.bm25_index import add_chunks
                chunk_dicts = [{"id": p.id, "payload": p.payload} for p in pts]
                add_chunks(chunk_dicts)

            asyncio.run(_run())
        except Exception as e:
            import traceback
            traceback.print_exc()
            logger.error("process_error", doc_id=doc_id, error=str(e))
            self._update_mysql(doc_id, "failed")

    def _update_mysql(self, doc_id, status, chunk_count=0):
        try:
            c = _conn()
            cur = c.cursor()
            cur.execute("UPDATE knowledge_document SET status=%s, chunk_count=%s WHERE doc_id=%s",
                        (status, chunk_count, doc_id))
            c.commit(); c.close()
        except Exception as e:
            logger.error("mysql_update_failed", doc_id=doc_id, status=status, error=str(e))

    async def list_documents(self, device_type: str = "", doc_type: str = "",
                             page: int = 1, page_size: int = 20) -> dict:
        c = _conn()
        wheres = []; params = []
        if device_type: wheres.append("device_type=%s"); params.append(device_type)
        if doc_type: wheres.append("doc_type=%s"); params.append(doc_type)
        w = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        cur = c.cursor()
        cur.execute(f"SELECT COUNT(*) FROM knowledge_document {w}", params)
        total = cur.fetchone()[0]
        off = (page - 1) * page_size
        cur.execute(f"SELECT COALESCE(doc_id,''),name,device_type,doc_type,version,permission,status,COALESCE(chunk_count,0),created_at FROM knowledge_document {w} ORDER BY created_at DESC LIMIT %s OFFSET %s", params + [page_size, off])
        rows = cur.fetchall()
        c.close()
        return {
            "items": [{"document_id": r[0] or f"doc_{r[1][:8]}", "name": r[1], "device_type": r[2], "doc_type": r[3],
                       "version": r[4], "permission": r[5], "status": r[6], "chunk_count": r[7],
                       "created_at": r[8].isoformat() if r[8] else None} for r in rows],
            "total": total, "page": page, "page_size": page_size,
        }

    async def update_document(self, doc_id: str, device_type: str = "", doc_type: str = "",
                               version: str = "", permission: str = "") -> bool:
        """编辑文档元数据。"""
        c = _conn()
        cur = c.cursor()
        fields = []; vals = []
        if device_type: fields.append("device_type=%s"); vals.append(device_type)
        if doc_type: fields.append("doc_type=%s"); vals.append(doc_type)
        if version: fields.append("version=%s"); vals.append(version)
        if permission: fields.append("permission=%s"); vals.append(permission)
        if not fields: c.close(); return False
        fields.append("updated_at=%s"); vals.append(datetime.now(timezone.utc))
        vals.append(doc_id)
        sql = f"UPDATE knowledge_document SET {', '.join(fields)} WHERE doc_id=%s"
        r = cur.execute(sql, vals)
        c.commit(); c.close()

        # 同步更新 Qdrant 中所有 chunk 的 payload（local 模式 set_payload 会覆盖，需先读再合并）
        try:
            from app.core.qdrant import get_qdrant_client, COLLECTION_ENTERPRISE
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            qd = get_qdrant_client()
            pts, _ = qd.scroll(
                collection_name=COLLECTION_ENTERPRISE,
                scroll_filter=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]),
                with_payload=True, with_vectors=False, limit=10000,
            )
            if pts:
                updates = {k: v for k, v in [("device_type", device_type),
                    ("doc_type", doc_type), ("version", version), ("permission", permission)] if v}
                for p in pts:
                    merged = {**(p.payload or {}), **updates}
                    qd.set_payload(collection_name=COLLECTION_ENTERPRISE, payload=merged, points=[p.id])
        except Exception as e:
            logger.error("qdrant_payload_update_failed", doc_id=doc_id, error=str(e))

        return r > 0

    async def delete_document(self, doc_id: str) -> bool:
        c = _conn()
        cur = c.cursor()
        cur.execute("DELETE FROM knowledge_chunk WHERE document_id=(SELECT id FROM knowledge_document WHERE doc_id=%s)", (doc_id,))
        r = cur.execute("DELETE FROM knowledge_document WHERE doc_id=%s", (doc_id,))
        c.commit(); c.close()
        # 同步删除 BM25 索引
        from app.rag.bm25_index import remove_chunks
        remove_chunks(doc_id)

        # 同步删除 Qdrant 中的向量
        try:
            from app.core.qdrant import get_qdrant_client, COLLECTION_ENTERPRISE
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            qd = get_qdrant_client()
            pts, _ = qd.scroll(
                collection_name=COLLECTION_ENTERPRISE,
                scroll_filter=Filter(must=[FieldCondition(key="document_id", match=MatchValue(value=doc_id))]),
                with_payload=False, with_vectors=False, limit=10000,
            )
            if pts:
                qd.delete(collection_name=COLLECTION_ENTERPRISE, points_selector=[p.id for p in pts])
        except Exception as e:
            logger.error("qdrant_delete_failed", doc_id=doc_id, error=str(e))
        return r > 0

    async def get_document_status(self, doc_id: str) -> dict | None:
        c = _conn()
        cur = c.cursor()
        cur.execute("SELECT name,version,status,COALESCE(chunk_count,0),created_at,updated_at FROM knowledge_document WHERE doc_id=%s LIMIT 1", (doc_id,))
        row = cur.fetchone()
        c.close()
        if not row: return None
        return {"document_id": doc_id, "name": row[0], "version": row[1], "status": row[2],
                "chunks_total": row[3], "chunks_embedded": row[3], "chunks_pending": 0, "chunks_failed": 0,
                "created_at": row[4].isoformat() if row[4] else None, "updated_at": row[5].isoformat() if row[5] else None}