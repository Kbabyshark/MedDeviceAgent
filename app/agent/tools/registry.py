"""
Tool Registry — 统一管理所有 Agent 工具。

所有业务能力必须通过 Registry 注册，禁止 LLM 直接调用数据库或业务接口。
"""

from __future__ import annotations
from typing import Any, Protocol


class Tool(Protocol):
    """Tool 接口协议。"""
    name: str
    description: str
    requires_confirmation: bool
    input_schema: dict

    async def execute(self, **params: Any) -> dict: ...


class ToolRegistry:
    """工具注册中心（类级别单例）。"""

    _tools: dict[str, Any] = {}
    _intent_to_tool: dict[str, str] = {}

    @classmethod
    def register(cls, tool: Any, intents: list[str] | None = None) -> None:
        """注册一个 Tool 及其对应的 Intent。"""
        cls._tools[tool.name] = tool
        if intents:
            for intent in intents:
                cls._intent_to_tool[intent] = tool.name

    @classmethod
    def get(cls, name: str) -> Any | None:
        """按名称获取 Tool。"""
        return cls._tools.get(name)

    @classmethod
    def get_by_intent(cls, intent: str) -> Any | None:
        """按 Intent 获取 Tool。"""
        tool_name = cls._intent_to_tool.get(intent)
        if tool_name:
            return cls._tools.get(tool_name)
        return None

    @classmethod
    def list_all(cls) -> list:
        """列出所有已注册的 Tool。"""
        return list(cls._tools.values())


def register_all_tools() -> None:
    """注册所有业务工具（在 app startup 时调用）。"""
    from app.agent.tools.query_warranty import query_warranty_tool
    from app.agent.tools.query_device_binding import query_device_binding_tool
    from app.agent.tools.create_ticket import create_ticket_tool
    from app.agent.tools.transfer_human import transfer_human_tool
    from app.agent.tools.create_warranty import create_warranty_tool

    ToolRegistry.register(query_warranty_tool, intents=["warranty_query"])
    ToolRegistry.register(query_device_binding_tool, intents=["device_binding"])
    ToolRegistry.register(create_ticket_tool, intents=["create_ticket"])
    ToolRegistry.register(transfer_human_tool, intents=["transfer_human"])
    ToolRegistry.register(create_warranty_tool, intents=["create_warranty"])
