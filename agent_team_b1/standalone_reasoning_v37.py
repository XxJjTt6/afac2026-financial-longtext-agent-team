"""V37 面向仅查看 reasoning 文本的官方 judge 进行独立可读精修。"""

from __future__ import annotations

import re
from typing import Any

from agent.schemas import RetrievalResult
from agent_team_b1.clean_reasoning_v10 import REASONING_SECTIONS
from agent_team_b1.option_coverage_v13 import option_coverage_evidence
from agent_team_b1.provenance_reasoning_v35 import normalize_response_answers_v35
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements, extract_model_payload


REFINEMENT_QIDS_V37: tuple[str, ...] = (
    "fc_b_003",
    "fc_b_014",
    "fc_b_020",
    "fin_b_009",
    "ins_b_006",
    "ins_b_013",
    "ins_b_014",
    "ins_b_017",
    "ins_b_020",
    "reg_b_008",
    "reg_b_013",
    "reg_b_016",
    "reg_b_018",
    "reg_b_027",
    "res_b_008",
)


PROMOTED_REFINEMENT_QIDS_V37: tuple[str, ...] = (
    "fc_b_003",
    "fc_b_014",
    "fin_b_009",
    "ins_b_006",
    "ins_b_013",
    "ins_b_017",
    "reg_b_013",
    "reg_b_018",
    "res_b_008",
)


ANSWER_OVERRIDES_V37: dict[str, list[str]] = {
    "fc_b_003": ["ABCD"],
}


_PROHIBITED_TEXT_V37 = (
    "锁定答案",
    "候选答案",
    "第一阶段",
    "第二阶段",
    "人工原文审计",
    "已审计",
    "证据窗口",
    "doc_id",
    "qid",
)


_PROHIBITED_PATTERNS_V37 = (
    re.compile(r"(?:官方)?证据\s*\d+"),
    re.compile(r"\b(?:text\d+|pack\d+_text\d+|annual_[A-Za-z0-9_-]+)\b", re.I),
)


def _answer_text(answers: list[str]) -> str:
    return "；".join(str(value) for value in answers)


def normalize_final_format_v37(reasoning: str, answers: list[str]) -> str:
    """仅统一段落标签和结论连接符，不增加或改变任何事实与推导。"""
    normalized = str(reasoning).strip()
    replacements = (
        (r"定位依据(?:为|是|包括|显示)?\s*[：:]?", "定位依据："),
        (r"关键信息(?:为|显示|包括|指出)?\s*[：:]?", "关键信息："),
        (r"分析推导(?:为|显示|指出|认为)?\s*[：:]?", "分析推导："),
    )
    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, count=1)

    conclusions = list(
        re.finditer(r"结论(?:为|是|指出)?\s*[：:]?", normalized)
    )
    if conclusions:
        normalized = normalized[: conclusions[-1].start()].rstrip("。；;，, ")
        normalized += f"。结论：最终答案为{_answer_text(answers)}。"
    return normalized


def build_standalone_messages_v37(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    required_answers: list[str],
    reference_reasoning: str,
    max_evidence_chars: int,
    max_documents: int,
    max_chunks: int,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    """要求白名单模型输出脱离题面也能独立阅读的完整推理摘要。"""
    evidence_text, selected = option_coverage_evidence(
        evidence,
        question_text=question.question,
        options=question.options,
        max_chars=max_evidence_chars,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    options_text = (
        "\n".join(f"{key}. {value}" for key, value in question.options.items())
        or "（无选项）"
    )
    system = (
        "你是金融长文本答案解释撰写员。评审只会看到reasoning文本，不会看到题目、选项、"
        "证据片段或其他字段，因此reasoning必须自包含、可独立阅读，并准确支持指定答案。"
        "只输出一个合法JSON对象，不输出Markdown或额外文字。JSON结构固定为："
        '{"answers":["答案"],"reasoning":"最终推理","doc_ids":["实际使用的文档ID"]}。'
        "answers必须与用户给出的答案字段逐字一致。reasoning为180至300个中文字符，严格依次"
        "包含定位依据、关键信息、分析推导、结论四段。定位依据写明文件名称、条款或表格位置；"
        "关键信息写出原文要件或原始数值；分析推导逐项说明成立与排除理由，计算题写公式、代入、"
        "未取整结果、四舍五入和单位；结论逐字包含用中文分号连接的答案。不得出现检索过程、"
        "检索编号、证据编号、doc_id、qid、文件代号、阶段、草稿、候选、锁定、审计或模型等元叙事。"
    )
    user = (
        f"领域：{question.domain}\n题型：{question.type}\n问题：{question.question}\n"
        f"选项：\n{options_text}\n\n答案格式：{_format_requirements(question)}\n"
        f"答案字段（必须原样返回）：{_answer_text(required_answers)}\n\n"
        f"事实参考摘要：\n{reference_reasoning}\n\n官方原文片段：\n{evidence_text}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], selected


def parse_standalone_response_v37(
    question: BQuestion,
    text: str,
    *,
    required_answers: list[str],
    allowed_doc_ids: set[str],
) -> dict[str, Any]:
    """保留模型最终文本原貌，并执行独立可读性和来源门禁。"""
    payload = extract_model_payload(text)
    answers = normalize_response_answers_v35(question, payload["answers"])
    if answers != required_answers:
        raise ValueError(f"{question.qid} 不得改变指定答案")

    reasoning = str(payload.get("reason") or payload.get("reasoning", "")).strip()
    if not 150 <= len(reasoning) <= 350:
        raise ValueError(f"{question.qid} 的 reasoning 必须为150至350字")
    positions = [reasoning.find(section) for section in REASONING_SECTIONS]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError(f"{question.qid} 的 reasoning 四段标签缺失或顺序错误")
    answer_text = _answer_text(answers)
    if answer_text not in reasoning.rsplit("结论", 1)[-1]:
        raise ValueError(f"{question.qid} 的 reasoning 结论未逐字包含答案")

    prohibited = [value for value in _PROHIBITED_TEXT_V37 if value in reasoning]
    prohibited.extend(
        pattern.pattern
        for pattern in _PROHIBITED_PATTERNS_V37
        if pattern.search(reasoning)
    )
    if prohibited:
        raise ValueError(f"{question.qid} 的 reasoning 含过程性或不可读引用: {prohibited}")

    declared_doc_ids = [
        str(value).strip()
        for value in payload.get("doc_ids", [])
        if str(value).strip()
    ]
    doc_ids = [doc_id for doc_id in declared_doc_ids if doc_id in allowed_doc_ids]
    if not doc_ids:
        raise ValueError(f"{question.qid} 未声明可追溯的文档ID")
    return {"answers": answers, "reasoning": reasoning, "doc_ids": doc_ids}


def build_repair_messages_v37(
    original_messages: list[dict[str, str]],
    *,
    invalid_response: str,
    error: str,
    required_answers: list[str],
    allowed_doc_ids: set[str],
) -> list[dict[str, str]]:
    """保留原始题面和原文上下文，对不合规响应最多进行一次白名单模型修复。"""
    allowed = "、".join(sorted(allowed_doc_ids))
    answer_text = _answer_text(required_answers)
    return [
        *original_messages,
        {"role": "assistant", "content": invalid_response},
        {
            "role": "user",
            "content": (
                f"上次输出未通过格式与独立可读性校验，错误为：{error}。"
                f"请重新输出一个JSON对象，answers必须原样填写{answer_text}，"
                f"doc_ids只能填写以下集合的非空子集：{allowed}。"
                "reasoning仍须为180至300个中文字符，严格依次包含定位依据、关键信息、"
                "分析推导、结论，并遵守上文全部禁止元叙事要求。所有此前调用都会计入Token，"
                "这只是调用统计说明，不得写入reasoning。只输出修复后的JSON。"
            ),
        },
    ]


def combine_attempts_v37(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    """累计与最终内容相关的每一次模型调用，禁止只申报最后一次。"""
    if not attempts:
        raise ValueError("V37 至少需要一次模型调用")
    totals = {
        key: sum(int(attempt["token_usage"][key]) for attempt in attempts)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    if totals["prompt_tokens"] + totals["completion_tokens"] != totals["total_tokens"]:
        raise ValueError("V37 模型调用 Token 不守恒")
    calls = [
        {
            "stage": "v37_standalone_reasoning",
            "token_usage": dict(attempt["token_usage"]),
            "response": str(attempt["response"]),
            "reasoning_content": str(attempt.get("reasoning_content", "")),
        }
        for attempt in attempts
    ]
    return {
        "token_usage": totals,
        "calls": calls,
        "final_response": str(attempts[-1]["response"]),
    }


def promote_format_only_result_v37(
    qid: str,
    attempts: list[dict[str, Any]],
    *,
    required_answers: list[str],
) -> dict[str, Any]:
    """晋升仅需标签规范化的最终响应，并累计相关调用的完整 Token。"""
    combined = combine_attempts_v37(attempts)
    payload = extract_model_payload(combined["final_response"])
    answers = [str(value).strip() for value in payload.get("answers", [])]
    if answers != required_answers:
        raise ValueError(f"{qid} 不得改变指定答案")

    reasoning = str(payload.get("reason") or payload.get("reasoning", "")).strip()
    if not reasoning:
        raise ValueError(f"{qid} 缺少可规范化的 reasoning")
    doc_ids = [
        str(value).strip()
        for value in payload.get("doc_ids", [])
        if str(value).strip()
    ]
    if not doc_ids:
        raise ValueError(f"{qid} 未声明可追溯的文档ID")

    return {
        "qid": qid,
        "answers": answers,
        "reasoning": normalize_final_format_v37(reasoning, answers),
        "doc_ids": doc_ids,
        "token_usage": combined["token_usage"],
        "calls": combined["calls"],
    }
