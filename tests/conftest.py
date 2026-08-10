"""
测试夹具。提供共享的 mock 对象和测试数据。
"""

import pytest


@pytest.fixture
def sample_agent_state() -> dict:
    """示例 AgentState（用于节点单元测试）。"""
    return {
        "user_id": "10001",
        "session_id": "sess_test_001",
        "trace_id": "trace_test_001",
        "query": "设备显示E101是什么意思？",
        "intent": "",
        "intents": [],
        "route_type": "",
        "device_info": {"device_type": "Monitor-X1", "device_sn": "SN001"},
        "messages": [],
        "retrieved_docs": [],
        "tool_calls": [],
        "pending_action": {},
        "summary": "",
        "response": "",
        "citations": [],
        "risk_level": "none",
        "error": "",
    }


@pytest.fixture
def mock_deepseek_response() -> dict:
    """模拟 DeepSeek API 响应。"""
    return {
        "choices": [{"message": {"content": "E101表示传感器异常，请检查..."}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50},
    }
