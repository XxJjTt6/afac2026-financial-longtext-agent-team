"""B 榜补充规则下的独立单轮作答、紧凑证据与原始 usage 审计。"""

from __future__ import annotations

from typing import Any

from agent.schemas import RetrievalResult, TokenUsage
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements, extract_model_payload
from agent_team_b1.submission_v1 import normalize_answers


REASONING_SECTIONS = ("定位依据", "关键信息", "分析推导", "结论")


def official_token_efficiency_score(total_tokens: int) -> float:
    """按天池 B 榜补充说明的分段公式计算 Token 效率分。"""
    if total_tokens <= 0 or total_tokens > 5_000_000:
        return 0.0
    if total_tokens < 500_000:
        return total_tokens / 500_000 * 100
    return (5_000_000 - total_tokens) / 5_000_000 * 100


def _evidence_header(number: int, item: RetrievalResult) -> str:
    page = item.metadata.get("page", "")
    section = str(item.metadata.get("section", "")).strip()
    return (
        f"[官方证据{number}] doc_id={item.doc_id}; page={page}; "
        f"section={section}; score={item.score:.4f}"
    )


def _diverse_candidates(
    evidence: list[RetrievalResult],
    *,
    max_documents: int,
    max_chunks: int,
) -> list[RetrievalResult]:
    """先为高排名文档保留一条证据，再按原排名填充其余证据。"""
    selected: list[RetrievalResult] = []
    selected_ids: set[int] = set()
    seen_docs: set[str] = set()
    for item in evidence:
        if item.doc_id in seen_docs:
            continue
        selected.append(item)
        selected_ids.add(id(item))
        seen_docs.add(item.doc_id)
        if len(seen_docs) >= max_documents or len(selected) >= max_chunks:
            break
    for item in evidence:
        if len(selected) >= max_chunks:
            break
        if id(item) in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(id(item))
    return selected


def compact_evidence_text(
    evidence: list[RetrievalResult],
    *,
    max_chars: int,
    max_documents: int = 6,
    max_chunks: int = 8,
) -> tuple[str, list[RetrievalResult]]:
    """在硬字符预算内均衡保留多文档证据，避免单个长块吃完预算。"""
    if max_chars < 256:
        raise ValueError("max_chars 不能小于 256")
    if max_documents < 1 or max_chunks < 1:
        raise ValueError("max_documents 和 max_chunks 必须为正整数")
    if not evidence:
        return "", []

    selected = _diverse_candidates(
        evidence,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    while selected:
        headers = [_evidence_header(number, item) for number, item in enumerate(selected, start=1)]
        fixed_chars = (
            sum(len(header) for header in headers)
            + len(selected)
            + 2 * (len(selected) - 1)
        )
        if fixed_chars + 32 * len(selected) <= max_chars:
            break
        selected.pop()
    if not selected:
        raise ValueError("max_chars 无法容纳证据头信息")

    headers = [_evidence_header(number, item) for number, item in enumerate(selected, start=1)]
    fixed_chars = (
        sum(len(header) for header in headers)
        + len(selected)
        + 2 * (len(selected) - 1)
    )
    body_budget = max_chars - fixed_chars
    base, remainder = divmod(body_budget, len(selected))
    blocks: list[str] = []
    for index, (header, item) in enumerate(zip(headers, selected, strict=True)):
        allowance = base + int(index < remainder)
        body = item.evidence_text.strip()
        if len(body) > allowance:
            body = body[: max(0, allowance - 1)].rstrip() + "…"
        blocks.append(f"{header}\n{body}")
    rendered = "\n\n".join(blocks)
    if len(rendered) > max_chars:
        raise AssertionError("紧凑证据超出字符预算")
    return rendered, selected


def build_clean_v10_messages(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    max_evidence_chars: int,
    max_documents: int = 6,
    max_chunks: int = 8,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    """仅使用题面和当前官方证据生成答案，不引入历史候选或推理底稿。"""
    evidence_text, selected = compact_evidence_text(
        evidence,
        max_chars=max_evidence_chars,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    options = "\n".join(f"{key}. {value}" for key, value in question.options.items()) or "（无选项）"
    system = (
        "你是金融长文档证据推理专家。只能依据用户给出的题面和官方证据作答，"
        "不得凭常识补全。先在内部完成文档定位、原文提取、逐项判断或公式计算，"
        "最后只输出一个合法 JSON 对象，不要输出 Markdown 或 JSON 之外的文字。"
        "JSON 结构固定为："
        '{"answers":["答案"],"reasoning":"自包含推理摘要","doc_ids":["实际使用的doc_id"]}。'
        "reasoning 必须为160至320个中文字符，并在同一段中依次使用四个标签："
        "定位依据：…… 关键信息：…… 分析推导：…… 结论：……。"
        "选择题要逐项比对A、B、C、D，说明正确项成立的原文要件以及错误项的具体错处；"
        "计算题要写出原始数值、公式、代入和按题意取值的过程。"
        "摘要必须脱离题目和证据编号仍可理解，不得只写‘证据1’、‘依据材料’或重复最终答案。"
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options}\n\n"
        f"答案格式: {_format_requirements(question)}\n\n"
        f"官方材料节选:\n{evidence_text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], selected


def parse_clean_v10_response(question: BQuestion, text: str) -> dict[str, Any]:
    """解析模型响应，并将官方推理评分要求转为硬门禁。"""
    payload = extract_model_payload(text)
    answers = normalize_answers(question, payload["answers"])
    reasoning = str(payload.get("reason") or payload.get("reasoning", "")).strip()
    if len(reasoning) < 120:
        raise ValueError(f"{question.qid} 的 reasoning 少于 120 字")
    if len(reasoning) > 800:
        raise ValueError(f"{question.qid} 的 reasoning 过长")
    positions = [reasoning.find(section) for section in REASONING_SECTIONS]
    missing = [section for section, position in zip(REASONING_SECTIONS, positions, strict=True) if position < 0]
    if missing:
        raise ValueError(f"{question.qid} 的 reasoning 缺少结构段: {missing}")
    if positions != sorted(positions):
        raise ValueError(f"{question.qid} 的 reasoning 结构段顺序错误")
    doc_ids = [str(value).strip() for value in payload.get("doc_ids", []) if str(value).strip()]
    if not doc_ids:
        raise ValueError(f"{question.qid} 未声明实际使用的 doc_id")
    return {"answers": answers, "reasoning": reasoning, "doc_ids": doc_ids}


def require_official_usage(raw_response: dict[str, Any] | None) -> TokenUsage:
    """只接受百炼 API 原始响应的 usage，不允许本地估算替代。"""
    raw_usage = (raw_response or {}).get("usage")
    if not isinstance(raw_usage, dict):
        raise ValueError("模型 API 未返回原始 usage")
    try:
        prompt_tokens = int(raw_usage["prompt_tokens"])
        completion_tokens = int(raw_usage["completion_tokens"])
        total_tokens = int(raw_usage["total_tokens"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("模型 API 原始 usage 字段不完整") from exc
    if prompt_tokens <= 0 or completion_tokens <= 0 or total_tokens <= 0:
        raise ValueError("模型 API 原始 usage 必须为正整数")
    if total_tokens != prompt_tokens + completion_tokens:
        raise ValueError("模型 API 原始 usage Token 不守恒")
    return TokenUsage(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
    )
