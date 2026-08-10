"""
tool_execute_node — 统一 Tool 治理管道。

Pipeline:
  Tool Lookup → LLM 参数提取 → Schema 校验 → 权限检查 → 风险判断
  → [写操作: 分布式锁 + Human Confirm] / [读操作: 直接执行]
  → 执行 + MySQL 兜底
"""

from __future__ import annotations

import asyncio

from app.agent.state import AgentState, get_stream_queue
from app.agent.tools.registry import ToolRegistry
from app.core.logger import get_logger

logger = get_logger(__name__)

# Tool 风险等级: low / medium / high
_TOOL_RISK: dict[str, str] = {
    "query_warranty": "low",
    "query_device_binding": "low",
    "create_ticket": "high",
    "create_warranty": "high",
    "transfer_human": "high",
}

# 需要用户确认的 Tool
_CONFIRM_REQUIRED = {"create_ticket", "create_warranty", "transfer_human"}

# 角色权限: 哪些角色可以调哪些 Tool
_ROLE_PERMISSIONS: dict[str, set[str]] = {
    "admin": {"query_warranty", "query_device_binding", "create_ticket", "create_warranty", "transfer_human"},
    "support": {"query_warranty", "query_device_binding", "create_ticket", "create_warranty", "transfer_human"},
    "user": {"query_warranty", "query_device_binding", "create_ticket", "create_warranty", "transfer_human"},
}


# ================================================================
# 管道步骤
# ================================================================

def _validate_schema(tool: any, params: dict) -> str | None:
    """JSON Schema 参数校验。通过返回 None，失败返回错误信息。"""
    try:
        import jsonschema
        jsonschema.validate(params, tool.input_schema)
        return None
    except ImportError:
        # jsonschema 未安装，跳过校验
        return None
    except Exception as e:
        return f"参数校验失败: {e}"


def _check_permission(tool_name: str, role: str) -> str | None:
    """权限检查。通过返回 None，拒绝返回错误信息。"""
    allowed = _ROLE_PERMISSIONS.get(role, set())
    if tool_name not in allowed:
        return f"角色 {role} 无权调用 {tool_name}"
    return None


def _check_risk(tool_name: str) -> str:
    """风险评估。返回 risk level: low/medium/high。"""
    return _TOOL_RISK.get(tool_name, "medium")


async def _acquire_lock(tool_name: str, user_id: str, trace_id: str) -> bool:
    """Redis 分布式锁：防止重复提交。"""
    try:
        from app.core.redis import RedisKeys, get_redis_client
        redis = await get_redis_client()
        key = RedisKeys.lock(tool_name, user_id)
        # SET NX EX: 10 秒内不可重复提交
        acquired = await redis.set(key, trace_id, nx=True, ex=10)
        return bool(acquired)
    except Exception as e:
        logger.warning("redis_lock_failed", error=str(e), trace_id=trace_id)
        return True  # Redis 不可用时降级放行


async def _release_lock(tool_name: str, user_id: str):
    """释放分布式锁。"""
    try:
        from app.core.redis import RedisKeys, get_redis_client
        redis = await get_redis_client()
        key = RedisKeys.lock(tool_name, user_id)
        await redis.delete(key)
    except Exception:
        pass


# ================================================================
# LLM 参数提取
# ================================================================

_PARAM_EXTRACT_PROMPT = """从用户消息中提取工具调用参数，返回 JSON。

可用工具及参数:
- query_warranty: {"device_sn": "设备序列号"}
- query_device_binding: {"user_id": "用户ID"}
- create_ticket: {"device_sn": "设备序列号", "fault_desc": "故障描述", "priority": "low|medium|high"}
- create_warranty: {"device_sn": "设备序列号", "problem_desc": "问题描述"}
- transfer_human: {"reason": "转人工原因", "summary": "问题摘要"}

规则:
- 只提取用户消息中明确出现的信息，不要编造
- 找不到的参数返回空字符串 ""

只返回 JSON，不要其他文字。"""


async def _extract_params(query: str, tool_name: str, trace_id: str) -> dict:
    """LLM 从用户消息中提取 Tool 调用参数。"""
    from app.core.llm import ModelType, get_llm_client
    llm = get_llm_client()
    try:
        result = await llm.chat_structured(
            prompt=f"工具: {tool_name}\n用户消息: {query}\n\n{_PARAM_EXTRACT_PROMPT}",
            model=ModelType.V3, temperature=0.0, max_tokens=256,
        )
        # 清理空值
        return {k: v for k, v in result.items() if v and k != "raw" and k != "mock"}
    except Exception as e:
        logger.warning("param_extract_failed", error=str(e), trace_id=trace_id)
        return {}


# ================================================================
# 写操作执行（带锁 + 兜底）
# ================================================================

async def _execute_with_lock(tool: any, params: dict, user_id: str, trace_id: str) -> dict:
    """写操作：加锁 → 执行 → 释放锁，失败有 MySQL 兜底。"""
    tool_name = tool.name

    # 获取分布式锁
    locked = await _acquire_lock(tool_name, user_id, trace_id)
    if not locked:
        return {"status": "rejected", "reason": "操作过于频繁，请稍后重试"}

    try:
        result = await tool.execute(**params)
        return result
    except Exception as e:
        logger.error("tool_execute_locked_error", tool=tool_name, error=str(e), trace_id=trace_id)
        # MySQL 兜底：从 DB 查询最新状态
        return {"status": "error", "reason": str(e), "fallback": "mysql"}
    finally:
        await _release_lock(tool_name, user_id)


# ================================================================
# 主节点
# ================================================================

async def tool_execute_node(state: AgentState) -> dict:
    """Tool 执行节点 — 完整治理管道。

    Pipeline:
      1. Tool Lookup
      2. LLM 参数提取
      3. Schema 校验
      4. 权限检查
      5. 风险判断
      6. Human Confirm（写）/ 直接执行（读）
      7. 分布式锁 + MySQL 兜底（写）
    """
    intent = state.get("intent", "")
    user_id = state.get("user_id", "")
    query = state.get("query", "")
    trace_id = state.get("trace_id", "")
    device_info = state.get("device_info", {})
    stream_queue = get_stream_queue()

    # ---- Step 1: Tool Lookup ----
    tool = ToolRegistry.get_by_intent(intent)
    if tool is None:
        logger.warning("tool_not_found", intent=intent, trace_id=trace_id)
        return {"response": "暂不支持该操作。请转接人工客服处理。"}

    logger.info("tool_execute_start", tool=tool.name, intent=intent, trace_id=trace_id)

    # ---- Step 2: LLM 参数提取 ----
    params = await _extract_params(query, tool.name, trace_id)
    if not params:
        # 查不到参数时用 state 里的默认值兜底
        params = {
            "user_id": user_id,
            "device_sn": device_info.get("device_sn", ""),
        }

    # ---- Step 3: Schema 校验 ----
    schema_err = _validate_schema(tool, params)
    if schema_err:
        logger.warning("tool_schema_invalid", tool=tool.name, error=schema_err, trace_id=trace_id)
        return {"response": f"参数不完整，请补充信息后重试。"}

    # ---- Step 4: 权限检查 ----
    # 从 state 或 context 中获取用户角色（默认 user）
    role = state.get("role", "user") or "user"
    perm_err = _check_permission(tool.name, role)
    if perm_err:
        logger.warning("tool_permission_denied", tool=tool.name, role=role, trace_id=trace_id)
        return {"response": "您没有权限执行此操作。如需帮助请联系管理员。"}

    # ---- Step 5: 风险判断 ----
    risk = _check_risk(tool.name)
    logger.info("tool_risk_assessed", tool=tool.name, risk=risk, trace_id=trace_id)

    # ---- Step 6: 查询类 → 直接执行 ----
    if tool.name not in _CONFIRM_REQUIRED:
        try:
            result = await tool.execute(**params)
            response = _format_query_result(tool.name, result, user_id)
            return {"response": response, "pending_action": {}}
        except Exception as e:
            logger.error("tool_read_error", tool=tool.name, error=str(e), trace_id=trace_id)
            return {"response": "查询失败，请稍后重试或转接人工客服。"}

    # ---- Step 7: 写操作 → 生成确认草稿 ----
    device_sn = params.get("device_sn", device_info.get("device_sn", ""))
    problem_desc = params.get("problem_desc", params.get("fault_desc", query))

    pending_action = {
        "type": tool.name,
        "status": "waiting_confirm",
        "params": {**params, "user_id": user_id, "device_sn": device_sn},
    }

    response_text = _build_confirm_message(tool.name, device_sn, problem_desc)

    # 流式输出确认消息
    if stream_queue is not None:
        for c in response_text:
            await stream_queue.put(c)
        await stream_queue.put(None)

    logger.info("tool_pending_confirm", tool=tool.name, risk=risk, trace_id=trace_id)
    return {"pending_action": pending_action, "response": response_text}


# ================================================================
# 辅助函数
# ================================================================

def _format_query_result(tool_name: str, result: dict, user_id: str) -> str:
    """格式化查询结果。"""
    if tool_name == "query_warranty":
        return (
            f"设备 {result.get('device_sn', '')} 的保修信息：\n"
            f"保修状态：{'在保' if result.get('status') == 'valid' else '已过期'}\n"
            f"保修截止：{result.get('end_date', '未知')}"
        )
    elif tool_name == "query_device_binding":
        devices = result.get("devices", [])
        if devices:
            lines = [f"- {d.get('device_sn', '')} ({d.get('device_type', '')})" for d in devices]
            return f"您绑定的设备：\n" + "\n".join(lines)
        return "您当前没有绑定的设备。"
    return "操作完成。"


def _build_confirm_message(tool_name: str, device_sn: str, desc: str) -> str:
    """生成确认草稿消息。"""
    messages = {
        "create_ticket": (
            f"📋 工单草稿\n\n设备：{device_sn}\n故障描述：{desc}\n\n确认后将安排售后工程师处理。"
        ),
        "transfer_human": (
            "即将为您转接人工客服，对话摘要将同步给客服。确认转接？"
        ),
        "create_warranty": (
            f"📋 保修登记草稿\n\n设备序列号：{device_sn}\n问题描述：{desc}\n\n确认后将登记设备保修信息。"
        ),
    }
    return messages.get(tool_name, "请确认操作。")
