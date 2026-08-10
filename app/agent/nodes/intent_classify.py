"""
intent_classify_node

意图识别：AC 自动机规则优先 + DeepSeek-V3 LLM 兜底。
"""

from __future__ import annotations

import json

import ahocorasick

from app.agent.state import AgentState
from app.core.llm import LLMClient, ModelType, get_llm_client
from app.core.prompt_manager import get_prompt_manager
from app.core.logger import get_logger

logger = get_logger(__name__)

import datetime as _dt
def _tr(msg):
    with open("_trace.log", "a", encoding="utf-8") as f:
        f.write(f"{_dt.datetime.now().strftime('%H:%M:%S.%f')[:-3]} INTENT {msg}\n")

# ============================================================
# AC 自动机规则层 — 高频意图快速匹配
# ============================================================

_INTENT_RULES: list[tuple[list[str], str]] = [
    (["保修", "保修期", "还在保修", "免费维修", "保修查询", "保修记录"], "warranty_query"),
    (["新建保修", "添加保修", "登记保修", "创建保修", "保修登记"], "create_warranty"),
    (["转人工", "人工客服", "人工服务", "找人工", "投诉", "找客服"], "transfer_human"),
    (["绑定", "我的设备", "已绑", "设备列表", "绑定设备"], "device_binding"),
    (["故障码", "错误码", "E1", "E2", "E3", "E4", "E5", "报错", "错误代码"], "fault_code_query"),
    (["工单", "报修", "维修", "修一下", "修理", "上门", "创建工单"], "create_ticket"),
    (["怎么用", "说明书", "操作步骤", "使用说明", "初始化", "如何使用", "怎么操作"], "faq_query"),
    (["常见问题", "FAQ", "问题汇总", "常见故障"], "faq_query"),
    (["参数", "规格", "型号", "型号对比", "配置", "技术参数", "尺寸", "重量"], "device_info_query"),
    (["排查", "故障", "不工作", "没反应", "开不了机", "坏了", "异常", "不显示"], "troubleshooting"),
    (["药", "诊断", "治疗", "治病", "处方", "手术", "吃什么", "得了什么病"], "medical_risk"),
    (["政策", "售后政策", "退换货", "退货", "换货", "退款", "三包", "质保政策"], "policy_query"),
    (["你好", "您好", "在吗", "在不在", "hi", "hello", "嗨", "谢谢", "感谢", "再见", "拜拜", "晚安", "早"], "chitchat"),
]

# 构建 AC 自动机
_automaton = ahocorasick.Automaton()
for idx, (keywords, intent) in enumerate(_INTENT_RULES):
    for kw in keywords:
        _automaton.add_word(kw, (idx, intent, kw))
_automaton.make_automaton()


LLM_INTENT_SCHEMA = {
    "intent": "faq_query",
    "confidence": 0.0,
    "reason": "",
}
VALID_INTENTS = [
    "faq_query", "device_info_query", "fault_code_query",
    "troubleshooting", "warranty_query", "device_binding",
    "create_ticket", "transfer_human", "medical_risk",
    "policy_query", "create_warranty", "chitchat",
]


async def intent_classify_node(state: AgentState) -> dict:
    """意图分类节点。

    流程：
    1. AC 自动机匹配
    2. 单意图 → 直接返回
    3. 多意图 → 返回列表
    4. 未命中 → DeepSeek-V3 LLM 结构化分类（Mock 模式降级为 faq_query）
    """
    query = state.get("query", "")
    trace_id = state.get("trace_id", "")
    device_info = state.get("device_info", {})

    print(f"[TRACE] intent_classify start q={query[:60]}", flush=True)

    # ---- Step 1: AC 自动机匹配 ----
    _tr(f"AC-ITER-START qlen={len(query)}")
    print(f"[TRACE] intent_classify AC-ITER-START qlen={len(query)}", flush=True)
    hits: dict[str, int] = {}
    for end_idx, (rule_idx, intent, keyword) in _automaton.iter(query):
        hits[intent] = hits.get(intent, 0) + 1
    _tr(f"AC-ITER-DONE len={len(hits)}")
    print(f"[TRACE] intent_classify AC-ITER-DONE hits={len(hits)}", flush=True)

    # ---- Step 2: 命中处理（按命中次数 + 关键词总长度加权，长关键词优先） ----
    if hits:
        # 计算每个意图的加权分数：命中次数 + 关键词总长度/100（长关键词优先）
        # 写操作（create_ticket/create_warranty/transfer_human）额外 +0.5 优先
        _WRITE_INTENTS = {"create_ticket", "create_warranty", "transfer_human"}
        _keyword_len: dict[str, int] = {}
        for _, (_, intent, kw) in _automaton.iter(query):
            _keyword_len[intent] = _keyword_len.get(intent, 0) + len(kw)
        weighted = {
            i: hits[i] + _keyword_len.get(i, 0) / 100 + (0.5 if i in _WRITE_INTENTS else 0)
            for i in hits
        }
        sorted_intents = sorted(weighted.items(), key=lambda x: x[1], reverse=True)
        if len(sorted_intents) == 1:
            intent = sorted_intents[0][0]
            _tr(f"AC-SINGLE intent={intent}")
            logger.info("intent_rule_hit", intent=intent, query=query[:50], trace_id=trace_id)
            return {
                "intent": intent,
                "intents": [{"intent": intent, "confidence": 1.0, "source": "ac_automaton"}],
            }
        _tr(f"AC-HIT hits={dict(hits)}")
        # 多意图
        max_count = max(hits.values())
        intents = [
            {"intent": i, "confidence": round(c / max_count, 2), "source": "ac_automaton"}
            for i, c in sorted_intents
        ]
        print(f"[TRACE] intent AC hit intents={intents} primary={sorted_intents[0][0]}", flush=True)
        logger.info("intent_multi_hit", intents=intents, trace_id=trace_id)
        return {"intent": sorted_intents[0][0], "intents": intents}

    # ---- Step 3: LLM 兜底 ----
    _tr("LLM-FALLBACK")
    logger.info("intent_fallback_llm", query=query[:50], trace_id=trace_id)
    r = await _llm_classify(query, device_info, trace_id)
    _tr(f"LLM-RESULT intent={r.get('intent','?')}")
    return r


async def _llm_classify(query: str, device_info: dict, trace_id: str) -> dict:
    """LLM 结构化意图分类。"""
    llm = get_llm_client()
    pm = get_prompt_manager()

    try:
        template = pm.get("intent", "v1")
        system, user_prompt = template.render(
            query=query,
            device_info=str(device_info) if device_info else "未知设备",
        )

        result = await llm.chat_structured(
            prompt=user_prompt,
            system=system,
            model=ModelType.V3,
            temperature=0.1,
            max_tokens=256,
        )

        intent = result.get("intent", "faq_query")
        confidence = float(result.get("confidence", 0.5))

        # 校验 intent 合法性
        if intent not in VALID_INTENTS:
            logger.warning("intent_invalid_fallback", raw_intent=intent, trace_id=trace_id)
            intent = "faq_query"
            confidence = 0.3

        return {
            "intent": intent,
            "intents": [{"intent": intent, "confidence": confidence, "source": "llm"}],
        }

    except Exception as e:
        logger.error("intent_llm_error", error=str(e), trace_id=trace_id)
        return {
            "intent": "faq_query",
            "intents": [{"intent": "faq_query", "confidence": 0.3, "source": "fallback"}],
        }
