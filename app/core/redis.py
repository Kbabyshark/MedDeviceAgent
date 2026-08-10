"""
Redis 客户端封装。

提供连接池管理、Key 规范生成、常用操作封装。
Key 格式：业务:类型:ID
"""

from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import get_settings

# 全局 Redis 连接池（进程级单例）
_pool: aioredis.ConnectionPool | None = None
_client: aioredis.Redis | None = None


def _build_key(business: str, obj_type: str, obj_id: str) -> str:
    """生成 Redis Key，格式: 业务:类型:ID"""
    return f"{business}:{obj_type}:{obj_id}"


async def get_redis_client() -> aioredis.Redis:
    """获取 Redis 客户端实例。"""
    global _client, _pool
    if _client is None:
        settings = get_settings()
        _pool = aioredis.ConnectionPool.from_url(
            settings.redis.url,
            max_connections=50,
            decode_responses=True,
        )
        _client = aioredis.Redis(connection_pool=_pool)
    return _client


async def close_redis() -> None:
    """关闭 Redis 连接（app shutdown 时调用）。"""
    global _client, _pool
    if _client:
        await _client.close()
        _client = None
    if _pool:
        await _pool.disconnect()
        _pool = None


async def check_redis_health() -> dict:
    """Redis 健康检查（仅验证配置，不实际 ping）。"""
    settings = get_settings()
    return {
        "status": "configured",
        "host": settings.redis.host,
        "port": settings.redis.port,
        "db": settings.redis.db,
    }


# ---- Key 常量（遵循 业务:类型:ID 规范）----


class RedisKeys:
    """Redis Key 命名空间。"""

    # 限流
    @staticmethod
    def rate_limit(action: str, user_id: str) -> str:
        return _build_key("rate_limit", action, user_id)

    # 分布式锁
    @staticmethod
    def lock(action: str, user_id: str, resource_id: str = "") -> str:
        key = _build_key("lock", action, user_id)
        return f"{key}:{resource_id}" if resource_id else key

    # Session 缓存
    @staticmethod
    def session(session_id: str) -> str:
        return _build_key("session", "cache", session_id)

    # AB Test 分组
    @staticmethod
    def ab_experiment(experiment_name: str, user_id: str) -> str:
        return _build_key("ab", experiment_name, user_id)
