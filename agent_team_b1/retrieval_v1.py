"""将 B 榜题目适配到既有自适应盲检索引。"""

from __future__ import annotations

from agent.config import Settings
from agent.index.bm25 import BM25SearchIndex
from agent.index.document_index import DocumentSearchIndex
from agent.schemas import Question, RetrievalResult
from agent_team_b1.questions_v1 import BQuestion
from agent_team_v7.adaptive_blind import AdaptiveBlindRetriever
from agent_team_v9.option_coverage_index import OptionCoverageIndex


class B1Retriever:
    """保持 B 榜 schema 独立，同时复用已验证的检索实现。"""

    def __init__(self, retriever: AdaptiveBlindRetriever) -> None:
        self.retriever = retriever

    @staticmethod
    def adapt_question(question: BQuestion) -> Question:
        answer_format = {
            "single": "mcq",
            "multi": "multi",
            "tf": "tf",
            "freeform": "mcq",
        }[question.answer_kind]
        return Question(
            qid=question.qid,
            domain=question.domain,
            split=question.split,
            question=question.question,
            options=question.options,
            answer_format=answer_format,
            type=question.type,
            doc_ids=[],
        )

    def retrieve(
        self,
        question: BQuestion,
        restrict_to_doc_ids: bool = True,
    ) -> list[RetrievalResult]:
        adapted = self.adapt_question(question)
        return self.retriever.retrieve(adapted, restrict_to_doc_ids=False)


def build_b1_retriever(
    settings: Settings,
    *,
    default_shortlist_size: int = 12,
    expanded_shortlist_size: int = 20,
    top_k: int = 40,
) -> B1Retriever:
    """从已预处理的块级和文档级 BM25 索引构建 B1 检索器。"""
    raw_index = BM25SearchIndex.load(settings.index_dir / "bm25_index.pkl")
    doc_index_path = settings.index_dir / "document_bm25_index.pkl"
    if not doc_index_path.exists():
        raise FileNotFoundError(f"缺少文档索引: {doc_index_path}")
    doc_index = DocumentSearchIndex.load(doc_index_path)
    covered_index = OptionCoverageIndex(raw_index, pool_multiplier=8)
    adaptive = AdaptiveBlindRetriever(
        covered_index,
        doc_index=doc_index,
        top_k_per_query=max(top_k, expanded_shortlist_size),
        fused_top_k=top_k,
        strategy="doc_first_bm25f_expansion",
        blind_top_docs=default_shortlist_size,
        expanded_blind_top_docs=expanded_shortlist_size,
        coverage_start_rank=0,
    )
    return B1Retriever(adaptive)

