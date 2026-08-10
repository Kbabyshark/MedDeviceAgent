"""
Redis 分布式锁。

防止并发冲突（重复创建工单、重复转人工等）。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

from app.core.redis import RedisKeys, get_redis_client
from app.core.logger import get_logger

logger = get_logger(__name__)

DEFAULT_LOCK_TTL = 30  # 锁默认 30 秒


class DistributedLock:
    """Redis 分布式锁。

    使用方式：
        lock = DistributedLock("create_ticket", user_id="10001", resource_id="SN001")
        async with lock.acquire():
            await do_critical_operation()
    """

    def __init__(
        self,
        action: str,
        user_id: str,
        resource_id: str = "",
        ttl: int = DEFAULT_LOCK_TTL,
    ) -> None:
        self._key = RedisKeys.lock(action, user_id, resource_id)
        self._ttl = ttl
        self._token = str(uuid.uuid4())

    @asynccontextmanager
    async def acquire(self):
        """尝试获取锁。获取失败则抛出异常。"""
        redis = await get_redis_client()
        acquired = await redis.set(
            self._key,
            self._token,
            nx=True,  # 仅当 key 不存在时设置
            ex=self._ttl,
        )

        if not acquired:
            logger.warning("lock_failed", key=self._key)
            raise LockAcquireError(f"操作过于频繁，请稍后重试。lock: {self._key}")

        logger.debug("lock_acquired", key=self._key, ttl=self._ttl)

        try:
            yield
        finally:
            # Lua 脚本：原子性释放（仅当 token 匹配）
            lua_script = """
            if redis.call("get", KEYS[1]) == ARGV[1] then
                return redis.call("del", KEYS[1])
            else
                return 0
            end
            """
            await redis.eval(lua_script, 1, self._key, self._token)
            logger.debug("lock_released", key=self._key)

    async def extend(self, extra_ttl: int = DEFAULT_LOCK_TTL) -> bool:
        """延长锁的 TTL（仅在持有锁时有效）。"""
        redis = await get_redis_client()
        lua_script = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("expire", KEYS[1], ARGV[2])
        else
            return 0
        end
        """
        result = await redis.eval(lua_script, 1, self._key, self._token, extra_ttl)
        return bool(result)


class LockAcquireError(Exception):
    """获取锁失败异常。"""
    pass


@asynccontextmanager
async def with_ticket_lock(user_id: str, device_sn: str):
    """创建工单的分布式锁（便捷方法）。"""
    lock = DistributedLock("create_ticket", user_id=user_id, resource_id=device_sn, ttl=30)
    async with lock.acquire():
        yield


@asynccontextmanager
async def with_transfer_lock(user_id: str):
    """转人工的分布式锁（便捷方法）。"""
    lock = DistributedLock("transfer_human", user_id=user_id, ttl=30)
    async with lock.acquire():
        yield
