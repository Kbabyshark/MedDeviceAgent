"""
FastAPI 应用入口。

启动方式：
    uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

P1 状态：可无外部依赖启动，Mock 模式运行。
"""

from __future__ import annotations

# ================================================================
# 必须在所有 app import 之前执行：压制第三方库的 console 噪音
# ================================================================
import os as _os
_os.environ.setdefault("TQDM_DISABLE", "1")
_os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
_os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import logging as _logging
for _lib in (
    "sentence_transformers", "transformers", "transformers.modeling_utils",
    "httpx", "httpcore", "urllib3", "aiohttp", "asyncio",
    "uvicorn", "uvicorn.access", "uvicorn.error", "fastapi",
    "sqlalchemy", "sqlalchemy.engine",
    "qdrant_client", "pymysql",
):
    _lg = _logging.getLogger(_lib)
    _lg.setLevel(_logging.WARNING)
    _lg.handlers.clear()
    _lg.propagate = False

# 清理命名空间，避免污染模块
del _os, _lib, _lg, _logging
# ================================================================

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid4

# LangSmith 需要从 os.environ 读取，显式加载 .env
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import SmartVoiceException
from app.core.logger import get_logger, setup_logging

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。

    启动时：
    - 初始化日志系统
    - 校验配置完整性
    - 注册 Agent Tools
    - 不连接任何外部服务

    关闭时：
    - 关闭 LLM HTTP 客户端
    - 关闭 Redis 连接池
    """
    # ====== startup ======
    setup_logging()

    settings = get_settings()

    # 配置完整性校验
    _validate_config(settings)

    # 注册所有 Agent Tools
    from app.agent.tools.registry import register_all_tools
    register_all_tools()

    # 首次启动初始化默认管理员账号
    from app.api.routers.auth import _ensure_default_admin
    await _ensure_default_admin()

    # 后台预加载 Embedding 模型
    import threading
    def _preload_embedding():
        import asyncio
        from app.rag.embedding import EmbeddingService
        emb = EmbeddingService()
        asyncio.run(emb.embed("warmup"))
        logger.info("embedding_preloaded", dim=emb.dim)
    threading.Thread(target=_preload_embedding, daemon=True).start()

    # 启动 MinerU API 常驻服务（pipeline 后端，GPU 复用）
    import subprocess, sys, os, socket, time as _time
    logger.info("mineru_api_starting")
    venv_scripts = os.path.dirname(sys.executable)
    _mineru_bin = os.path.join(venv_scripts, "mineru-api.exe")
    if not os.path.exists(_mineru_bin):
        _mineru_bin = "mineru-api"
    _mineru_proc = subprocess.Popen(
        [_mineru_bin, "--port", "5566"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    # 后台线程读 stderr，只打印真正的错误
    def _read_stderr():
        for line in _mineru_proc.stderr:
            s = line.strip()
            if s and ("error" in s.lower() or "traceback" in s.lower() or "exception" in s.lower()):
                logger.error("mineru_api_stderr", msg=s)
    threading.Thread(target=_read_stderr, daemon=True).start()
    # 等端口就绪
    _ready = False
    _dl = _time.monotonic() + 30
    while _time.monotonic() < _dl:
        if _mineru_proc.poll() is not None:
            logger.error("mineru_api_died", rc=_mineru_proc.returncode)
            break
        try:
            s = socket.create_connection(("127.0.0.1", 5566), timeout=1); s.close()
            _ready = True; break
        except Exception:
            _time.sleep(1)
    if _ready:
        logger.info("mineru_api_ready")
    else:
        logger.warning("mineru_api_not_ready")

    yield

    # ====== shutdown ======
    _mineru_proc.terminate(); _mineru_proc.wait(timeout=5)
    logger.info("mineru_api_stopped")

    from app.core.llm import _default_client
    if _default_client:
        await _default_client.close()

    from app.core.redis import close_redis
    await close_redis()

    logger.info("app_stopped")


def _validate_config(settings) -> None:
    """校验必填配置项是否存在。

    缺失关键配置项时直接报错，避免静默失败。
    """
    critical = {
        "DEEPSEEK_API_KEY": settings.deepseek.api_key,
        "JWT_SECRET_KEY": settings.jwt.secret_key,
    }
    missing = [k for k, v in critical.items() if not v or "changeme" in v.lower()]
    if missing:
        logger.warning("config_missing_critical", keys=missing)
        # 非生产环境仅警告，不阻止启动
        if settings.is_production:
            raise RuntimeError(f"生产环境缺少关键配置: {', '.join(missing)}")


# ---- App ----
settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_debug else None,
    redoc_url="/api/redoc" if settings.app_debug else None,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate Limit（Redis 滑动窗口限流）
from app.api.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# Timeout Guard（请求超时保护）
from app.api.middleware.timeout import TimeoutMiddleware
app.add_middleware(TimeoutMiddleware)

# Metrics（延迟追踪 + P95 统计）
from app.api.middleware.metrics import MetricsMiddleware
app.add_middleware(MetricsMiddleware)


# ---- Trace ID 中间件 ----
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    """为每个请求注入 trace_id。"""
    trace_id = request.headers.get("X-Trace-ID", str(uuid4()))
    request.state.trace_id = trace_id
    request.state.start_time = datetime.now(timezone.utc)

    response = await call_next(request)

    response.headers["X-Trace-ID"] = trace_id
    return response


# ---- 全局异常处理 ----
@app.exception_handler(SmartVoiceException)
async def smart_voice_exception_handler(request: Request, exc: SmartVoiceException):
    """统一业务异常处理。"""
    logger.warning(
        "business_exception",
        code=exc.code,
        message=exc.message,
        trace_id=getattr(request.state, "trace_id", ""),
    )
    return JSONResponse(
        status_code=400 if exc.code < 50000 else 500,
        content={"code": exc.code, "message": exc.message, "data": None},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """兜底异常处理。"""
    logger.error(
        "unhandled_exception",
        error=str(exc),
        trace_id=getattr(request.state, "trace_id", ""),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"code": 50001, "message": "内部错误", "data": None},
    )


# ---- 健康检查 + 状态 ----
@app.get("/api/v1/health")
async def health_check():
    """系统健康检查（不依赖外部服务）。"""
    from app.core.database import check_database_health
    from app.core.redis import check_redis_health
    from app.core.qdrant import check_qdrant_health

    db_status = await check_database_health()
    redis_status = await check_redis_health()
    qdrant_status = await check_qdrant_health()

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "mock_mode": settings.app_debug,
        "services": {
            "database": db_status,
            "redis": redis_status,
            "qdrant": qdrant_status,
            "llm": {
                "status": "configured",
                "provider": "DeepSeek",
                "models": [settings.deepseek.v3_model, settings.deepseek.r1_model],
                "mock_mode": settings.app_debug,
            },
        },
    }


@app.get("/api/v1/status")
async def system_status():
    """系统状态 + 性能指标 + 告警状态。"""
    from app.api.middleware.metrics import get_performance_stats
    from app.core.alert import check_all_alerts, get_alert_rules

    perf = get_performance_stats()
    alerts = await check_all_alerts()

    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "env": settings.app_env,
        "performance": perf,
        "alerts_triggered": alerts,
        "alert_rules": [
            {"name": r.name, "level": r.level.value, "threshold": r.threshold}
            for r in get_alert_rules()
        ],
    }


# ---- Router 注册（后续 Phase 逐步接入）----
from app.api.routers import chat, session, ticket
from app.api.routers.auth import router as auth_router
from app.api.routers.user import router as user_router
from app.api.routers.knowledge import router as knowledge_router, admin_router as knowledge_admin_router

app.include_router(auth_router, prefix="/api/v1")
app.include_router(user_router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(session.router, prefix="/api/v1")
app.include_router(ticket.router, prefix="/api/v1")
app.include_router(knowledge_router, prefix="/api/v1")
app.include_router(knowledge_admin_router, prefix="/api/v1/admin")

from app.api.routers.fault_code import router as fault_code_router
from app.api.routers.warranty import router as warranty_router
from app.api.routers.device import router as device_router
from app.api.routers.support import router as support_router
from app.api.routers.ws_chat import router as ws_chat_router
from app.api.routers.trace import router as trace_router
app.include_router(fault_code_router, prefix="/api/v1/admin")
app.include_router(warranty_router, prefix="/api/v1")
app.include_router(device_router, prefix="/api/v1")
app.include_router(support_router, prefix="/api/v1")
app.include_router(ws_chat_router, prefix="/api/v1")
app.include_router(trace_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
