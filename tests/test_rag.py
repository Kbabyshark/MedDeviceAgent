"""RAG 检索模块测试。"""

import pytest


@pytest.mark.asyncio
async def test_rag_retrieve_empty_docs(sample_agent_state):
    from app.agent.nodes.rag_retrieve import rag_retrieve_node
    state = sample_agent_state
    state["query"] = "nonexistent_query_xyz"
    result = await rag_retrieve_node(state)
    assert "retrieved_docs" in result


@pytest.mark.asyncio
async def test_rag_rerank_empty_input(sample_agent_state):
    from app.agent.nodes.rag_rerank import rag_rerank_node
    state = sample_agent_state
    state["retrieved_docs"] = []
    result = await rag_rerank_node(state)
    assert result["retrieved_docs"] == []
    assert not result["low_confidence"]


@pytest.mark.asyncio
async def test_rag_rerank_high_confidence_skip(sample_agent_state):
    from app.agent.nodes.rag_rerank import rag_rerank_node
    state = sample_agent_state
    state["retrieved_docs"] = [
        {"content": "test", "metadata": {}, "score": 0.95},
        {"content": "test2", "metadata": {}, "score": 0.8},
    ]
    result = await rag_rerank_node(state)
    # 高置信度且 ≤3 条 → 跳过 Rerank
    assert len(result["retrieved_docs"]) <= 2


@pytest.mark.asyncio
async def test_rag_answer_empty_docs(sample_agent_state):
    from app.agent.nodes.rag_answer import rag_answer_node
    state = sample_agent_state
    state["retrieved_docs"] = []
    result = await rag_answer_node(state)
    assert "抱歉" in result["response"] or "未能在" in result["response"]


@pytest.mark.asyncio
async def test_rag_answer_with_docs(sample_agent_state):
    from app.agent.nodes.rag_answer import rag_answer_node
    state = sample_agent_state
    state["retrieved_docs"] = [
        {"content": "E101故障码表示传感器异常", "metadata": {"name": "故障手册", "device_type": "Monitor-X1", "version": "v1"}, "score": 0.9},
    ]
    result = await rag_answer_node(state)
    assert "E101" in result["response"] or "传感器" in result["response"]


@pytest.mark.asyncio
async def test_rag_answer_citations(sample_agent_state):
    from app.agent.nodes.rag_answer import rag_answer_node
    state = sample_agent_state
    state["retrieved_docs"] = [
        {"content": "设备初始化步骤", "metadata": {"name": "操作手册", "device_type": "Monitor-X1", "version": "v2"}, "score": 0.88},
    ]
    result = await rag_answer_node(state)
    citations = result.get("citations", [])
    assert len(citations) > 0
    assert citations[0]["source"] == "操作手册"


@pytest.mark.asyncio
async def test_query_rewrite_with_device(sample_agent_state):
    from app.agent.nodes.query_rewrite import query_rewrite_node
    state = sample_agent_state
    state["query"] = "E101是什么"
    state["device_info"] = {"device_type": "Monitor-X1"}
    result = await query_rewrite_node(state)
    assert "Monitor-X1" in result["query"]


@pytest.mark.asyncio
async def test_query_rewrite_no_device(sample_agent_state):
    from app.agent.nodes.query_rewrite import query_rewrite_node
    state = sample_agent_state
    state["query"] = "如何使用设备"
    state["device_info"] = {}
    result = await query_rewrite_node(state)
    assert "如何使用设备" in result["query"]


@pytest.mark.asyncio
async def test_intent_to_doc_type_mapping():
    from app.agent.nodes.rag_retrieve import _map_intent_to_doc_type
    assert _map_intent_to_doc_type("faq_query") == "faq"
    assert _map_intent_to_doc_type("fault_code_query") == "fault_code"
    assert _map_intent_to_doc_type("device_info_query") == "manual"
    assert _map_intent_to_doc_type("warranty_query") == ""  # 非 RAG 意图
