"""V11 基于题面关键词的证据窗口选择与独立作答提示。"""

from __future__ import annotations

import re

import jieba

from agent.schemas import RetrievalResult
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements


_STOPWORDS = {
    "根据",
    "关于",
    "下列",
    "以下",
    "说法",
    "正确",
    "错误",
    "哪些",
    "多少",
    "分别",
    "计算",
    "计算题",
    "保留",
    "答案",
    "格式",
    "报告",
    "报告书",
    "选项",
    "其中",
    "并且",
    "以及",
    "进行",
    "作出",
}


def _focus_tokens(focus_text: str) -> list[str]:
    without_titles = re.sub(r"《[^》]{2,}》", " ", focus_text)
    tokens: set[str] = set()
    for token in jieba.lcut_for_search(without_titles, HMM=False):
        value = token.strip()
        if len(value) >= 2 and value not in _STOPWORDS:
            tokens.add(value)
    tokens.update(
        match.group(0)
        for match in re.finditer(
            r"\d+(?:\.\d+)?%|\d{4}年(?:\d{1,2}月(?:\d{1,2}日)?)?|\d+(?:-\d+)+",
            without_titles,
        )
    )
    return sorted(tokens, key=lambda value: (-len(value), value))


def _focused_excerpt(text: str, *, focus_text: str, max_chars: int) -> str:
    source = text.strip()
    if len(source) <= max_chars:
        return source
    tokens = _focus_tokens(focus_text)
    inner_chars = max(1, max_chars - 2)
    starts = {0, max(0, len(source) - inner_chars)}
    for token in tokens:
        offset = 0
        while True:
            position = source.find(token, offset)
            if position < 0:
                break
            starts.add(max(0, min(position - inner_chars // 3, len(source) - inner_chars)))
            starts.add(max(0, min(position - inner_chars // 2, len(source) - inner_chars)))
            offset = position + max(1, len(token))

    def score(start: int) -> tuple[int, int, int]:
        window = source[start : start + inner_chars]
        relevance = 0
        for token in tokens:
            occurrences = window.count(token)
            if occurrences:
                weight = len(token) ** 2
                if any(character.isdigit() for character in token):
                    weight *= 2
                relevance += occurrences * weight
        boundary_bonus = int(start == 0) + int(start + inner_chars >= len(source))
        return relevance, boundary_bonus, -start

    best_start = max(starts, key=score)
    best_end = min(len(source), best_start + inner_chars)
    if 0 < len(source) - best_end <= min(64, max_chars // 4):
        best_start = max(0, len(source) - inner_chars)
        best_end = len(source)
    prefix = "…" if best_start > 0 else ""
    suffix = "…" if best_end < len(source) else ""
    allowance = max_chars - len(prefix) - len(suffix)
    excerpt = prefix + source[best_start : best_start + allowance] + suffix
    return excerpt[:max_chars]


def _focused_candidates(
    evidence: list[RetrievalResult],
    *,
    max_documents: int,
    max_chunks: int,
) -> list[RetrievalResult]:
    selected: list[RetrievalResult] = []
    selected_ids: set[int] = set()
    selected_docs: set[str] = set()
    for item in evidence:
        if item.doc_id in selected_docs:
            continue
        selected.append(item)
        selected_ids.add(id(item))
        selected_docs.add(item.doc_id)
        if len(selected_docs) >= max_documents or len(selected) >= max_chunks:
            break
    for item in evidence:
        if len(selected) >= max_chunks:
            break
        if item.doc_id not in selected_docs or id(item) in selected_ids:
            continue
        selected.append(item)
        selected_ids.add(id(item))
    return selected


def _header(number: int, item: RetrievalResult) -> str:
    return (
        f"[官方证据{number}] doc_id={item.doc_id}; page={item.metadata.get('page', '')}; "
        f"section={str(item.metadata.get('section', '')).strip()}; score={item.score:.4f}"
    )


def focused_compact_evidence(
    evidence: list[RetrievalResult],
    *,
    focus_text: str,
    max_chars: int,
    max_documents: int = 4,
    max_chunks: int = 8,
) -> tuple[str, list[RetrievalResult]]:
    """对每个证据块保留与题面最相关的窗口，并限制实际文档数。"""
    if max_chars < 256:
        raise ValueError("max_chars 不能小于 256")
    if max_documents < 1 or max_chunks < 1:
        raise ValueError("max_documents 和 max_chunks 必须为正整数")
    if not evidence:
        return "", []
    selected = _focused_candidates(
        evidence,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    while selected:
        headers = [_header(number, item) for number, item in enumerate(selected, start=1)]
        fixed = sum(len(value) for value in headers) + len(selected) + 2 * (len(selected) - 1)
        if fixed + 48 * len(selected) <= max_chars:
            break
        selected.pop()
    if not selected:
        raise ValueError("max_chars 无法容纳证据头信息")

    headers = [_header(number, item) for number, item in enumerate(selected, start=1)]
    fixed = sum(len(value) for value in headers) + len(selected) + 2 * (len(selected) - 1)
    body_budget = max_chars - fixed
    base, remainder = divmod(body_budget, len(selected))
    blocks: list[str] = []
    for index, (header, item) in enumerate(zip(headers, selected, strict=True)):
        allowance = base + int(index < remainder)
        excerpt = _focused_excerpt(
            item.evidence_text,
            focus_text=focus_text,
            max_chars=allowance,
        )
        blocks.append(f"{header}\n{excerpt}")
    rendered = "\n\n".join(blocks)
    if len(rendered) > max_chars:
        raise AssertionError("聚焦证据超出字符预算")
    return rendered, selected


def build_focused_v11_messages(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    max_evidence_chars: int,
    max_documents: int = 4,
    max_chunks: int = 8,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    options = "\n".join(f"{key}. {value}" for key, value in question.options.items()) or "（无选项）"
    focus_text = question.question + "\n" + options
    evidence_text, selected = focused_compact_evidence(
        evidence,
        focus_text=focus_text,
        max_chars=max_evidence_chars,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    system = (
        "你是金融长文档证据推理专家。只能依据用户给出的题面和官方证据作答，"
        "不得凭常识补全，也不得把其他文档的条款张冠李戴。先识别题目指定的文档，"
        "再完成原文定位、数值提取、逐项判断或公式计算。"
        "多选题必须逐项检查A、B、C、D的全部子句；对‘所有’、‘均’、‘仅’、‘一定’等限定词严格按原文判断。"
        "一项中同时出现监管上限与实际计算比例时，两个命题应分别核对，不能相互替代。"
        "最后只输出一个合法 JSON 对象，不要输出 Markdown 或 JSON 之外的文字。"
        "JSON 结构固定为："
        '{"answers":["答案"],"reasoning":"自包含推理摘要","doc_ids":["实际使用的doc_id"]}。'
        "reasoning 必须为160至320个中文字符，并在同一段中依次使用："
        "定位依据：…… 关键信息：…… 分析推导：…… 结论：……。"
        "选择题要说明正确项成立的原文要件以及错误项的具体错处；"
        "计算题要写出原始数值、公式、代入和按题意取值的过程。"
        "摘要必须脱离题目和证据编号仍可理解。"
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options}\n\n"
        f"答案格式: {_format_requirements(question)}\n\n"
        f"官方材料节选:\n{evidence_text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], selected
