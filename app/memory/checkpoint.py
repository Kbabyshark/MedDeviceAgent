"""
LangGraph Checkpoint 管理（MySQL 后端）。

使用 LangGraph 内置的 AsyncMySQLSaver 实现 Agent 状态持久化。
支持 Workflow 中断恢复、多轮任务状态保持。
"""

from __future__ import annotations

try:
    from langgraph.checkpoint.mysql.aio import AsyncMySQLSaver
except ImportError:
    AsyncMySQLSaver = None  # type: ignore[assignment]

from app.core.config import get_settings
from app.core.logger import get_logger

logger = get_logger(__name__)

# 全局 Checkpointer 实例
_checkpointer = None  # AsyncMySQLSaver | None


async def get_checkpointer():
    """获取或创建 MySQL Checkpointer。

    连接失败时返回 None（降级为内存模式），不阻止 Agent 启动。
    """
    global _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    settings = get_settings()
    if AsyncMySQLSaver is None:
        logger.warning("checkpointer_unavailable", hint="langgraph mysql module not installed")
        return None
    try:
        _checkpointer = AsyncMySQLSaver.from_conn_string(settings.mysql.database_url_sync)
        await _checkpointer.setup()
        logger.info("checkpointer_connected", host=settings.mysql.host, database=settings.mysql.database)
    except Exception as e:
        logger.warning("checkpointer_connect_failed", error=str(e), hint="降级为内存模式，会话重启后状态丢失")
        _checkpointer = None

    return _checkpointer


async def close_checkpointer() -> None:
    """关闭 Checkpointer 连接。"""
    global _checkpointer
    if _checkpointer:
        await _checkpointer.close()
        _checkpointer = None
        logger.info("checkpointer_closed")


def get_checkpointer_sync():
    """同步获取 checkpointer（用于 graph 编译）。"""
    return _checkpointer
