"""V21 在领域全部官方文档内对每个选项独立执行 BM25 检索。"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from agent.index.bm25 import BM25SearchIndex
from agent.schemas import RetrievalResult
from agent_team_b1.focused_reasoning_v11 import _focused_excerpt
from agent_team_b1.questions_v1 import BQuestion


def option_queries(question: BQuestion) -> list[str]:
    if not question.options:
        return [question.question]
    return [
        f"{question.question}\n选项{key}：{value}"
        for key, value in question.options.items()
    ]


def _domain_doc_ids(documents_path: Path) -> dict[str, set[str]]:
    by_domain: dict[str, set[str]] = {}
    with Path(documents_path).open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            domain = str(row.get("domain", ""))
            doc_id = str(row.get("doc_id", ""))
            if domain and doc_id:
                by_domain.setdefault(domain, set()).add(doc_id)
    return by_domain


class DomainOptionTargetRetriever:
    def __init__(
        self,
        index: BM25SearchIndex,
        domain_doc_ids: dict[str, set[str]],
        *,
        top_k_per_query: int = 4,
        excerpt_chars: int = 1400,
    ) -> None:
        self.index = index
        self.domain_doc_ids = domain_doc_ids
        self.top_k_per_query = top_k_per_query
        self.excerpt_chars = excerpt_chars

    def retrieve(
        self,
        question: BQuestion,
        restrict_to_doc_ids: bool = True,
    ) -> list[RetrievalResult]:
        del restrict_to_doc_ids
        allowed = self.domain_doc_ids.get(question.domain, set())
        if not allowed:
            raise ValueError(f"{question.qid} 所在领域没有官方文档: {question.domain}")
        primary: list[RetrievalResult] = []
        secondary: list[RetrievalResult] = []
        for query in option_queries(question):
            hits = self.index.search(
                query,
                top_k=self.top_k_per_query,
                filter_doc_ids=allowed,
                source="v21_domain_option_target",
                scoring_mode="bm25f_lite",
            )
            prepared = [
                replace(
                    hit,
                    evidence_text=_focused_excerpt(
                        hit.evidence_text,
                        focus_text=query,
                        max_chars=self.excerpt_chars,
                    ),
                    query=query,
                )
                for hit in hits
            ]
            if prepared:
                primary.append(prepared[0])
                secondary.extend(prepared[1:])
        selected = [*primary, *secondary]
        if not selected:
            raise ValueError(f"{question.qid} 未检索到选项级官方证据")
        return selected


def build_domain_option_target_retriever(index_dir: Path) -> DomainOptionTargetRetriever:
    root = Path(index_dir).parent
    index = BM25SearchIndex.load(Path(index_dir) / "bm25_index.pkl")
    return DomainOptionTargetRetriever(
        index,
        _domain_doc_ids(root / "documents.jsonl"),
    )
