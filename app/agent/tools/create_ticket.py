"""create_ticket — 创建维修工单 Tool（高风险，需 Human Confirm）"""

from __future__ import annotations


class CreateTicketTool:
    """创建维修工单。高风险操作：必须经过 Human-in-the-loop 确认后才执行。"""

    def __init__(self) -> None:
        self.name = "create_ticket"
        self.description = "为用户创建维修工单草稿，等待用户确认后提交。"
        self.requires_confirmation = True
        self.input_schema = {
            "type": "object",
            "properties": {
                "device_sn": {"type": "string", "description": "设备序列号"},
                "fault_desc": {"type": "string", "description": "故障描述"},
                "contact_name": {"type": "string", "description": "联系人姓名"},
                "contact_phone": {"type": "string", "description": "联系电话"},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
            },
            "required": ["device_sn", "fault_desc"],
        }

    async def execute(self, user_id: str, device_sn: str, fault_desc: str,
                      contact_name: str = "", contact_phone: str = "",
                      priority: str = "medium") -> dict:
        return {
            "ticket_id": "draft_xxx",
            "status": "pending_confirm",
            "device_sn": device_sn,
            "priority": priority,
        }


create_ticket_tool = CreateTicketTool()
