"""Workflow 关键路径测试。"""

import pytest


@pytest.mark.asyncio
async def test_safety_high_risk_intercept(sample_agent_state):
    """测试高风险输入被拦截。"""
    from app.agent.nodes.safety_check import input_safety_check_node

    state = sample_agent_state
    state["query"] = "我应该吃什么药来治疗高血压"
    result = await input_safety_check_node(state)
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_query_router_rag_path(sample_agent_state):
    """测试 FAQ 意图路由到 RAG。"""
    from app.agent.nodes.query_router import query_router_node

    state = sample_agent_state
    state["intent"] = "faq_query"
    result = await query_router_node(state)
    assert result["route_type"] == "rag"


@pytest.mark.asyncio
async def test_query_router_tool_path(sample_agent_state):
    """测试保修意图路由到 Tool。"""
    from app.agent.nodes.query_router import query_router_node

    state = sample_agent_state
    state["intent"] = "warranty_query"
    result = await query_router_node(state)
    assert result["route_type"] == "tool"


@pytest.mark.asyncio
async def test_query_router_safe_reply_path(sample_agent_state):
    """测试医疗风险路由到 Safe Reply。"""
    from app.agent.nodes.query_router import query_router_node

    state = sample_agent_state
    state["intent"] = "medical_risk"
    result = await query_router_node(state)
    assert result["route_type"] == "safe_reply"
