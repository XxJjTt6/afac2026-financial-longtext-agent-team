"""低 Token 最终确认提示与响应解析。"""

from __future__ import annotations

import json
import re
from typing import Any

from agent_team_b1.questions_v1 import BQuestion


def build_compact_messages(
    question: BQuestion,
    answers: list[str],
    evidence_summary: str,
    *,
    max_summary_chars: int = 1200,
) -> list[dict[str, str]]:
    """只携带题面、建议答案和压缩依据，避免再次发送长证据全文。"""
    candidate = " | ".join(answers)
    options = "；".join(f"{key}.{value}" for key, value in question.options.items()) or "无"
    system = (
        "你是金融题答案的最终低成本核验器。根据题面和压缩依据核验建议答案。"
        "只输出JSON，不展开长推理："
        '{"confirmed":true,"answer":"核验后的完整答案","reason":"不超过40字"}。'
    )
    user = (
        f"qid: {question.qid}\n题型: {question.type}\n问题: {question.question}\n"
        f"选项: {options}\n建议答案: {candidate}\n"
        f"压缩依据: {evidence_summary[:max_summary_chars]}\n"
        "若建议答案与依据一致，原样返回；若不一致，返回修正后的完整答案。"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_compact_verdict(text: str) -> dict[str, Any]:
    """从纯 JSON 或 Markdown 代码块中提取紧凑核验结果。"""
    candidates = [text.strip()]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.I | re.S))
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for match in re.finditer(r"\{", candidate):
            try:
                payload, _ = decoder.raw_decode(candidate[match.start() :])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or "answer" not in payload:
                continue
            return {
                "confirmed": bool(payload.get("confirmed", False)),
                "answer": str(payload.get("answer", "")).strip(),
                "reason": str(payload.get("reason", "")).strip(),
            }
    raise ValueError("紧凑核验响应中没有合法 JSON")
