"""
告警规则模块。

定义关键指标的告警阈值和通知方式。

告警规则：
- Agent 失败率 > 5% → WARNING
- Agent 失败率 > 10% → CRITICAL
- LLM 调用失败率 > 3% → WARNING
- RAG 检索空结果率 > 20% → WARNING
- 请求 P95 > 5s → WARNING
- 请求 P95 > 10s → CRITICAL
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from app.core.logger import get_logger

logger = get_logger(__name__)


class AlertLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """告警规则定义。"""

    name: str
    description: str
    level: AlertLevel
    threshold: float
    metric_fn: Callable[[], float]  # 返回当前指标值
    cooldown_seconds: int = 300     # 冷却时间（秒），避免重复告警

    _last_alerted: float = field(default=0.0, init=False, repr=False)


# ================================================================
# 内置告警规则
# ================================================================


_alert_rules: list[AlertRule] = []


def register_alert_rule(rule: AlertRule) -> None:
    """注册告警规则。"""
    _alert_rules.append(rule)


def get_alert_rules() -> list[AlertRule]:
    return _alert_rules


async def check_all_alerts() -> list[dict]:
    """检查所有告警规则，触发超阈值的告警。

    Returns:
        触发告警的规则列表 [{name, level, current_value, threshold}]
    """
    import time as _time
    triggered = []

    for rule in _alert_rules:
        now = _time.time()
        if now - rule._last_alerted < rule.cooldown_seconds:
            continue

        try:
            current = rule.metric_fn()
        except Exception as e:
            logger.error("alert_metric_error", rule=rule.name, error=str(e))
            continue

        if current > rule.threshold:
            rule._last_alerted = now
            triggered.append({
                "name": rule.name,
                "level": rule.level.value,
                "description": rule.description,
                "current_value": current,
                "threshold": rule.threshold,
            })

            log_fn = logger.critical if rule.level == AlertLevel.CRITICAL else logger.warning
            log_fn(
                f"ALERT_{rule.level.value.upper()}",
                rule=rule.name,
                current=round(current, 4),
                threshold=rule.threshold,
            )

    return triggered


# ================================================================
# 预定义指标函数（占位，随系统运行填充真实数据）
# ================================================================

# Agent 统计（内存计数）
_agent_stats = {"total": 0, "failed": 0}
_llm_stats = {"total": 0, "failed": 0}
_rag_stats = {"total": 0, "empty_results": 0}


def record_agent_result(success: bool) -> None:
    """记录 Agent 执行结果。"""
    _agent_stats["total"] += 1
    if not success:
        _agent_stats["failed"] += 1


def record_llm_result(success: bool) -> None:
    """记录 LLM 调用结果。"""
    _llm_stats["total"] += 1
    if not success:
        _llm_stats["failed"] += 1


def record_rag_result(has_results: bool) -> None:
    """记录 RAG 检索结果。"""
    _rag_stats["total"] += 1
    if not has_results:
        _rag_stats["empty_results"] += 1


def _get_agent_failure_rate() -> float:
    if _agent_stats["total"] == 0:
        return 0.0
    return _agent_stats["failed"] / _agent_stats["total"]


def _get_llm_failure_rate() -> float:
    if _llm_stats["total"] == 0:
        return 0.0
    return _llm_stats["failed"] / _llm_stats["total"]


def _get_rag_empty_rate() -> float:
    if _rag_stats["total"] == 0:
        return 0.0
    return _rag_stats["empty_results"] / _rag_stats["total"]


def _get_avg_latency() -> float:
    """获取全局平均延迟（需要 MetricsMiddleware 先记录数据）。"""
    from app.api.middleware.metrics import get_performance_stats
    stats = get_performance_stats()
    if not stats:
        return 0.0
    all_avg = [s["avg_ms"] for s in stats.values()]
    return sum(all_avg) / len(all_avg) / 1000 if all_avg else 0.0  # 转为秒


def _get_p95_latency() -> float:
    """获取全局 P95 延迟。"""
    from app.api.middleware.metrics import get_performance_stats
    stats = get_performance_stats()
    if not stats:
        return 0.0
    all_p95 = [s["p95_ms"] for s in stats.values()]
    return max(all_p95) / 1000 if all_p95 else 0.0


# ---- 注册默认告警规则 ----

register_alert_rule(AlertRule(
    name="agent_failure_rate",
    description="Agent 执行失败率超过 5%",
    level=AlertLevel.WARNING,
    threshold=0.05,
    metric_fn=_get_agent_failure_rate,
))

register_alert_rule(AlertRule(
    name="agent_failure_rate_critical",
    description="Agent 执行失败率超过 10%",
    level=AlertLevel.CRITICAL,
    threshold=0.10,
    metric_fn=_get_agent_failure_rate,
))

register_alert_rule(AlertRule(
    name="llm_failure_rate",
    description="LLM 调用失败率超过 3%",
    level=AlertLevel.WARNING,
    threshold=0.03,
    metric_fn=_get_llm_failure_rate,
))

register_alert_rule(AlertRule(
    name="rag_empty_rate",
    description="RAG 检索空结果率超过 20%",
    level=AlertLevel.WARNING,
    threshold=0.20,
    metric_fn=_get_rag_empty_rate,
))

register_alert_rule(AlertRule(
    name="p95_latency_warning",
    description="请求 P95 延迟超过 5s",
    level=AlertLevel.WARNING,
    threshold=5.0,
    metric_fn=_get_p95_latency,
))

register_alert_rule(AlertRule(
    name="p95_latency_critical",
    description="请求 P95 延迟超过 10s",
    level=AlertLevel.CRITICAL,
    threshold=10.0,
    metric_fn=_get_p95_latency,
))
