"""
input_safety_check_node / output_safety_check_node

医疗场景安全检测：正则快速匹配 + DeepSeek-V3 LLM 语义检测。

检测范围：
输入：医疗诊断请求、治疗建议、用药建议、隐私攻击、越权请求
输出：无依据承诺、错误医疗建议、越权回答、医疗器械虚假宣传
"""

from __future__ import annotations

import re

from app.agent.state import AgentState
from app.core.llm import ModelType, get_llm_client
from app.core.prompt_manager import get_prompt_manager
from app.core.logger import get_logger

logger = get_logger(__name__)

import datetime as _dt
def _tr(msg):
    with open("_trace.log", "a", encoding="utf-8") as f:
        f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} {msg}\n")
_tr("MODULE-LOADED")

# ============================================================
# 正则快速匹配（零延迟优先拦截）
# ============================================================

_HIGH_RISK_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 医疗诊断
    (re.compile(r"我.*(得了|患上|是不是).*(病|癌|症)"), "medical_diagnosis"),
    (re.compile(r"(诊断|确诊).*(什么病|什么原因|怎么引起)"), "medical_diagnosis"),
    (re.compile(r"(症状|病因|病理).*(帮我|告诉我|是什么)"), "medical_diagnosis"),
    # 治疗建议
    (re.compile(r"应该.*(吃什么药|用什么药|怎么治疗|打什么针|怎么治)"), "treatment_advice"),
    (re.compile(r"(药|药品|处方|剂量|服用|注射).*推荐"), "medication_advice"),
    (re.compile(r"(手术|化疗|放疗|透析|切除)"), "treatment_advice"),
    # 隐私攻击
    (re.compile(r"(我的|帮我查).*(隐私|密码|身份证|银行卡|病历|体检报告)"), "privacy"),
    (re.compile(r"(别人|他人|某某).*(设备|病历|信息)"), "privacy"),
    # 越权请求
    (re.compile(r"(帮我|能不能).*(删除|修改|清空).*(记录|数据|账号)"), "unauthorized"),
]

# 输出端 —— 无依据承诺检测
_OUTPUT_RISK_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"保证.*(治好|治愈|康复|恢复|痊愈)"), "false_promise"),
    (re.compile(r"100%.*(有效|安全|没问题|治愈|康复)"), "false_promise"),
    (re.compile(r"绝对.*(不会|可以|能|没问题)"), "false_promise"),
    (re.compile(r"(肯定|必然|必定).*(治好|康复)"), "false_promise"),
    (re.compile(r"建议.*(服用|使用|购买).*(药|药品)"), "medication_advice_output"),
    (re.compile(r"(这款|这个).*(设备|仪器|机器).*(治疗|治愈).*(疾病|病|癌)"), "device_medical_claim"),
]


async def input_safety_check_node(state: AgentState) -> dict:
    """输入安全检测节点。

    两层检测：
    1. 正则快速匹配（零延迟）
    2. LLM 语义检测（Mock 模式跳过）

    高风险 → safe_reply_node
    正常 → intent_classify_node
    """
    query = state.get("query", "")
    trace_id = state.get("trace_id", "")
    _tr(f"SAFETY-START {query[:20]}")
    for pattern, risk_type in _HIGH_RISK_PATTERNS:
        if pattern.search(query):
            logger.warning(
                "input_safety_regex_hit",
                risk_type=risk_type,
                pattern=pattern.pattern[:50],
                query=query[:100],
                trace_id=trace_id,
            )
            return {
                "risk_level": "high",
                "risk_detail": {"type": risk_type, "source": "regex", "reason": f"匹配规则: {risk_type}"},
            }

    # ---- Layer 2: LLM 语义检测 ----
    print(f"[TRACE] safety_check LLM start q={query[:40]}", flush=True)
    llm = get_llm_client()
    if not llm.mock_mode:
        try:
            pm = get_prompt_manager()
            template = pm.get("safety", "v1")
            system, user_prompt = template.render(text=query)

            result = await llm.chat_structured(
                prompt=user_prompt,
                system=system,
                model=ModelType.V3,
                temperature=0.0,
                max_tokens=256,
            )
            print(f"[TRACE] safety_check LLM result={result.get('risk_level','?')}", flush=True)

            risk_level = result.get("risk_level", "none")
            if risk_level in ("high", "medium"):
                logger.warning(
                    "input_safety_llm_hit",
                    risk_level=risk_level,
                    risk_type=result.get("risk_type", ""),
                    trace_id=trace_id,
                )
                return {
                    "risk_level": "high",
                    "risk_detail": {
                        "type": result.get("risk_type", "unknown"),
                        "source": "llm",
                        "reason": result.get("reason", ""),
                    },
                }

        except Exception as e:
            print(f"[TRACE] safety_check LLM EXCEPTION: {e}", flush=True)
            logger.error("input_safety_llm_error", error=str(e), trace_id=trace_id)
            # LLM 检测失败不阻塞流程

    print(f"[TRACE] safety_check DONE → risk=none", flush=True)
    return {"risk_level": "none", "risk_detail": None}


async def output_safety_check_node(state: AgentState) -> dict:
    """输出安全检测节点。

    检测 Agent 回答中的风险内容：
    1. 正则检测无依据承诺
    2. LLM 语义检测（Mock 模式跳过）

    发现风险 → 改写输出或标记警告。
    """
    response = state.get("response", "")
    trace_id = state.get("trace_id", "")
    risk_level = state.get("risk_level", "none")

    # 已经是高风险输入 → 不再重复检测输出
    if risk_level == "high":
        return {}

    # ---- Layer 1: 正则检测 ----
    for pattern, risk_type in _OUTPUT_RISK_PATTERNS:
        if pattern.search(response):
            logger.warning(
                "output_safety_regex_hit",
                risk_type=risk_type,
                trace_id=trace_id,
            )
            # 自动修正：替换过度承诺的表述
            response = _sanitize_response(response, risk_type)
            return {"response": response}

    # ---- Layer 2: LLM 语义检测 ----
    llm = get_llm_client()
    if not llm.mock_mode:
        try:
            pm = get_prompt_manager()
            template = pm.get("safety", "v1")
            system, user_prompt = template.render(text=response)

            result = await llm.chat_structured(
                prompt=f"请检测以下客服回答是否包含医疗风险或虚假承诺：\n\n{user_prompt}",
                system="你是医疗设备客服回答审核员。检测是否包含无依据承诺、错误医疗建议、越权回答。",
                model=ModelType.V3,
                temperature=0.0,
                max_tokens=256,
            )

            if result.get("risk_level") in ("high", "medium"):
                logger.warning("output_safety_llm_hit", risk_level=result.get("risk_level"), trace_id=trace_id)
                return {"response": _sanitize_response(response, "llm_flagged")}

        except Exception as e:
            logger.error("output_safety_llm_error", error=str(e), trace_id=trace_id)

    return {}


def _sanitize_response(response: str, risk_type: str) -> str:
    """安全化改写输出。

    根据风险类型修正回答中的不安全表述。
    """
    # 移除绝对承诺词汇
    replacements = {
        "保证": "根据设备知识库信息，",
        "100%": "",
        "绝对": "",
        "肯定": "根据记录",
        "必然": "",
    }

    sanitized = response
    for old, new in replacements.items():
        sanitized = sanitized.replace(old, new)

    # 在末尾追加免责声明
    disclaimer = "\n\n---\n*本回答基于设备知识库信息，不构成医疗建议。如有健康问题请咨询专业医疗机构。*"

    if risk_type in ("medication_advice_output", "device_medical_claim", "llm_flagged"):
        sanitized = (
            "您的问题可能涉及医疗范畴。作为设备售后客服，我仅提供设备技术支持和故障排查。\n"
            "如有健康相关问题，请咨询专业医疗机构。"
        )
        return sanitized

    return sanitized + disclaimer
