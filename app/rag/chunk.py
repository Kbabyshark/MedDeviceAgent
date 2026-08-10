"""
文档 Chunk 切分服务。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ChunkResult:
    """Chunk 切分结果。"""
    content: str
    chunk_index: int
    metadata: dict


class DocumentChunker:
    """文档分块器。"""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 64) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str, metadata: dict | None = None) -> list[ChunkResult]:
        """将文档文本切分为 Chunk 列表。"""
        meta = metadata or {}
        chunks: list[ChunkResult] = []

        text_len = len(text)
        start = 0
        idx = 0
        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk_text = text[start:end]
            chunks.append(ChunkResult(
                content=chunk_text,
                chunk_index=idx,
                metadata={**meta, "chunk_index": idx},
            ))
            idx += 1
            if end >= text_len:
                break
            start = end - self.chunk_overlap
            if idx > 10000:  # 安全阀
                logger.warning("chunk_limit_exceeded", text_len=text_len)
                break

        return chunks
