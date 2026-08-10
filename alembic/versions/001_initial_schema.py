"""Initial schema — 创建全部 16 张业务表

Revision ID: 001
Revises: None
Create Date: 2026-07-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- user 用户表 ----
    op.create_table(
        "user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False, comment="用户名"),
        sa.Column("phone", sa.String(20), unique=True, comment="手机号"),
        sa.Column("email", sa.String(128), unique=True, comment="邮箱"),
        sa.Column("password_hash", sa.String(256), nullable=False, comment="密码哈希"),
        sa.Column("role", sa.String(32), nullable=False, server_default="user", comment="角色"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1", comment="状态"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_user_role", "user", ["role"])
    op.create_index("idx_user_status", "user", ["status"])

    # ---- device 设备表 ----
    op.create_table(
        "device",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_sn", sa.String(64), unique=True, nullable=False, comment="设备序列号"),
        sa.Column("device_type", sa.String(64), nullable=False, comment="设备型号"),
        sa.Column("version", sa.String(32), comment="软件版本"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="所属用户"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active", comment="设备状态"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_device_type", "device", ["device_type"])
    op.create_index("idx_device_user_id", "device", ["user_id"])
    op.create_index("idx_device_user_type", "device", ["user_id", "device_type"])

    # ---- warranty_record 保修表 ----
    op.create_table(
        "warranty_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("device_sn", sa.String(64), nullable=False, comment="设备SN"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="所属用户"),
        sa.Column("start_date", sa.Date(), comment="开始时间"),
        sa.Column("end_date", sa.Date(), comment="结束时间"),
        sa.Column("status", sa.String(32), comment="状态"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_warranty_device_sn", "warranty_record", ["device_sn"])
    op.create_index("idx_warranty_user_id", "warranty_record", ["user_id"])
    op.create_index("idx_warranty_ds_status", "warranty_record", ["device_sn", "status"])

    # ---- repair_ticket 工单表 ----
    op.create_table(
        "repair_ticket",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户"),
        sa.Column("device_sn", sa.String(64), nullable=False, comment="设备SN"),
        sa.Column("fault_desc", sa.Text(), nullable=False, comment="故障描述"),
        sa.Column("fault_category", sa.String(64), comment="故障分类"),
        sa.Column("priority", sa.String(16), nullable=False, server_default="medium", comment="优先级"),
        sa.Column("contact_name", sa.String(64), comment="联系人"),
        sa.Column("contact_phone", sa.String(20), comment="联系电话"),
        sa.Column("assigned_to", sa.BigInteger(), comment="分配客服"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft", comment="状态"),
        sa.Column("created_by", sa.String(32), nullable=False, server_default="agent", comment="创建来源"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ticket_user_id", "repair_ticket", ["user_id"])
    op.create_index("idx_ticket_device_sn", "repair_ticket", ["device_sn"])
    op.create_index("idx_ticket_fault_category", "repair_ticket", ["fault_category"])
    op.create_index("idx_ticket_assigned_to", "repair_ticket", ["assigned_to"])
    op.create_index("idx_ticket_status", "repair_ticket", ["status"])
    op.create_index("idx_ticket_user_status", "repair_ticket", ["user_id", "status"])
    op.create_index("idx_ticket_status_created", "repair_ticket", ["status", "created_at"])

    # ---- conversation 会话表 ----
    op.create_table(
        "conversation",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户"),
        sa.Column("session_id", sa.String(64), unique=True, nullable=False, comment="Agent Session"),
        sa.Column("title", sa.String(256), comment="标题"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active", comment="状态"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_conv_user_id", "conversation", ["user_id"])
    op.create_index("idx_conv_status", "conversation", ["status"])

    # ---- conversation_message 消息表 ----
    op.create_table(
        "conversation_message",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False, comment="会话"),
        sa.Column("role", sa.String(16), nullable=False, comment="角色"),
        sa.Column("content", sa.Text(), nullable=False, comment="内容"),
        sa.Column("token_usage", sa.Integer(), comment="Token数量"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_msg_session_id", "conversation_message", ["session_id"])
    op.create_index("idx_msg_session_created", "conversation_message", ["session_id", "created_at"])

    # ---- conversation_summary 摘要表 ----
    op.create_table(
        "conversation_summary",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户"),
        sa.Column("session_id", sa.String(64), nullable=False, comment="会话"),
        sa.Column("summary", sa.Text(), nullable=False, comment="摘要"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1", comment="版本"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_cs_user_id", "conversation_summary", ["user_id"])
    op.create_index("idx_cs_session_id", "conversation_summary", ["session_id"])
    op.create_index("idx_cs_user_session", "conversation_summary", ["user_id", "session_id"])

    # ---- user_memory 长期记忆表 ----
    op.create_table(
        "user_memory",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户"),
        sa.Column("memory_type", sa.String(32), nullable=False, comment="类型"),
        sa.Column("content", sa.Text(), nullable=False, comment="内容"),
        sa.Column("status", sa.Integer(), nullable=False, server_default="1", comment="状态"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_um_user_id", "user_memory", ["user_id"])
    op.create_index("idx_um_user_type_status", "user_memory", ["user_id", "memory_type", "status"])

    # ---- knowledge_document 知识库文档表 ----
    op.create_table(
        "knowledge_document",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(256), nullable=False, comment="文档名称"),
        sa.Column("device_type", sa.String(64), nullable=False, comment="设备类型"),
        sa.Column("doc_type", sa.String(32), nullable=False, comment="文档类型"),
        sa.Column("version", sa.String(32), nullable=False, comment="版本"),
        sa.Column("permission", sa.String(32), nullable=False, server_default="public", comment="权限"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kd_device_type", "knowledge_document", ["device_type"])
    op.create_index("idx_kd_doc_type", "knowledge_document", ["doc_type"])
    op.create_index("idx_kd_device_doc_version", "knowledge_document", ["device_type", "doc_type", "version"])

    # ---- knowledge_chunk Chunk表 ----
    op.create_table(
        "knowledge_chunk",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False, comment="所属文档"),
        sa.Column("content", sa.Text(), nullable=False, comment="文本内容"),
        sa.Column("chunk_index", sa.Integer(), nullable=False, comment="分块序号"),
        sa.Column("metadata", sa.JSON(), nullable=False, comment="元数据"),
        sa.Column("vector_id", sa.String(64), unique=True, nullable=False, comment="Qdrant向量ID"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_kc_document_id", "knowledge_chunk", ["document_id"])

    # ---- agent_trace 链路追踪表 ----
    op.create_table(
        "agent_trace",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(64), unique=True, nullable=False, comment="Trace ID"),
        sa.Column("session_id", sa.String(64), nullable=False, comment="会话"),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户"),
        sa.Column("start_time", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True)),
        sa.Column("total_latency", sa.Float(), comment="总耗时(ms)"),
        sa.Column("status", sa.String(32), nullable=False, server_default="running", comment="状态"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_trace_session_id", "agent_trace", ["session_id"])
    op.create_index("idx_trace_user_id", "agent_trace", ["user_id"])
    op.create_index("idx_trace_user_start", "agent_trace", ["user_id", "start_time"])

    # ---- agent_trace_node 节点执行记录 ----
    op.create_table(
        "agent_trace_node",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False, comment="链路ID"),
        sa.Column("node_name", sa.String(64), nullable=False, comment="节点名称"),
        sa.Column("input", sa.JSON(), comment="输入"),
        sa.Column("output", sa.JSON(), comment="输出"),
        sa.Column("latency", sa.Float(), comment="耗时(ms)"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tn_trace_id", "agent_trace_node", ["trace_id"])
    op.create_index("idx_tn_trace_node", "agent_trace_node", ["trace_id", "node_name"])

    # ---- llm_call_record LLM调用记录 ----
    op.create_table(
        "llm_call_record",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("trace_id", sa.String(64), nullable=False, comment="链路ID"),
        sa.Column("task_type", sa.String(32), nullable=False, comment="任务类型"),
        sa.Column("model_name", sa.String(64), nullable=False, comment="模型名称"),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency", sa.Float(), comment="耗时(ms)"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_llm_trace_id", "llm_call_record", ["trace_id"])
    op.create_index("idx_llm_task_model", "llm_call_record", ["task_type", "model_name"])
    op.create_index("idx_llm_created", "llm_call_record", ["created_at"])

    # ---- role 角色定义表 ----
    op.create_table(
        "role",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(32), unique=True, nullable=False, comment="角色名"),
        sa.Column("description", sa.String(256), comment="描述"),
        sa.Column("permissions", sa.JSON(), comment="权限列表"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ---- user_role 用户-角色关联 ----
    op.create_table(
        "user_role",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False, comment="用户"),
        sa.Column("role_id", sa.BigInteger(), nullable=False, comment="角色"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", name="uk_user_role"),
    )
    op.create_index("idx_ur_user_id", "user_role", ["user_id"])
    op.create_index("idx_ur_role_id", "user_role", ["role_id"])

    # ---- knowledge_permission 知识库权限 ----
    op.create_table(
        "knowledge_permission",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), nullable=False, comment="文档ID"),
        sa.Column("role_id", sa.BigInteger(), nullable=False, comment="角色ID"),
        sa.Column("permission", sa.String(16), nullable=False, server_default="read", comment="权限"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "role_id", name="uk_doc_role"),
    )
    op.create_index("idx_kp_document_id", "knowledge_permission", ["document_id"])
    op.create_index("idx_kp_role_id", "knowledge_permission", ["role_id"])


def downgrade() -> None:
    """回滚：删除所有表。"""
    op.drop_table("knowledge_permission")
    op.drop_table("user_role")
    op.drop_table("role")
    op.drop_table("llm_call_record")
    op.drop_table("agent_trace_node")
    op.drop_table("agent_trace")
    op.drop_table("knowledge_chunk")
    op.drop_table("knowledge_document")
    op.drop_table("user_memory")
    op.drop_table("conversation_summary")
    op.drop_table("conversation_message")
    op.drop_table("conversation")
    op.drop_table("repair_ticket")
    op.drop_table("warranty_record")
    op.drop_table("device")
    op.drop_table("user")
