"""V35 答案锁定的单轮 Qwen reasoning 重生成协议。"""

from __future__ import annotations

import re
from typing import Any

from agent.schemas import RetrievalResult
from agent_team_b1.clean_reasoning_v10 import REASONING_SECTIONS
from agent_team_b1.option_coverage_v13 import option_coverage_evidence
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements, extract_model_payload
from agent_team_b1.submission_v1 import normalize_answers


def _answer_text(answers: list[str]) -> str:
    return "；".join(str(value) for value in answers)


def normalize_reasoning_conclusion_v35(
    reasoning: str,
    answers: list[str],
) -> str:
    """仅规范结论中的答案连接符，避免 A、B 与 AB 的表示差异。"""
    normalized = str(reasoning).strip()
    answer_text = _answer_text(answers)
    if "结论" not in normalized or answer_text in normalized.rsplit("结论", 1)[-1]:
        return normalized
    prefix = normalized.rsplit("结论", 1)[0]
    return f"{prefix}结论：最终答案为{answer_text}。"


def normalize_response_answers_v35(
    question: BQuestion,
    raw_answers: list[object],
) -> list[str]:
    """兼容模型把多个自由答案字段合并到一个分号字符串中的表示。"""
    values = [str(value).strip() for value in raw_answers if value is not None]
    if (
        question.answer_kind == "freeform"
        and question.expected_answers > 1
        and len(values) == 1
    ):
        split_values = [value.strip() for value in re.split(r"[；;]", values[0])]
        if len(split_values) == question.expected_answers and all(split_values):
            values = split_values
    return normalize_answers(question, values)


def build_provenance_messages_v35(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    locked_answers: list[str],
    audited_reasoning: str,
    max_evidence_chars: int,
    max_documents: int,
    max_chunks: int,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    """提供已审计草稿和证据，只让模型重写与锁定答案一致的 reasoning。"""
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
        "你是金融长文档答案解释编辑。答案已经由原文审计和确定性复算锁定，"
        "答案已锁定，禁止修改，也不得增删任何选项或答案字段。你的唯一任务是结合题面、"
        "已审计推理草稿和官方证据，把推理改写成自包含、可核验且与锁定答案严格一致的版本。"
        "证据窗口不足时以已审计草稿中的事实为准，不得反向质疑或修改锁定答案。"
        "只输出一个合法JSON对象，不输出Markdown。JSON结构固定为："
        '{"answers":["与锁定答案逐字相同"],"reasoning":"推理正文",'
        '"doc_ids":["实际使用的doc_id"]}。'
        "reasoning必须为170至300个中文字符，并严格依次包含定位依据、关键信息、分析推导、"
        "结论四个标签。选择题逐项说明成立依据和错误项错处；计算题写出原值、公式、代入、"
        "取值及单位处理。结论必须逐字包含用中文分号连接的锁定答案。"
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options_text}\n\n"
        f"答案格式: {_format_requirements(question)}\n"
        f"锁定答案: {_answer_text(locked_answers)}\n\n"
        f"已审计推理草稿:\n{audited_reasoning}\n\n"
        f"官方证据窗口:\n{evidence_text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], selected


def parse_provenance_response_v35(
    question: BQuestion,
    text: str,
    *,
    locked_answers: list[str],
    allowed_doc_ids: set[str],
) -> dict[str, Any]:
    """解析模型原始响应，并保证最终内容可从这一次调用完整追溯。"""
    payload = extract_model_payload(text)
    answers = normalize_response_answers_v35(question, payload["answers"])
    if answers != locked_answers:
        raise ValueError(f"{question.qid} 不得改变锁定答案")

    reasoning = normalize_reasoning_conclusion_v35(
        str(payload.get("reason") or payload.get("reasoning", "")),
        answers,
    )
    if not 150 <= len(reasoning) <= 350:
        raise ValueError(f"{question.qid} 的 reasoning 必须为150至350字")
    positions = [reasoning.find(section) for section in REASONING_SECTIONS]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError(f"{question.qid} 的 reasoning 四段标签缺失或顺序错误")
    if _answer_text(answers) not in reasoning.rsplit("结论", 1)[-1]:
        raise ValueError(f"{question.qid} 的 reasoning 结论未逐字包含锁定答案")

    doc_ids = [
        str(value).strip()
        for value in payload.get("doc_ids", [])
        if str(value).strip()
    ]
    doc_ids = [doc_id for doc_id in doc_ids if doc_id in allowed_doc_ids]
    if not doc_ids:
        raise ValueError(f"{question.qid} 未声明实际使用的 doc_id")

    return {
        "answers": answers,
        "reasoning": reasoning,
        "doc_ids": doc_ids,
    }
