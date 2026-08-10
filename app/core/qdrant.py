"""
Qdrant 向量数据库客户端封装。

Collection 设计：
- enterprise_knowledge：企业公共知识库
- user_summary：用户历史摘要（按 user_id 隔离）
"""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CollectionStatus,
    Distance,
    VectorParams,
)

from app.core.config import get_settings

# 全局客户端（进程级单例）
_client: QdrantClient | None = None

# Collection 定义
COLLECTION_ENTERPRISE = "enterprise_knowledge"
COLLECTION_USER_SUMMARY = "user_summary"

# 向量维度（从配置读取）
_EMBEDDING_DIM = 1536


def get_qdrant_client() -> QdrantClient:
    """获取 Qdrant 客户端实例。开发环境使用本地文件模式，无需单独服务。"""
    global _client
    if _client is None:
        settings = get_settings()
        if settings.app_debug:
            import os
            p = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".qdrant_data")
            _client = QdrantClient(path=p)
        else:
            _client = QdrantClient(
                host=settings.qdrant.host,
                port=settings.qdrant.port,
                api_key=settings.qdrant.api_key or None,
            )
    return _client


def get_collection_schemas() -> dict[str, VectorParams]:
    """返回 Collection 的向量参数定义。"""
    settings = get_settings()
    dim = settings.embedding.dim
    return {
        COLLECTION_ENTERPRISE: VectorParams(
            size=dim,
            distance=Distance.COSINE,
        ),
        COLLECTION_USER_SUMMARY: VectorParams(
            size=dim,
            distance=Distance.COSINE,
        ),
    }


def get_enterprise_metadata_schema() -> dict:
    """企业知识库 metadata 字段说明（用于文档和校验）。"""
    return {
        "device_type": {"type": "keyword", "description": "设备型号"},
        "doc_type": {"type": "keyword", "description": "文档类型: manual/faq/fault_code/policy"},
        "version": {"type": "keyword", "description": "文档版本"},
        "permission": {"type": "keyword", "description": "权限级别: public/internal/restricted"},
        "document_id": {"type": "integer", "description": "关联 knowledge_document.id"},
        "chunk_index": {"type": "integer", "description": "分块序号"},
    }


def get_user_summary_metadata_schema() -> dict:
    """用户 Summary 向量库 metadata 字段说明。"""
    return {
        "user_id": {"type": "keyword", "description": "用户ID（检索时必须过滤）"},
        "session_id": {"type": "keyword", "description": "会话ID"},
        "version": {"type": "integer", "description": "摘要版本"},
    }


async def check_qdrant_health() -> dict:
    """Qdrant 健康检查（仅验证配置，不实际连接）。"""
    settings = get_settings()
    return {
        "status": "configured",
        "host": settings.qdrant.host,
        "port": settings.qdrant.port,
        "collections": [COLLECTION_ENTERPRISE, COLLECTION_USER_SUMMARY],
    }
