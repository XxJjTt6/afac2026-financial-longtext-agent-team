"""B 榜 V10 正式运行的小型审计辅助函数。"""

from __future__ import annotations

from agent_team_b1.questions_v1 import BQuestion


def validate_claimed_doc_ids(
    qid: str,
    claimed_doc_ids: list[str],
    provided_doc_ids: set[str],
) -> None:
    """防止 reasoning 声称使用本次 prompt 未提供的外部材料。"""
    unknown = sorted(set(claimed_doc_ids) - provided_doc_ids)
    if unknown:
        raise ValueError(f"{qid} 声称使用了未提供的官方证据: {unknown}")


def projected_total_tokens(current_total: int, *, completed: int, total_questions: int) -> int:
    """按已完成题目的实测均值投影整份提交 Token 总量。"""
    if completed <= 0 or total_questions <= 0:
        return 0
    return round(current_total / completed * total_questions)


def build_repair_messages(
    question: BQuestion,
    *,
    original_messages: list[dict[str, str]],
    invalid_response: str,
    error: str,
) -> list[dict[str, str]]:
    """在保留原题面和官方证据的前提下进行一次可审计的结构修复。"""
    return [
        *original_messages,
        {"role": "assistant", "content": invalid_response},
        {
            "role": "user",
            "content": (
                f"上一次输出未通过校验，qid={question.qid}，错误={error}。"
                "请仍然只使用上文的题面与官方证据，重新核对答案并输出完整 JSON。"
                f"answers 必须恰好包含 {question.expected_answers} 个元素。"
                "reasoning 必须为160至320个中文字符，并依次包含"
                "定位依据、关键信息、分析推导和结论四个标签；"
                "doc_ids 只能填写上文实际提供的 doc_id。"
                "只输出 JSON，不要输出其他文字。"
            ),
        },
    ]
