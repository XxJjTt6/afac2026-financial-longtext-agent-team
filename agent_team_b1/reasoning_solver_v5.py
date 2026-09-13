"""B 榜补充规则下的独立单轮作答与可审计推理摘要。"""

from __future__ import annotations

from typing import Any

from agent.schemas import RetrievalResult
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _evidence_text, _format_requirements, extract_model_payload
from agent_team_b1.submission_v1 import normalize_answers


def build_reasoning_messages(
    question: BQuestion,
    evidence: list[RetrievalResult],
    *,
    max_evidence_chars: int,
) -> list[dict[str, str]]:
    """构建不携带历史候选答案的单轮作答提示。"""
    options = "\n".join(f"{key}. {value}" for key, value in question.options.items()) or "（无选项）"
    system = (
        "你是金融长文档证据推理专家。只能依据用户给出的官方材料证据作答，"
        "不得凭常识补全。先在内部完成定位、提取、逐项判断或计算，再输出一个 JSON 对象。"
        "不要输出 Markdown，不要输出 JSON 之外的文字。JSON 结构固定为："
        '{"answers":["答案"],"reasoning":"可审计的推理摘要","doc_ids":["实际使用的doc_id"]}。'
        "reasoning 必须为80至200个中文字符，说明定位依据、关键数值或条款、"
        "必要的逐项取舍或计算步骤，并明确导出答案；不要仅重复题目或答案。"
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options}\n\n"
        f"答案格式: {_format_requirements(question)}\n\n"
        f"官方材料检索证据:\n{_evidence_text(evidence, max_evidence_chars)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_reasoned_answer(question: BQuestion, text: str) -> dict[str, Any]:
    """解析并校验一次模型响应。"""
    payload = extract_model_payload(text)
    answers = normalize_answers(question, payload["answers"])
    reasoning = str(payload.get("reason") or payload.get("reasoning", "")).strip()
    if len(reasoning) < 20:
        raise ValueError(f"{question.qid} 的 reasoning 少于 20 字")
    if len(reasoning) > 1000:
        raise ValueError(f"{question.qid} 的 reasoning 过长")
    doc_ids = [str(value).strip() for value in payload.get("doc_ids", []) if str(value).strip()]
    if not doc_ids:
        raise ValueError(f"{question.qid} 未声明实际使用的 doc_id")
    return {"answers": answers, "reasoning": reasoning, "doc_ids": doc_ids}
