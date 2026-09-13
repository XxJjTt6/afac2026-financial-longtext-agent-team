"""V43无旧答案锚定的原始材料完整命题裁决。"""

from __future__ import annotations

from typing import Any

from agent.schemas import RetrievalResult
from agent_team_b1.accuracy_adjudication_v38 import (
    _complete_option_evidence_v38,
    _extract_accuracy_payload_v38,
)
from agent_team_b1.provenance_reasoning_v35 import (
    normalize_response_answers_v35,
)
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements


VERDICTS_V43 = {
    "fully_supported",
    "contradicted",
    "partial_or_unsupported",
}
REASONING_SECTIONS_V43 = ("定位依据", "关键信息", "分析推导", "结论")
NEGATIVE_QUESTION_MARKERS_V43 = (
    "说法错误",
    "表述错误",
    "判断错误",
    "不正确的是",
    "不符合的是",
)


def _asks_for_incorrect_v43(question: BQuestion) -> bool:
    return any(
        marker in question.question for marker in NEGATIVE_QUESTION_MARKERS_V43
    )


def build_source_entailment_messages_v43(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    max_evidence_chars: int,
    max_documents: int,
    max_chunks: int,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    """构造隐藏旧答案、逐项检查完整命题的独立裁决提示。"""
    if not question.options:
        raise ValueError("V43完整命题裁决仅处理选择题")
    evidence_text, selected = _complete_option_evidence_v38(
        evidence,
        question_text=question.question,
        options=question.options,
        max_chars=max_evidence_chars,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    options_text = "\n".join(
        f"{key}. {value}" for key, value in question.options.items()
    )
    option_schema = ",".join(
        (
            f'"{key}":{{"verdict":"fully_supported|contradicted|'
            'partial_or_unsupported","basis":"逐子句依据",'
            '"page_refs":["doc_id:p页码"]}'
        )
        for key in question.options
    )
    system = (
        "你是金融原始材料命题核验员，只能依据题面和赛事官方材料裁决。"
        "你看不到任何历史答案，必须独立作答，不得使用多数票、答案惯性或常识补全。"
        "逐项拆分每个选项的完整命题；选项包含多个子句、因果、比较、范围或绝对词时，"
        "只有所有必要子句都得到材料支持，才可标为fully_supported。"
        "只支持其中一部分、需要跨越材料作无依据推断、主体或时间口径不一致，均标为"
        "partial_or_unsupported；原文明确相反则标为contradicted。"
        "研究报告比较题允许有材料支撑的归纳，但必须列出归纳两端的事实，不能只写"
        "符合常识或逻辑上可能。问题问正确项时，只选择fully_supported；问题问错误项时，"
        "只选择contradicted。不得用排除法把partial_or_unsupported升级为正确。"
        "每个选项必须给出实际doc_id和PDF页码。只输出JSON，不输出Markdown。"
        "JSON字段固定为answers、option_audit、reasoning、doc_ids。"
        f'option_audit结构为{{{option_schema}}}。'
        "reasoning必须依次包含定位依据、关键信息、分析推导、结论四个标签，"
        "结论必须写出最终答案。"
    )
    user = (
        f"qid：{question.qid}\n领域：{question.domain}\n题型：{question.type}\n"
        f"问题：{question.question}\n选项：\n{options_text}\n\n"
        f"答案格式：{_format_requirements(question)}\n\n"
        f"赛事官方材料证据窗口：\n{evidence_text}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], selected


def parse_source_entailment_response_v43(
    question: BQuestion,
    text: str,
    *,
    allowed_doc_ids: set[str],
) -> dict[str, Any]:
    """验证独立答案与逐项完整命题裁决严格一致。"""
    payload = _extract_accuracy_payload_v38(text)
    answers = normalize_response_answers_v35(
        question,
        payload.get("answers", []),
    )
    raw_audit = payload.get("option_audit")
    if not isinstance(raw_audit, dict):
        raise ValueError(f"{question.qid} 缺少option_audit对象")
    if set(raw_audit) != set(question.options):
        raise ValueError(f"{question.qid} 未逐项覆盖所有选项")

    option_audit: dict[str, dict[str, Any]] = {}
    for option, item in raw_audit.items():
        if not isinstance(item, dict):
            raise ValueError(f"{question.qid} 的{option}裁决结构非法")
        verdict = str(item.get("verdict", "")).strip().lower()
        basis = str(item.get("basis", "")).strip()
        page_refs = [
            str(value).strip()
            for value in item.get("page_refs", [])
            if str(value).strip()
        ]
        if verdict not in VERDICTS_V43 or not basis or not page_refs:
            raise ValueError(f"{question.qid} 的{option}裁决不完整")
        option_audit[str(option)] = {
            "verdict": verdict,
            "basis": basis,
            "page_refs": page_refs,
        }

    chosen = set("".join(answers))
    if _asks_for_incorrect_v43(question):
        invalid = sorted(
            option
            for option in chosen
            if option_audit[option]["verdict"] != "contradicted"
        )
        omitted = sorted(
            option
            for option, item in option_audit.items()
            if item["verdict"] == "contradicted" and option not in chosen
        )
        if invalid:
            raise ValueError(f"{question.qid} 选中了未被原文反驳的错误项: {invalid}")
        if omitted:
            raise ValueError(f"{question.qid} 遗漏了原文反驳的错误项: {omitted}")
    else:
        invalid = sorted(
            option
            for option in chosen
            if option_audit[option]["verdict"] != "fully_supported"
        )
        omitted = sorted(
            option
            for option, item in option_audit.items()
            if item["verdict"] == "fully_supported" and option not in chosen
        )
        if invalid:
            raise ValueError(f"{question.qid} 选项未完整支持: {invalid}")
        if omitted:
            raise ValueError(f"{question.qid} 遗漏完整支持项: {omitted}")

    reasoning = str(payload.get("reasoning") or payload.get("reason", "")).strip()
    if not 100 <= len(reasoning) <= 700:
        raise ValueError(f"{question.qid} reasoning长度不合规")
    positions = [reasoning.find(section) for section in REASONING_SECTIONS_V43]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError(f"{question.qid} reasoning四段缺失或顺序错误")

    doc_ids = [
        str(value).strip()
        for value in payload.get("doc_ids", [])
        if str(value).strip()
    ]
    if not doc_ids:
        raise ValueError(f"{question.qid} 未声明doc_ids")
    outside = sorted(set(doc_ids) - set(allowed_doc_ids))
    if outside:
        raise ValueError(f"{question.qid} 声明窗口外doc_id: {outside}")
    return {
        "answers": answers,
        "option_audit": option_audit,
        "reasoning": reasoning,
        "doc_ids": doc_ids,
    }
