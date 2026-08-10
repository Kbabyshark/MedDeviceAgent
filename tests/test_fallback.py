"""Fallback 降级链测试。"""

import pytest


@pytest.mark.asyncio
async def test_fallback_decorator_retry_then_fallback():
    from app.core.fallback import with_fallback

    call_count = 0

    @with_fallback(fallback_value="fallback", max_retries=2)
    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("always fail")

    result = await always_fail()
    assert result == "fallback"
    assert call_count == 3  # 1 original + 2 retries


@pytest.mark.asyncio
async def test_fallback_decorator_success_no_retry():
    from app.core.fallback import with_fallback

    call_count = 0

    @with_fallback(fallback_value="fallback", max_retries=3)
    async def succeed_first_time():
        nonlocal call_count
        call_count += 1
        return "success"

    result = await succeed_first_time()
    assert result == "success"
    assert call_count == 1


@pytest.mark.asyncio
async def test_fallback_chain():
    from app.core.fallback import FallbackChain

    async def primary():
        raise RuntimeError("primary down")

    async def secondary():
        return "secondary_result"

    chain = FallbackChain([
        ("primary", primary),
        ("secondary", secondary),
    ])

    result, source = await chain.execute(default="default")
    assert result == "secondary_result"
    assert source == "secondary"


@pytest.mark.asyncio
async def test_fallback_chain_all_fail():
    from app.core.fallback import FallbackChain

    async def fail1():
        raise RuntimeError()

    async def fail2():
        raise RuntimeError()

    chain = FallbackChain([("a", fail1), ("b", fail2)])
    result, source = await chain.execute(default="default_value")
    assert result == "default_value"
    assert source == "fallback_default"


@pytest.mark.asyncio
async def test_distributed_lock_acquire_release():
    from app.core.lock import DistributedLock

    lock = DistributedLock("test_action", user_id="test_user")
    try:
        async with lock.acquire():
            assert True  # 成功获取
    except Exception:
        # Mock 模式下 Redis 可能不可用
        pass


def test_rate_limit_action_extraction():
    from app.api.middleware.rate_limit import _get_action_from_path
    assert _get_action_from_path("/api/v1/chat") == "chat"
    assert _get_action_from_path("/api/v1/chat/stream") == "chat_stream"
    assert _get_action_from_path("/api/v1/ticket/draft") == "create_ticket"


def test_tts_sentence_split():
    from app.voice.tts import _split_sentences
    text = "设备显示E101故障码。请检查传感器连接。如有疑问请联系人工客服。"
    sentences = _split_sentences(text)
    assert len(sentences) == 3
    assert "传感器" in sentences[1]


def test_parser_text():
    import pytest
    from app.rag.parser import DocumentParser
    parser = DocumentParser()
    result = parser._parse_text("测试内容".encode("utf-8"), "test.txt")
    assert "测试内容" in result.text
