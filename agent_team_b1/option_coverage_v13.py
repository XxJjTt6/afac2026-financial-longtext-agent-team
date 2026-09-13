"""V13 通过选项级词法覆盖，为每个候选命题保留专属证据窗口。"""

from __future__ import annotations

from agent.schemas import RetrievalResult
from agent_team_b1.focused_reasoning_v11 import _focus_tokens, _focused_excerpt
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements


def _lexical_score(text: str, focus_text: str) -> int:
    tokens = _focus_tokens(focus_text)
    score = 0
    for token in tokens:
        occurrences = min(2, text.count(token))
        if not occurrences:
            continue
        weight = len(token) ** 2
        if any(character.isdigit() for character in token):
            weight *= 2
        score += occurrences * weight
    return score


def _allowed_documents(evidence: list[RetrievalResult], limit: int) -> set[str]:
    documents: list[str] = []
    for item in evidence:
        if item.doc_id not in documents:
            documents.append(item.doc_id)
        if len(documents) >= limit:
            break
    return set(documents)


def _coverage_windows(
    evidence: list[RetrievalResult],
    *,
    question_text: str,
    options: dict[str, str],
    max_documents: int,
    max_chunks: int,
) -> list[tuple[RetrievalResult, str]]:
    allowed = _allowed_documents(evidence, max_documents)
    pool = [item for item in evidence if item.doc_id in allowed]
    if not pool:
        return []
    units = [f"选项{key}：{value}" for key, value in options.items()]
    if not units:
        units = [question_text]
    elif len(units) < max_chunks:
        units.append(question_text)

    selected: list[tuple[RetrievalResult, str]] = []
    for unit in units:
        if len(selected) >= max_chunks:
            break
        best = max(
            enumerate(pool),
            key=lambda pair: (_lexical_score(pair[1].evidence_text, unit), -pair[0]),
        )[1]
        selected.append((best, unit))

    used_chunk_ids = {item.chunk_id for item, _ in selected}
    global_focus = question_text + "\n" + "\n".join(options.values())
    for item in pool:
        if len(selected) >= max_chunks:
            break
        if item.chunk_id in used_chunk_ids:
            continue
        selected.append((item, global_focus))
        used_chunk_ids.add(item.chunk_id)
    return selected


def _header(number: int, item: RetrievalResult) -> str:
    return (
        f"[官方证据窗口{number}] doc_id={item.doc_id}; page={item.metadata.get('page', '')}; "
        f"section={str(item.metadata.get('section', '')).strip()}; score={item.score:.4f}"
    )


def option_coverage_evidence(
    evidence: list[RetrievalResult],
    *,
    question_text: str,
    options: dict[str, str],
    max_chars: int,
    max_documents: int = 4,
    max_chunks: int = 8,
) -> tuple[str, list[RetrievalResult]]:
    """按选项选取最相关证据窗口，低排名但直接命中的条款不再被截断。"""
    if max_chars < 256:
        raise ValueError("max_chars 不能小于 256")
    if max_documents < 1 or max_chunks < 1:
        raise ValueError("max_documents 和 max_chunks 必须为正整数")
    if not evidence:
        return "", []
    windows = _coverage_windows(
        evidence,
        question_text=question_text,
        options=options,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    while windows:
        headers = [_header(number, item) for number, (item, _) in enumerate(windows, start=1)]
        fixed = sum(len(value) for value in headers) + len(windows) + 2 * (len(windows) - 1)
        if fixed + 48 * len(windows) <= max_chars:
            break
        windows.pop()
    if not windows:
        raise ValueError("max_chars 无法容纳选项证据头信息")

    headers = [_header(number, item) for number, (item, _) in enumerate(windows, start=1)]
    fixed = sum(len(value) for value in headers) + len(windows) + 2 * (len(windows) - 1)
    body_budget = max_chars - fixed
    base, remainder = divmod(body_budget, len(windows))
    blocks: list[str] = []
    for index, (header, (item, focus)) in enumerate(zip(headers, windows, strict=True)):
        allowance = base + int(index < remainder)
        excerpt = _focused_excerpt(
            item.evidence_text,
            focus_text=focus,
            max_chars=allowance,
        )
        blocks.append(f"{header}\n{excerpt}")
    rendered = "\n\n".join(blocks)
    if len(rendered) > max_chars:
        raise AssertionError("选项覆盖证据超出字符预算")
    return rendered, [item for item, _ in windows]


def build_option_coverage_v13_messages(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    max_evidence_chars: int,
    max_documents: int = 4,
    max_chunks: int = 8,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    options_text = "\n".join(f"{key}. {value}" for key, value in question.options.items()) or "（无选项）"
    evidence_text, selected = option_coverage_evidence(
        evidence,
        question_text=question.question,
        options=question.options,
        max_chars=max_evidence_chars,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    system = (
        "你是金融长文档证据推理专家。只能依据题面和官方证据窗口作答，"
        "不得凭常识补全，也不得将不同文档的条款混用。"
        "证据窗口是按题面和各选项分别检索的，编号不对应选项序号；"
        "必须核对文档标题、条款主体和适用范围后再使用。"
        "多选题必须逐项检查A、B、C、D的每个子句；对‘所有’、‘均’、‘仅’、‘一定’严格按原文判断。"
        "若题目问‘错误的是’，answers必须填错误项；若问‘正确的是’，answers必须填正确项。"
        "最后只输出一个合法 JSON 对象，不要输出 Markdown 或其他文字。JSON 结构为："
        '{"answers":["答案"],"reasoning":"自包含推理摘要","doc_ids":["实际使用的doc_id"]}。'
        "reasoning 必须为160至320个中文字符，依次使用："
        "定位依据：…… 关键信息：…… 分析推导：…… 结论：……。"
        "选择题要写出每个选项的判断；计算题要写出原始数值、公式、代入和取值过程。"
        "摘要必须脱离题目和证据编号仍可理解。"
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options_text}\n\n"
        f"答案格式: {_format_requirements(question)}\n\n"
        f"官方证据窗口:\n{evidence_text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], selected
