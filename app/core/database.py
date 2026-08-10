"""
数据库引擎和会话管理。

SQLAlchemy 2.x 异步引擎，连接池配置，Session 工厂。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

# 全局引擎（进程级单例）
_engine = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    """获取或创建异步数据库引擎。"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.mysql.database_url,
            pool_size=settings.mysql.pool_size,
            pool_recycle=settings.mysql.pool_recycle,
            pool_pre_ping=True,          # 连接前检测可用性
            echo=False,
            connect_args={
                "charset": "utf8mb4",
            },
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """获取异步 Session 工厂。"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


async def get_db_session() -> AsyncSession:
    """获取一个数据库会话（用于 FastAPI Depends）。"""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_database_health() -> dict:
    """数据库健康检查（不实际连接，仅验证配置和引擎状态）。"""
    settings = get_settings()
    return {
        "status": "configured",
        "host": settings.mysql.host,
        "port": settings.mysql.port,
        "database": settings.mysql.database,
        "pool_size": settings.mysql.pool_size,
        "engine_created": _engine is not None,
    }
