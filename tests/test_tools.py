"""Tool 调用模块测试。"""

import pytest


def test_tool_registry_has_all_tools():
    from app.agent.tools.registry import ToolRegistry, register_all_tools
    register_all_tools()
    tools = ToolRegistry.list_all()
    tool_names = [t.name for t in tools]
    assert "query_warranty" in tool_names
    assert "query_device_binding" in tool_names
    assert "create_ticket" in tool_names
    assert "transfer_human" in tool_names


def test_tool_registry_intent_mapping():
    from app.agent.tools.registry import ToolRegistry, register_all_tools
    register_all_tools()
    assert ToolRegistry.get_by_intent("warranty_query").name == "query_warranty"
    assert ToolRegistry.get_by_intent("device_binding").name == "query_device_binding"
    assert ToolRegistry.get_by_intent("create_ticket").name == "create_ticket"
    assert ToolRegistry.get_by_intent("transfer_human").name == "transfer_human"


def test_query_warranty_read_only():
    from app.agent.tools.query_warranty import query_warranty_tool
    assert query_warranty_tool.requires_confirmation is False


def test_create_ticket_requires_confirm():
    from app.agent.tools.create_ticket import create_ticket_tool
    assert create_ticket_tool.requires_confirmation is True


def test_transfer_human_requires_confirm():
    from app.agent.tools.transfer_human import transfer_human_tool
    assert transfer_human_tool.requires_confirmation is True


@pytest.mark.asyncio
async def test_tool_execute_read_only(sample_agent_state):
    from app.agent.nodes.tool_execute import tool_execute_node
    from app.agent.tools.registry import register_all_tools
    register_all_tools()

    state = sample_agent_state
    state["intent"] = "warranty_query"
    state["device_info"] = {"device_sn": "SN001"}
    result = await tool_execute_node(state)
    assert "保修" in result.get("response", "") or "valid" in result.get("response", "").lower()
    assert not result.get("pending_action")  # 查询类无 pending


@pytest.mark.asyncio
async def test_tool_execute_write_pending(sample_agent_state):
    from app.agent.nodes.tool_execute import tool_execute_node
    from app.agent.tools.registry import register_all_tools
    register_all_tools()

    state = sample_agent_state
    state["intent"] = "create_ticket"
    result = await tool_execute_node(state)
    assert result.get("pending_action", {}).get("status") == "waiting_confirm"


@pytest.mark.asyncio
async def test_tool_not_found_fallback(sample_agent_state):
    from app.agent.nodes.tool_execute import tool_execute_node
    state = sample_agent_state
    state["intent"] = "unknown_intent"
    result = await tool_execute_node(state)
    assert "暂不支持" in result.get("response", "")
