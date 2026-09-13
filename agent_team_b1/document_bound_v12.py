"""V12 文档标题绑定与严格 doc_id 修复契约。"""

from __future__ import annotations

from agent_team_b1.clean_run_v10 import build_repair_messages
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import extract_model_payload


def effective_document_limit(question: BQuestion, *, configured_limit: int) -> int:
    """显式指定单份金融合同文档时，只保留检索排名第一的文档。"""
    if configured_limit < 1:
        raise ValueError("configured_limit 必须为正整数")
    if question.domain == "financial_contracts" and "《" in question.question and "》" in question.question:
        return 1
    return configured_limit


def build_strict_repair_messages(
    question: BQuestion,
    *,
    original_messages: list[dict[str, str]],
    invalid_response: str,
    error: str,
    allowed_doc_ids: set[str],
) -> list[dict[str, str]]:
    """在修复请求中明列允许与禁止的 doc_id，避免再次幻觉引用。"""
    if not allowed_doc_ids:
        raise ValueError("allowed_doc_ids 不能为空")
    messages = build_repair_messages(
        question,
        original_messages=original_messages,
        invalid_response=invalid_response,
        error=error,
    )
    try:
        payload = extract_model_payload(invalid_response)
        claimed = set(payload.get("doc_ids", []))
    except ValueError:
        claimed = set()
    disallowed = sorted(claimed - allowed_doc_ids)
    allowed_text = "、".join(sorted(allowed_doc_ids))
    forbidden_text = "".join(f"不得输出 {doc_id}。" for doc_id in disallowed)
    messages[-1]["content"] += (
        f"本题允许的 doc_id 仅为：{allowed_text}。"
        f"{forbidden_text}doc_ids 必须是该允许集合的非空子集。"
    )
    return messages
