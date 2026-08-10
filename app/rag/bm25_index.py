"""
BM25 关键词索引 — SQLite FTS5 引擎，文件持久化。

- 启动无需加载，直接可用
- 上传文档时 INSERT，即时生效
- 删除文档时 DELETE，即时生效
- 重启不丢数据

表结构：
  bm25_index (chunk_id TEXT PK, content TEXT, tokens TEXT,
              doc_type TEXT, device_type TEXT, permission TEXT,
              document_id TEXT, doc_name TEXT, chunk_index INT)
  虚拟列 tokens 用于 FTS5 全文本匹配（jieba 分词后空格拼接）。
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from app.core.logger import get_logger

logger = get_logger(__name__)

_DB_PATH = Path(__file__).resolve().parent.parent.parent / ".data" / "bm25_fts.db"
_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS bm25_index USING fts5(
            chunk_id,
            content,
            tokens,
            doc_type,
            device_type,
            permission,
            document_id,
            doc_name,
            chunk_index,
            tokenize='unicode61',
            prefix='2'
        )
    """)
    conn.commit()


def _tokenize(text: str) -> str:
    """jieba 分词 → 空格拼接。"""
    import jieba
    return " ".join(t for t in jieba.cut(text) if len(t.strip()) > 1)


def build() -> None:
    """全量从 Qdrant 加载到 FTS5（仅首次初始化用）。同时确保建表。"""
    try:
        from app.core.qdrant import get_qdrant_client, COLLECTION_ENTERPRISE
        qd = get_qdrant_client()
        conn = _get_conn()
        _ensure_table(conn)

        # 检查是否已有数据
        row = conn.execute("SELECT COUNT(*) FROM bm25_index").fetchone()
        if row and row[0] > 0:
            logger.info("bm25_skip_build", existing=row[0])
            conn.close()
            return

        pts: list = []
        offset: str | int | None = None
        while True:
            batch, next_offset = qd.scroll(
                collection_name=COLLECTION_ENTERPRISE,
                limit=1000, with_payload=True, with_vectors=False, offset=offset,
            )
            if not batch: break
            pts.extend(batch)
            offset = next_offset
            if not offset: break

        with _lock:
            conn.execute("DELETE FROM bm25_index")  # 清空旧数据
            for p in pts:
                pl = p.payload or {}
                content = pl.get("content", "")
                if not content: continue
                tokens = _tokenize(content)
                conn.execute(
                    "INSERT INTO bm25_index(chunk_id, content, tokens, doc_type, device_type, permission, document_id, doc_name, chunk_index) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(p.id), content, tokens,
                     pl.get("doc_type", ""), pl.get("device_type", ""), pl.get("permission", ""),
                     pl.get("document_id", ""), pl.get("name", ""), pl.get("chunk_index", 0)),
                )
            conn.commit()
        conn.close()
        logger.info("bm25_built", docs_count=len(pts))
    except Exception as e:
        logger.error("bm25_build_failed", error=str(e))


def add_chunks(chunks: list[dict]) -> None:
    """增量追加 chunk。chunks: [{id, payload: {content, ...}}]."""
    try:
        conn = _get_conn()
        _ensure_table(conn)
        with _lock:
            for c in chunks:
                pl = c.get("payload") or c
                if not isinstance(pl, dict): continue
                content = pl.get("content", "")
                if not content: continue
                tokens = _tokenize(content)
                conn.execute(
                    "INSERT OR REPLACE INTO bm25_index(chunk_id, content, tokens, doc_type, device_type, permission, document_id, doc_name, chunk_index) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (str(c.get("id", "")), content, tokens,
                     pl.get("doc_type", ""), pl.get("device_type", ""), pl.get("permission", ""),
                     pl.get("document_id", ""), pl.get("name", ""), pl.get("chunk_index", 0)),
                )
            conn.commit()
        conn.close()
        logger.info("bm25_added", added=len(chunks))
    except Exception as e:
        logger.error("bm25_add_failed", error=str(e))


def remove_chunks(doc_id: str) -> None:
    """按 document_id 移除 chunk。"""
    try:
        conn = _get_conn()
        _ensure_table(conn)
        with _lock:
            cur = conn.execute("DELETE FROM bm25_index WHERE document_id = ?", (doc_id,))
            conn.commit()
        conn.close()
        if cur.rowcount:
            logger.info("bm25_removed", removed=cur.rowcount)
    except Exception as e:
        logger.error("bm25_remove_failed", error=str(e))


def search(query: str, top_k: int = 20) -> list[dict]:
    """FTS5 BM25 检索。对 jieba 分词后的 query 做 MATCH，按 BM25 score 排序。"""
    try:
        conn = _get_conn()
        _ensure_table(conn)

        tokens = _tokenize(query)
        if not tokens.strip():
            conn.close()
            return []

        # FTS5 MATCH 语法：每个词前缀+AND
        fts_query = " AND ".join(f'"{t}"' for t in tokens.split()[:10])
        rows = conn.execute(
            "SELECT chunk_id, content, doc_type, device_type, permission, "
            "document_id, doc_name, chunk_index, bm25(bm25_index, 0) AS score "
            "FROM bm25_index WHERE bm25_index MATCH ? ORDER BY score LIMIT ?",
            (fts_query, top_k),
        ).fetchall()
        conn.close()

        results = []
        for r in rows:
            results.append({
                "id": r[0],
                "score": float(r[8]) if r[8] else 0.0,
                "payload": {
                    "content": r[1], "doc_type": r[2], "device_type": r[3],
                    "permission": r[4], "document_id": r[5], "name": r[6],
                    "chunk_index": r[7],
                },
            })
        return results
    except Exception as e:
        logger.error("bm25_search_failed", error=str(e))
        return []
