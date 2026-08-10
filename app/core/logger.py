"""
结构化日志模块。

基于 structlog，所有日志自动携带 trace_id / session_id / user_id / node_name。
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.core.config import get_settings


def setup_logging() -> None:
    """配置全局日志（在 app startup 时调用一次）。"""
    import os
    settings = get_settings()

    # ---- 压制第三方库的 console 噪音 ----
    os.environ.setdefault("TQDM_DISABLE", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    for _lib in ("funasr", "modelscope", "sentence_transformers", "transformers",
                 "httpx", "httpcore", "urllib3", "aiohttp", "asyncio"):
        logging.getLogger(_lib).setLevel(logging.WARNING)

    timestamper = structlog.processors.TimeStamper(fmt="iso")

    if settings.log_format == "json":
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        timestamper,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors + [structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    class _AppFilter(logging.Filter):
        """只放行 app.* 和 __main__，其余全拦截。"""
        def filter(self, record):
            name = record.name
            return name.startswith("app.") or name.startswith("__main__")

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_AppFilter())
    handler.setFormatter(formatter)

    # 清空所有非 app logger 的 handler，强制走 root handler（受 AppFilter 管控）
    for _name in list(logging.root.manager.loggerDict):
        _lg = logging.getLogger(_name)
        if _lg.handlers:
            _lg.handlers.clear()
        _lg.propagate = True

    # root 默认 WARNING（三方库 INFO 全拦截），app 体系保持 INFO
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(getattr(logging, settings.log_level))
    logging.getLogger("__main__").setLevel(getattr(logging, settings.log_level))


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """获取结构化 logger 实例。"""
    return structlog.get_logger(name or __name__)
