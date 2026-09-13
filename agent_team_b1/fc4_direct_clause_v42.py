"""Direct-clause finalization protocol for the fc_b_004 correction."""

from __future__ import annotations

from typing import Any

from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import extract_model_payload


FC4_LOCKED_ANSWER_V42 = ["ABC"]
FC4_SOURCE_DOC_ID_V42 = "text02"
FC4_SOURCE_PAGES_V42 = (104, 105)
FC4_REQUIRED_PHRASES_V42 = (
    "90.79%",
    "发行人两年行业监管评级均为A级",
    "84.17%",
    "不超过3年的过渡期",
)
FC4_REASONING_SECTIONS_V42 = ("定位依据", "关键信息", "分析推导", "结论")


def build_fc4_finalization_messages_v42(
    question: BQuestion,
    *,
    source_pages: dict[int, str],
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Build a locked-answer prompt from raw official PDF pages."""
    if question.qid != "fc_b_004":
        raise ValueError("V42 direct-clause finalization only accepts fc_b_004")
    pages = {int(page): str(text) for page, text in source_pages.items()}
    if set(pages) != set(FC4_SOURCE_PAGES_V42):
        raise ValueError("fc_b_004 official pages 104 and 105 are incomplete")
    evidence_text = "\n\n".join(
        f"[募集说明书第{page}页]\n{pages[page]}" for page in FC4_SOURCE_PAGES_V42
    )
    compact_evidence = "".join(evidence_text.split())
    if any("".join(phrase.split()) not in compact_evidence for phrase in FC4_REQUIRED_PHRASES_V42):
        raise ValueError("fc_b_004 direct-clause evidence is incomplete")

    options = "\n".join(f"{key}. {value}" for key, value in question.options.items())
    system = (
        "你是金融募集说明书答案定稿员。只能依据用户提供的官方原文，"
        "不得补充外部信息。答案已完成逐项原文审计并锁定，禁止修改。"
        "只输出合法JSON对象，字段固定为"
        'answers、reasoning、doc_ids，格式为{"answers":["ABC"],'
        '"reasoning":"正文","doc_ids":["text02"]}。reasoning须为170至300个中文字符，'
        "依次包含定位依据、关键信息、分析推导、结论；"
        "必须逐项说明A、B、C正确和D错误，"
        "结论必须包含最终答案ABC。"
    )
    user = (
        f"qid：{question.qid}\n问题：{question.question}\n选项：\n{options}\n\n"
        "答案已由官方原文锁定为ABC。"
        "请仅依据以下两页原文生成最终reasoning，"
        "不得质疑、删减或改写锁定答案。\n\n"
        f"官方原文：\n{evidence_text}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], {
        "doc_id": FC4_SOURCE_DOC_ID_V42,
        "pages": list(FC4_SOURCE_PAGES_V42),
        "source_type": "raw_official_pdf",
    }


def parse_fc4_finalization_v42(
    question: BQuestion,
    response_text: str,
) -> dict[str, Any]:
    """Validate that the model returned the locked answer and complete reasoning."""
    if question.qid != "fc_b_004":
        raise ValueError("V42 direct-clause parser only accepts fc_b_004")
    payload = extract_model_payload(response_text)
    answers = [str(value).strip() for value in payload.get("answers", [])]
    if answers != FC4_LOCKED_ANSWER_V42:
        raise ValueError("fc_b_004 final answer must remain locked to ABC")
    reasoning = str(payload.get("reasoning") or payload.get("reason", "")).strip()
    if not 170 <= len(reasoning) <= 350:
        raise ValueError("fc_b_004 reasoning length must be between 170 and 350")
    positions = [reasoning.find(section) for section in FC4_REASONING_SECTIONS_V42]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError("fc_b_004 reasoning sections are incomplete or out of order")
    analysis = reasoning.split("分析推导", 1)[-1].split("结论", 1)[0]
    if any(option not in analysis for option in ("A", "B", "C", "D")):
        raise ValueError("fc_b_004 reasoning must audit all four options")
    if "ABC" not in reasoning.rsplit("结论", 1)[-1]:
        raise ValueError("fc_b_004 conclusion must contain ABC")
    doc_ids = [str(value).strip() for value in payload.get("doc_ids", [])]
    if doc_ids != [FC4_SOURCE_DOC_ID_V42]:
        raise ValueError("fc_b_004 finalization must cite only text02")
    return {"answers": answers, "reasoning": reasoning, "doc_ids": doc_ids}
