"""
RAG 检索质量评估。

指标：
- Recall@K: 正确文档出现在 Top-K 中的比例
- Precision@K: Top-K 中正确文档的比例
- MRR (Mean Reciprocal Rank): 第一个正确答案排名的倒数均值
- NDCG@K: 归一化折损累积增益

使用方式：
    uv run python tests/eval/rag_eval.py
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

# 评估数据集目录
EVAL_DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass
class RAGTestCase:
    """单条 RAG 评估用例。"""

    query: str
    device_type: str = ""
    doc_type: str = ""
    relevant_doc_ids: list[str] = field(default_factory=list)  # 标注的相关文档 ID
    relevant_chunk_ids: list[str] = field(default_factory=list)  # 标注的相关 Chunk ID


@dataclass
class RAGEvalResult:
    """RAG 评估结果。"""

    total_queries: int = 0
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    precision_at_5: float = 0.0
    mrr: float = 0.0
    ndcg_at_5: float = 0.0
    per_query: list[dict] = field(default_factory=list)


class RAGEvaluator:
    """RAG 检索评估器。

    使用方式：
        evaluator = RAGEvaluator(test_cases)
        result = await evaluator.evaluate()
        evaluator.print_report(result)
    """

    def __init__(self, test_cases: list[RAGTestCase]) -> None:
        self.cases = test_cases

    async def evaluate(self, top_k: int = 5) -> RAGEvalResult:
        """对所有测试用例进行评估。"""
        from app.rag.retriever import RagRetriever
        retriever = RagRetriever()

        result = RAGEvalResult(total_queries=len(self.cases))
        rr_sum = 0.0
        ndcg_sum = 0.0

        for case in self.cases:
            # 检索
            docs = await retriever.retrieve(
                query=case.query,
                device_type=case.device_type,
                doc_type=case.doc_type,
                top_k=top_k,
            )

            retrieved_ids = [d.get("metadata", {}).get("document_id", "") for d in docs]
            retrieved_scores = [d.get("score", 0) for d in docs]
            relevant_set = set(case.relevant_doc_ids)

            # Recall@K
            hits = sum(1 for rid in retrieved_ids if rid in relevant_set)
            total_relevant = len(relevant_set) if relevant_set else 1

            # Reciprocal Rank
            rr = 0.0
            for rank, rid in enumerate(retrieved_ids, 1):
                if rid in relevant_set:
                    rr = 1.0 / rank
                    break

            # NDCG@K
            ideal_scores = sorted(retrieved_scores, reverse=True)[:top_k]
            dcg = sum(
                (1.0 if rid in relevant_set else 0.0) / math.log2(i + 2)
                for i, rid in enumerate(retrieved_ids[:top_k])
            )
            idcg = sum(s / math.log2(i + 2) for i, s in enumerate(ideal_scores)) or 1.0

            rr_sum += rr
            ndcg_sum += dcg / idcg

            per_query = {
                "query": case.query,
                "retrieved": retrieved_ids[:top_k],
                "relevant": list(relevant_set),
                "recall_at_k": round(hits / total_relevant, 3),
                "rr": round(rr, 4),
            }
            result.per_query.append(per_query)

            # 累加
            result.recall_at_1 += (1 if retrieved_ids[:1] and retrieved_ids[0] in relevant_set else 0)
            result.recall_at_3 += (1 if any(rid in relevant_set for rid in retrieved_ids[:3]) else 0)
            result.recall_at_5 += (1 if any(rid in relevant_set for rid in retrieved_ids[:5]) else 0)
            result.precision_at_5 += hits / min(top_k, len(retrieved_ids)) if retrieved_ids else 0

        n = max(len(self.cases), 1)
        result.recall_at_1 /= n
        result.recall_at_3 /= n
        result.recall_at_5 /= n
        result.precision_at_5 /= n
        result.mrr = round(rr_sum / n, 4)
        result.ndcg_at_5 = round(ndcg_sum / n, 4)

        return result

    def print_report(self, result: RAGEvalResult) -> None:
        """打印评估报告。"""
        print("\n" + "=" * 60)
        print("RAG 检索质量评估报告")
        print("=" * 60)
        print(f"测试用例数: {result.total_queries}")
        print(f"{'Recal@1':<15}: {result.recall_at_1:.2%}")
        print(f"{'Recal@3':<15}: {result.recall_at_3:.2%}")
        print(f"{'Recal@5':<15}: {result.recall_at_5:.2%}  ← 目标 > 85%")
        print(f"{'Precision@5':<15}: {result.precision_at_5:.2%}")
        print(f"{'MRR':<15}: {result.mrr:.4f}")
        print(f"{'NDCG@5':<15}: {result.ndcg_at_5:.4f}")
        print("-" * 60)
        print("各查询详情:")
        for q in result.per_query:
            status = "✓" if q["recall_at_k"] > 0 else "✗"
            print(f"  {status} {q['query'][:50]}... → {q['retrieved']}")
        print("=" * 60)


# ---- 内置测试数据集 ----
def get_builtin_test_cases() -> list[RAGTestCase]:
    """内置测试用例（开发阶段 Mock 数据）。"""
    return [
        RAGTestCase(
            query="设备显示E101故障码是什么意思",
            device_type="Monitor-X1",
            doc_type="fault_code",
            relevant_doc_ids=["doc_fault_monitor_x1"],
        ),
        RAGTestCase(
            query="如何进行设备初始化",
            device_type="Monitor-X1",
            doc_type="manual",
            relevant_doc_ids=["doc_manual_monitor_x1"],
        ),
        RAGTestCase(
            query="保修期限是多久",
            device_type="Monitor-X1",
            doc_type="faq",
            relevant_doc_ids=["doc_faq_warranty"],
        ),
        RAGTestCase(
            query="传感器异常怎么排查",
            device_type="Monitor-Pro",
            doc_type="fault_code",
            relevant_doc_ids=["doc_fault_monitor_pro"],
        ),
        RAGTestCase(
            query="如何清洁设备屏幕",
            device_type="Monitor-X1",
            doc_type="manual",
            relevant_doc_ids=["doc_manual_monitor_x1"],
        ),
    ]


def load_test_cases(filepath: str) -> list[RAGTestCase]:
    """从 JSON 文件加载测试用例。"""
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    return [RAGTestCase(**item) for item in data]


# ---- CLI 入口 ----
if __name__ == "__main__":
    import asyncio

    async def main():
        cases = get_builtin_test_cases()
        evaluator = RAGEvaluator(cases)
        result = await evaluator.evaluate(top_k=5)
        evaluator.print_report(result)

    asyncio.run(main())
