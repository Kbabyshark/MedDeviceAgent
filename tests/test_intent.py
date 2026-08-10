"""意图识别测试。"""

import pytest

from app.agent.nodes.intent_classify import intent_classify_node


@pytest.mark.asyncio
async def test_intent_fault_code(sample_agent_state):
    """测试故障码意图识别。"""
    state = sample_agent_state
    state["query"] = "设备显示E101故障码"
    result = await intent_classify_node(state)
    assert result["intent"] == "fault_code_query"


@pytest.mark.asyncio
async def test_intent_warranty(sample_agent_state):
    """测试保修查询意图识别。"""
    state = sample_agent_state
    state["query"] = "我的设备还在保修期内吗？"
    result = await intent_classify_node(state)
    assert result["intent"] == "warranty_query"


@pytest.mark.asyncio
async def test_intent_transfer_human(sample_agent_state):
    """测试转人工意图识别。"""
    state = sample_agent_state
    state["query"] = "我要转人工客服"
    result = await intent_classify_node(state)
    assert result["intent"] == "transfer_human"


@pytest.mark.asyncio
async def test_intent_medical_risk(sample_agent_state):
    """测试医疗风险意图拦截。"""
    state = sample_agent_state
    state["query"] = "我最近总是头晕，是不是得了什么病"
    result = await intent_classify_node(state)
    assert result["intent"] == "medical_risk"
