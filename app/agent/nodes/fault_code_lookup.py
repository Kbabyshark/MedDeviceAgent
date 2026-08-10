"""
fault_code_lookup_node

当意图为 fault_code_query 时，不查知识库，直接从故障码表精确查询。
LLM 从用户问题中提取故障码 + 设备型号 → MySQL 查询 → 结果格式化 → 交给 LLM 回答。
"""

from __future__ import annotations

import asyncio

from app.agent.state import AgentState, get_stream_queue
from app.core.llm import ModelType, get_llm_client
from app.core.prompt_manager import get_prompt_manager
from app.core.logger import get_logger

logger = get_logger(__name__)

EXTRACT_PROMPT = """从用户问题中提取故障码和设备型号，返回 JSON。

示例1: "海尔KFR-600的E1故障码代表什么" → {"fault_code":"E1","device_model":"KFR-600"}
示例2: "E5故障怎么解决" → {"fault_code":"E5","device_model":""}
示例3: "美的MDV-450的H5是什么" → {"fault_code":"H5","device_model":"MDV-450"}

规则:
- fault_code: 故障码本身，如 E1、Er:04、ECG-ERR。如果用户没提，返回空字符串
- device_model: 设备型号（数字字母组合），如 KFR-600、MDV-450。如果用户没提，返回空字符串

只返回 JSON，不要其他文字。"""


def _query_mysql_sync(fault_code: str, device_model: str) -> list[tuple]:
    """同步 MySQL 查询 — 在 thread executor 中执行，避免阻塞事件循环。"""
    import pymysql
    from app.core.config import get_settings

    s = get_settings().mysql
    conn = pymysql.connect(
        host="127.0.0.1", port=s.port, user=s.user,
        password=s.password, database=s.database,
        charset="utf8mb4", connect_timeout=3,
    )
    try:
        cur = conn.cursor()
        if device_model:
            cur.execute(
                "SELECT device_name, device_model, fault_code, fault_symptom, fault_cause, solution "
                "FROM fault_code WHERE fault_code=%s AND device_model LIKE %s LIMIT 5",
                (fault_code, f"%{device_model}%"))
        else:
            cur.execute(
                "SELECT device_name, device_model, fault_code, fault_symptom, fault_cause, solution "
                "FROM fault_code WHERE fault_code=%s LIMIT 5",
                (fault_code,))
        return cur.fetchall()
    finally:
        conn.close()


async def fault_code_lookup_node(state: AgentState) -> dict:
    """故障码精确查询节点。

    1. LLM 提取 (fault_code, device_model)
    2. MySQL fault_code 表查询
    3. 命中 → 返回结构化结果让 LLM 回答
    4. 未命中或缺失信息 → 引导用户补充
    """
    query = state.get("query", "")
    trace_id = state.get("trace_id", "")
    stream_queue = get_stream_queue()

    print(f"[TRACE] fault_code_lookup START q={query[:60]}", flush=True)

    llm = get_llm_client()

    # Step 1: LLM 提取
    try:
        extract_result = await llm.chat_structured(
            prompt=query + "\n\n" + EXTRACT_PROMPT,
            model=ModelType.V3, temperature=0.0, max_tokens=128,
        )
    except Exception:
        extract_result = {"fault_code": "", "device_model": ""}

    fault_code = (extract_result.get("fault_code", "") or "").strip()
    device_model = (extract_result.get("device_model", "") or "").strip()

    logger.info("fault_code_extract", fault_code=fault_code, device_model=device_model, trace_id=trace_id)

    # Step 2: 缺少关键信息 → 让用户补充
    if not fault_code:
        msg = "请提供具体的故障码（如 E1、H5、Er:04），我好帮您查询对应的故障原因和解决方法。"
        if stream_queue:
            for c in msg: await stream_queue.put(c)
            await stream_queue.put(None)
        return {"response": msg, "citations": []}

    # Step 3: 查询 MySQL（线程池执行，不阻塞事件循环）
    try:
        rows = await asyncio.to_thread(_query_mysql_sync, fault_code, device_model)
    except Exception as e:
        logger.error("fault_code_db_error", error=str(e), trace_id=trace_id)
        rows = []

    # Step 4: 未命中
    if not rows:
        hint = f"未找到故障码「{fault_code}」"
        if device_model:
            hint += f"在设备型号「{device_model}」中"
        hint += "的相关记录。请确认故障码是否正确，或转人工客服查询。"
        if stream_queue:
            for c in hint: await stream_queue.put(c)
            await stream_queue.put(None)
        return {"response": hint, "citations": []}

    # Step 5: 命中 → 交给 LLM 生成口语化回答
    structured = []
    for r in rows:
        structured.append(
            f"- 设备: {r[0]}（型号: {r[1]}）\n"
            f"  故障码: {r[2]}\n"
            f"  故障现象: {r[3]}\n"
            f"  故障原因: {r[4]}\n"
            f"  解决方法: {r[5]}"
        )
    context = "\n\n".join(structured)
    citations = [{"source": f"{r[0]} {r[2]}", "device_type": r[1]} for r in rows]

    logger.info("fault_code_hit", count=len(rows), fault_code=fault_code, trace_id=trace_id)

    # 复用 RAG 同一套 prompt，保持客服语气一致
    pm = get_prompt_manager()
    template = pm.get("rag", "v2")
    system, user_prompt = template.render(
        query=query,
        context=context,
        device_info=device_model or "未知设备",
    )

    # 流式 LLM 生成
    if stream_queue is not None:
        response = ""
        async for token in llm.chat_stream(
            prompt=user_prompt, system=system,
            model=ModelType.V3, temperature=0.5, max_tokens=1024,
        ):
            response += token
            await stream_queue.put(token)
        await stream_queue.put(None)
    else:
        result = await llm.chat(
            prompt=user_prompt, system=system,
            model=ModelType.V3, temperature=0.5, max_tokens=1024,
        )
        response = result.content

    return {
        "response": response,
        "retrieved_docs": [{
            "content": context,
            "metadata": {"name": f"故障码表-{fault_code}", "structured": True},
            "score": 1.0,
        }],
        "citations": citations,
    }
