"""
统一 Fallback / 降级策略。

每个组件失败时有明确降级路径，避免级联故障。
"""

from __future__ import annotations

import asyncio
import functools
from typing import Any, Callable, TypeVar

from app.core.logger import get_logger

logger = get_logger(__name__)

F = TypeVar("F", bound=Callable[..., Any])

# 默认配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 1.0   # 秒
DEFAULT_MAX_DELAY = 10.0   # 秒


def with_fallback(
    fallback_value: Any = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    base_delay: float = DEFAULT_BASE_DELAY,
    reraise: type[Exception] | tuple[type[Exception], ...] | None = None,
    on_failure: str = "warn",  # "warn" | "error" | "silent"
) -> Callable[[F], F]:
    """异步函数装饰器：自动重试 + 降级兜底。

    Usage:
        @with_fallback(fallback_value=[], max_retries=2)
        async def search_qdrant(query): ...

    Args:
        fallback_value: 最终降级返回值
        max_retries: 最大重试次数
        base_delay: 退避基础延迟（等比增长）
        reraise: 即便失败也抛出这些异常（不降级）
        on_failure: 失败日志级别
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    if reraise and isinstance(e, reraise):
                        raise

                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), DEFAULT_MAX_DELAY)
                        log_fn = getattr(logger, on_failure)
                        log_fn(
                            "fallback_retry",
                            func=func.__name__,
                            attempt=attempt + 1,
                            max_retries=max_retries,
                            delay=delay,
                            error=str(e)[:100],
                        )
                        await asyncio.sleep(delay)
                    else:
                        log_fn = getattr(logger, on_failure)
                        log_fn(
                            "fallback_exhausted",
                            func=func.__name__,
                            attempts=max_retries + 1,
                            error=str(last_error)[:100],
                        )

            return fallback_value

        return wrapper  # type: ignore[return-value]
    return decorator


class FallbackChain:
    """降级链：按优先级依次尝试，全部失败返回默认值。

    Usage:
        result = await FallbackChain([
            ("primary", primary_func),
            ("secondary", secondary_func),
        ]).execute(default="fallback_value")
    """

    def __init__(self, steps: list[tuple[str, Callable]]) -> None:
        self._steps = steps

    async def execute(self, default: Any = None) -> tuple[Any, str]:
        """依次执行，返回 (result, source)。"""
        for name, func in self._steps:
            try:
                result = await func()
                logger.debug("fallback_chain_hit", source=name)
                return result, name
            except Exception as e:
                logger.warning("fallback_chain_step_failed", step=name, error=str(e)[:100])
                continue

        logger.warning("fallback_chain_exhausted", steps=[s[0] for s in self._steps])
        return default, "fallback_default"


# ================================================================
# 具体降级策略
# ================================================================


class LLMFallback:
    """LLM 调用降级策略。

    R1 失败 → V3 重试 → Mock/规则兜底。
    """

    @staticmethod
    async def r1_to_v3_fallback(
        prompt: str,
        system: str = "",
        fallback_response: str = "",
    ) -> str:
        """R1 调用失败降级到 V3。"""
        from app.core.llm import LLMClient, ModelType, get_llm_client
        llm = get_llm_client()

        # Try R1
        try:
            result = await llm.chat(prompt=prompt, system=system, model=ModelType.R1)
            return result.content
        except Exception as e:
            logger.warning("llm_r1_failed_fallback_v3", error=str(e)[:100])

        # Fallback to V3
        try:
            result = await llm.chat(prompt=prompt, system=system, model=ModelType.V3)
            return result.content
        except Exception as e:
            logger.error("llm_both_failed", error=str(e)[:100])
            return fallback_response


class RAGFallback:
    """RAG 检索降级策略。

    无结果 → Query Rewrite → 重试 → 提示转人工。
    """

    @staticmethod
    async def no_result_fallback(
        query: str,
        device_info: dict,
        trace_id: str,
    ) -> tuple[list[dict], str]:
        """RAG 检索无结果时的降级链。

        Returns:
            (retrieved_docs, strategy): 文档列表 + 使用的策略名
        """
        from app.rag.retriever import RagRetriever
        retriever = RagRetriever()

        device_type = device_info.get("device_type", "")

        # Step 1: 严格过滤检索（原始 query）
        docs = await retriever.retrieve(query=query, device_type=device_type, top_k=20)
        if docs and docs[0].get("score", 0) > 0.5:
            return docs, "strict_match"

        # Step 2: 放宽 device_type 过滤
        logger.info("rag_fallback_relax_filter", trace_id=trace_id)
        docs = await retriever.retrieve(query=query, device_type="", top_k=20)
        if docs and docs[0].get("score", 0) > 0.3:
            return docs, "relaxed_filter"

        # Step 3: Query Rewrite 重试
        logger.info("rag_fallback_rewrite", trace_id=trace_id)
        try:
            from app.core.llm import ModelType, get_llm_client
            llm = get_llm_client()
            rewritten = await llm.chat(
                prompt=f"请将以下简短查询改写为更通用的检索语句：{query}",
                system="你是搜索优化器。输出改写后的查询。",
                model=ModelType.V3,
                max_tokens=100,
            )
            docs = await retriever.retrieve(query=rewritten.content, device_type="", top_k=20)
            if docs:
                return docs, "rewritten"
        except Exception as e:
            logger.error("rag_rewrite_fallback_failed", error=str(e)[:100])

        # Step 4: 完全无结果
        return [], "no_results"
