"""
LLM 客户端封装 — DeepSeek API。

支持：
- DeepSeek-V3（chat）：轻量任务
- DeepSeek-R1（reasoner）：复杂推理任务
- Token 级流式输出（async generator）
- Mock 模式：离线开发时返回模拟响应
- 统一的重试 + 超时机制
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Literal

import httpx

from app.core.config import get_settings
from app.core.logger import get_logger

try:
    from langsmith import traceable
except ImportError:
    def traceable(*args, **kwargs):
        return lambda f: f

logger = get_logger(__name__)


class ModelType(str, Enum):
    V3 = "deepseek-v3"
    R1 = "deepseek-r1"


@dataclass
class LLMCallResult:
    content: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    finish_reason: str = "stop"


@dataclass
class LLMClient:
    """DeepSeek API 客户端。"""

    mock_mode: bool = False
    _http: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    def _get_http(self) -> httpx.AsyncClient:
        if self._http is None:
            settings = get_settings()
            self._http = httpx.AsyncClient(
                base_url=settings.deepseek.base_url,
                headers={
                    "Authorization": f"Bearer {settings.deepseek.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(30.0, connect=5.0),
            )
        return self._http

    def _get_model_name(self, model: ModelType) -> str:
        settings = get_settings()
        return settings.deepseek.r1_model if model == ModelType.R1 else settings.deepseek.v3_model

    @traceable(run_type="llm", name="DeepSeek-Chat")
    async def chat(
        self,
        prompt: str,
        system: str = "",
        model: ModelType = ModelType.V3,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        response_format: Literal["text", "json_object"] = "text",
        task_type: str = "",
    ) -> LLMCallResult:
        """发送 Chat Completion 请求（非流式）。"""
        import time as _time
        t0 = _time.monotonic()
        error_str: str | None = None

        if self.mock_mode:
            result = await self._mock_chat(prompt, model)
            _record_llm_call(task_type, result, _time.monotonic() - t0)
            return result

        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})

        # DeepSeek/OpenAI 要求 json_object 模式时 prompt 中必须包含 "json" 关键词，
        # 否则返回 400。此处自动检测并降级，避免硬报错。
        use_json_mode = response_format == "json_object"
        if use_json_mode:
            combined = system + " " + prompt
            if "json" not in combined.lower():
                logger.warning(
                    "llm_json_mode_skip",
                    hint="prompt 中缺少 'json' 关键词，已自动降级为 text 模式，建议在提示词中添加 'JSON'",
                )
                use_json_mode = False

        body: dict[str, Any] = {
            "model": self._get_model_name(model),
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if use_json_mode:
            body["response_format"] = {"type": "json_object"}

        for attempt in range(3):
            try:
                response = await self._get_http().post("/chat/completions", json=body)
                response.raise_for_status()
                data = response.json()
                choice = data["choices"][0]
                usage = data.get("usage", {})
                result = LLMCallResult(
                    content=choice["message"]["content"],
                    model=data.get("model", self._get_model_name(model)),
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    finish_reason=choice.get("finish_reason", "stop"),
                )
                _record_llm_call(task_type or "", result, _time.monotonic() - t0)
                return result
            except httpx.HTTPStatusError as e:
                # 400 + json_mode → 降级重试
                if e.response.status_code == 400 and body.get("response_format", {}).get("type") == "json_object":
                    logger.warning("llm_json_mode_400_fallback", attempt=attempt + 1)
                    body.pop("response_format", None)
                    continue
                logger.warning("llm_http_error", attempt=attempt + 1, status=e.response.status_code)
                error_str = str(e)
                if attempt == 2:
                    _record_llm_call(task_type or "", None, _time.monotonic() - t0, error=error_str)
                    raise
                await asyncio.sleep(1 * (attempt + 1))
            except httpx.RequestError as e:
                logger.warning("llm_request_error", attempt=attempt + 1, error=str(e))
                if attempt == 2:
                    raise
                await asyncio.sleep(1 * (attempt + 1))

        raise RuntimeError("LLM request failed after 3 attempts")

    async def chat_stream(
        self,
        prompt: str,
        system: str = "",
        model: ModelType = ModelType.V3,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        task_type: str = "",
    ) -> AsyncIterator[str]:
        """Token 级流式输出。

        Yields:
            每个 yield 是一个文本片段（可能包含多个 token）。
        """
        import time as _time
        t0 = _time.monotonic()
        model_name = self._get_model_name(model)

        if self.mock_mode:
            for word in self._mock_stream(prompt):
                yield word
            _record_llm_call(task_type, LLMCallResult(content="", model=model_name), _time.monotonic() - t0)
            return

        messages = [{"role": "system", "content": system}] if system else []
        messages.append({"role": "user", "content": prompt})

        body: dict[str, Any] = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        total_content = ""
        try:
            async with self._get_http().stream("POST", "/chat/completions", json=body) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line.removeprefix("data: ")
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                total_content += content
                                yield content
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
            _record_llm_call(task_type, LLMCallResult(content=total_content, model=model_name),
                           _time.monotonic() - t0)
        except Exception as e:
            logger.error("llm_stream_error", error=str(e))
            _record_llm_call(task_type, None, _time.monotonic() - t0, error=str(e))
            yield f"\n[流式输出中断: {e}]"

    async def chat_structured(
        self,
        prompt: str,
        system: str = "",
        model: ModelType = ModelType.V3,
        temperature: float = 0.1,
        max_tokens: int = 2048,
    ) -> dict:
        """JSON 结构化输出。所有异常都 catch，不阻塞流程。"""
        try:
            result = await self.chat(
                prompt=prompt, system=system, model=model,
                temperature=temperature, max_tokens=max_tokens,
                response_format="json_object",
            )
            raw = result.content.strip()
            for attempt in range(3):
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    raw = raw.lstrip("`").rstrip("`").strip()
                    if raw.startswith("json"):
                        raw = raw[4:].strip()
            logger.warning("llm_json_parse_failed", content=raw[:200])
            return {"raw": raw}
        except Exception as e:
            logger.warning("chat_structured_failed", error=str(e)[:200])
            # 重建 HTTP 客户端，防止连接池脏连接
            try: await self._http.aclose()
            except Exception: pass
            self._http = None
            return {}

    def _mock_stream(self, prompt: str) -> AsyncIterator[str]:
        """Mock 流式：逐词输出模拟文本。"""
        words = f"[Mock 流式输出] 基于您的查询，正在检索知识库并生成回答... (查询: {prompt[:50]}...)".split()
        for word in words:
            yield word + " "

    async def _mock_chat(self, prompt: str, model: ModelType) -> LLMCallResult:
        mock_content = json.dumps({
            "mock": True,
            "model": self._get_model_name(model),
            "note": "Mock mode — 未连接 DeepSeek API",
        }, ensure_ascii=False)
        return LLMCallResult(
            content=mock_content,
            model=f"{self._get_model_name(model)}[mock]",
            prompt_tokens=len(prompt) // 2,
            completion_tokens=len(mock_content) // 2,
            total_tokens=(len(prompt) + len(mock_content)) // 2,
        )

    async def close(self) -> None:
        if self._http:
            await self._http.aclose()
            self._http = None


_default_client: LLMClient | None = None


def _record_llm_call(task_type: str, result: LLMCallResult | None,
                     latency_s: float, error: str | None = None) -> None:
    """自动记录 LLM 调用到当前 Trace。"""
    from app.core.tracer import _current_trace
    tracer = _current_trace.get()
    if tracer is None:
        return
    tracer.llm_call(
        task_type=task_type,
        model_name=result.model if result else "unknown",
        prompt_tokens=result.prompt_tokens if result else 0,
        completion_tokens=result.completion_tokens if result else 0,
        total_tokens=result.total_tokens if result else 0,
        latency=latency_s * 1000,
        error=error,
    )


def get_llm_client(mock_mode: bool | None = None) -> LLMClient:
    global _default_client
    if _default_client is None:
        settings = get_settings()
        # 有 API Key 就走真实调用，没 Key 才 Mock
        use_mock = mock_mode if mock_mode is not None else (not settings.deepseek.api_key or "changeme" in settings.deepseek.api_key.lower())
        _default_client = LLMClient(mock_mode=use_mock)
    return _default_client
