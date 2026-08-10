"""Memory 模块测试。"""

import pytest


def test_token_estimation():
    from app.memory.summary import estimate_tokens
    messages = [
        {"role": "user", "content": "你好" * 100},
        {"role": "assistant", "content": "回复" * 200},
    ]
    tokens = estimate_tokens(messages)
    assert tokens > 0  # 任何内容都应估算出正数
    # 中文约 1.5 字符/token
    expected = (200 + 400) / 1.5
    assert abs(tokens - expected) < 50


def test_summary_trigger_by_rounds():
    from app.memory.summary import SummaryService
    svc = SummaryService()
    messages = [{"role": "user", "content": "msg"}] * 20
    assert svc.should_summarize(messages) is True


def test_summary_trigger_by_tokens():
    from app.memory.summary import SummaryService
    svc = SummaryService()
    messages = [{"role": "user", "content": "长文本" * 3000}]
    assert svc.should_summarize(messages) is True


def test_summary_no_trigger_short():
    from app.memory.summary import SummaryService
    svc = SummaryService()
    messages = [{"role": "user", "content": "短消息"}] * 3
    assert svc.should_summarize(messages) is False


def test_split_messages_for_summary():
    from app.memory.summary import SummaryService
    svc = SummaryService()
    messages = [{"role": "user", "content": f"msg{i}"} for i in range(20)]

    to_summarize, keep_recent = svc.get_messages_to_summarize(messages)
    assert len(to_summarize) == 16  # 20 - 4
    assert len(keep_recent) == 4


def test_mock_summarize():
    from app.memory.summary import SummaryService
    svc = SummaryService()
    messages = [
        {"role": "user", "content": "设备故障"},
        {"role": "assistant", "content": "请检查电源"},
        {"role": "user", "content": "还是不行"},
    ]
    summary = svc._mock_summarize(messages)
    assert "设备故障" in summary
    assert "摘要" in summary


@pytest.mark.asyncio
async def test_memory_update_node_no_crash(sample_agent_state):
    from app.agent.nodes.memory_update import memory_update_node
    state = sample_agent_state
    state["messages"] = [{"role": "user", "content": "test"}]
    result = await memory_update_node(state)
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_context_load_no_crash(sample_agent_state):
    from app.agent.nodes.context_load import context_load_node
    result = await context_load_node(sample_agent_state)
    assert "device_info" in result
