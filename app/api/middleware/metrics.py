"""
请求延迟追踪中间件。

记录每个请求的耗时，便于性能分析和慢查询定位。
P95/P99 计算、慢请求告警。
"""

from __future__ import annotations

import time
from collections import deque

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logger import get_logger

logger = get_logger(__name__)

# 滑动窗口大小（最近 N 个请求）
_WINDOW_SIZE = 1000

# 慢请求阈值（ms）
SLOW_REQUEST_THRESHOLD_MS = 5000

# 各路径延迟统计（滑动窗口）
_path_latencies: dict[str, deque[float]] = {}


class MetricsMiddleware(BaseHTTPMiddleware):
    """请求延迟追踪中间件。

    记录每个请求的：
    - 路径
    - 耗时 (ms)
    - 超过 SLOW_REQUEST_THRESHOLD_MS 的标记为慢请求
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        t0 = time.monotonic()

        response = await call_next(request)

        latency_ms = (time.monotonic() - t0) * 1000

        # 记录延迟
        if path not in _path_latencies:
            _path_latencies[path] = deque(maxlen=_WINDOW_SIZE)
        _path_latencies[path].append(latency_ms)

        # 慢请求告警
        if latency_ms > SLOW_REQUEST_THRESHOLD_MS:
            logger.warning(
                "slow_request",
                path=path,
                latency_ms=round(latency_ms, 0),
                threshold=SLOW_REQUEST_THRESHOLD_MS,
                p95=_compute_p95(path),
                trace_id=getattr(request.state, "trace_id", ""),
            )

        response.headers["X-Response-Time-Ms"] = str(round(latency_ms, 1))
        return response


def _compute_p95(path: str) -> float:
    """计算某路径的 P95 延迟。"""
    latencies = _path_latencies.get(path)
    if not latencies:
        return 0.0
    sorted_lat = sorted(latencies)
    idx = int(len(sorted_lat) * 0.95)
    return sorted_lat[min(idx, len(sorted_lat) - 1)]


# ================================================================
# 统计查询（供管理 API 使用）
# ================================================================


def get_performance_stats() -> dict:
    """获取当前性能统计。"""
    stats = {}
    for path, latencies in _path_latencies.items():
        if not latencies:
            continue
        sorted_lat = sorted(latencies)
        n = len(sorted_lat)
        stats[path] = {
            "count": n,
            "avg_ms": round(sum(sorted_lat) / n, 1),
            "p50_ms": round(sorted_lat[int(n * 0.50)], 1) if n > 1 else round(sorted_lat[0], 1),
            "p95_ms": round(sorted_lat[int(n * 0.95)], 1) if n > 1 else round(sorted_lat[0], 1),
            "p99_ms": round(sorted_lat[int(n * 0.99)], 1) if n > 1 else round(sorted_lat[0], 1),
            "max_ms": round(sorted_lat[-1], 1),
            "min_ms": round(sorted_lat[0], 1),
            "slow_count": sum(1 for l in latencies if l > SLOW_REQUEST_THRESHOLD_MS),
        }
    return stats
