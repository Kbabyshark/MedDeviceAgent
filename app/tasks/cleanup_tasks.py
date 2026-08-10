"""
数据归档定时任务。

数据保留策略：
- agent_trace:      保留 90 天 → 归档后删除
- llm_call_record:  保留 180 天 → 归档后删除
- conversation:     保留 365 天
- conversation_message: 保留 365 天
- Redis session:    TTL 30 分钟自动过期（清理任务做兜底检查）
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.tasks.celery_app import celery_app
from app.core.logger import get_logger

logger = get_logger(__name__)

# 保留天數
TRACE_RETENTION_DAYS = 90
LLM_RECORD_RETENTION_DAYS = 180
CONVERSATION_RETENTION_DAYS = 365


@celery_app.task(queue="cleanup")
def cleanup_expired_traces() -> dict:
    """清理过期的 Trace 数据。

    每天凌晨 3:00 执行（celery beat 配置）。
    """
    now = datetime.now(timezone.utc)
    trace_cutoff = now - timedelta(days=TRACE_RETENTION_DAYS)
    llm_cutoff = now - timedelta(days=LLM_RECORD_RETENTION_DAYS)

    logger.info("cleanup_traces_start", trace_cutoff=trace_cutoff.isoformat())

    # TODO: 实际 MySQL 删除 / 归档
    # DELETE FROM agent_trace_node WHERE trace_id IN (
    #     SELECT trace_id FROM agent_trace WHERE start_time < :trace_cutoff
    # )
    # DELETE FROM agent_trace WHERE start_time < :trace_cutoff
    # DELETE FROM llm_call_record WHERE created_at < :llm_cutoff

    return {
        "traces_deleted": 0,
        "llm_records_deleted": 0,
        "trace_cutoff": trace_cutoff.isoformat(),
        "llm_cutoff": llm_cutoff.isoformat(),
    }


@celery_app.task(queue="cleanup")
def cleanup_expired_conversations() -> dict:
    """清理过期对话数据。"""
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=CONVERSATION_RETENTION_DAYS)

    logger.info("cleanup_conversations_start", cutoff=cutoff.isoformat())

    # TODO: 实际 MySQL 归档
    # DELETE FROM conversation_message WHERE session_id IN (
    #     SELECT session_id FROM conversation WHERE created_at < :cutoff AND status = 'closed'
    # )
    # DELETE FROM conversation WHERE created_at < :cutoff AND status = 'closed'

    return {
        "conversations_deleted": 0,
        "messages_deleted": 0,
        "cutoff": cutoff.isoformat(),
    }


@celery_app.task(queue="cleanup")
def cleanup_expired_redis_keys() -> dict:
    """清理 Redis 中的过期/孤立 Key。

    每 30 分钟执行（celery beat 配置）。
    主要清理：
    - 已过期的 Session 缓存残留
    - 孤儿 pending_action（超时未确认）
    - 孤儿分布式锁（进程崩溃残留）
    """
    logger.info("cleanup_redis_start")

    # TODO: SCAN Redis keys 并检查 TTL
    # - session:* 无 TTL 的 → 设置 TTL 30min
    # - pending:* 超时 30min → 删除
    # - lock:* 超时 60s → 删除

    return {
        "keys_scanned": 0,
        "keys_cleaned": 0,
    }


@celery_app.task(queue="cleanup")
def archive_traces_to_cold_storage() -> dict:
    """将过期 Trace 归档到冷存储（OSS / S3 / 本地文件）。

    保留策略：
    1. 导出 90 天前的 trace JSON
    2. 上传到 OSS
    3. 删除 MySQL 记录
    """
    logger.info("archive_traces_start")

    # TODO:
    # 1. SELECT * FROM agent_trace WHERE start_time < cutoff
    # 2. 导出为 JSON Lines → 压缩
    # 3. 上传 OSS → 验证 → 删除 MySQL

    return {
        "archived_traces": 0,
        "storage": "pending",
    }
