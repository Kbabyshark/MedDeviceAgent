"""
Embedding 服务 — BGE 模型（首次使用自动从 HuggingFace 下载）。
"""

from __future__ import annotations

from app.core.logger import get_logger

logger = get_logger(__name__)

# 延迟加载
_model = None
_DIM = 1024  # BGE-small-zh-v1.5 实际维度: 512


def _get_model():
    global _model, _DIM
    if _model is not None:
        return _model
    import os
    from pathlib import Path
    from sentence_transformers import SentenceTransformer
    # ModelScope 下载到本地，不走 HuggingFace 网络
    local_path = Path(__file__).resolve().parent.parent.parent / "models" / "bge-small-zh-v1.5"
    if local_path.exists():
        os.environ["HF_HUB_OFFLINE"] = "1"  # 禁止联网检查
        _model = SentenceTransformer(str(local_path))
    else:
        _model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
    _DIM = _model.get_embedding_dimension()
    logger.info("embedding_loaded", model="BAAI/bge-small-zh-v1.5", dim=_DIM)
    return _model


class EmbeddingService:
    def __init__(self):
        _get_model()  # 触发首次加载

    @property
    def dim(self) -> int:
        return _DIM

    async def embed(self, text: str) -> list[float]:
        m = _get_model()
        return m.encode(text, normalize_embeddings=True).tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        m = _get_model()
        vecs = m.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vecs.tolist()