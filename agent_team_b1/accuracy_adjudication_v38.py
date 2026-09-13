"""V38 使用完整选项证据进行正确率优先的 Qwen 裁决。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from agent.schemas import RetrievalResult
from agent_team_b1.accuracy_frontier_v38 import (
    DIRECT_BASIS_TYPES_V38,
    promote_accuracy_change_v38,
)
from agent_team_b1.focused_reasoning_v11 import _focused_excerpt
from agent_team_b1.option_coverage_v13 import _lexical_score
from agent_team_b1.provenance_reasoning_v35 import normalize_response_answers_v35
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements


_DECISIONS_V38 = {"keep", "change"}
_CONFIDENCE_V38 = {"high", "medium", "low"}
_VERDICTS_V38 = {"support", "refute", "insufficient"}
_BASIS_TYPES_V38 = {*DIRECT_BASIS_TYPES_V38, "insufficient"}
_REASONING_SECTIONS_V38 = ("定位依据", "关键信息", "分析推导", "结论")


def _answer_text(answers: list[str]) -> str:
    return "；".join(str(value) for value in answers)


def _complete_option_evidence_v38(
    evidence: list[RetrievalResult],
    *,
    question_text: str,
    options: dict[str, str],
    max_chars: int,
    max_documents: int,
    max_chunks: int,
) -> tuple[str, list[RetrievalResult]]:
    """每个证据块只使用一次，并在选项覆盖后补齐文档覆盖。"""
    if max_chars < 256 or max_documents < 1 or max_chunks < 1:
        raise ValueError("V38 证据预算和数量限制必须为正")
    allowed_docs: list[str] = []
    for item in evidence:
        if item.doc_id not in allowed_docs:
            allowed_docs.append(item.doc_id)
        if len(allowed_docs) >= max_documents:
            break
    allowed = set(allowed_docs)
    unique_pool: list[RetrievalResult] = []
    seen_chunks: set[str] = set()
    for item in evidence:
        if item.doc_id not in allowed or item.chunk_id in seen_chunks:
            continue
        unique_pool.append(item)
        seen_chunks.add(item.chunk_id)
    if not unique_pool:
        return "", []

    units = [f"选项{key}：{value}" for key, value in options.items()]
    units.append(question_text)
    selected: list[tuple[RetrievalResult, str]] = []
    used: set[str] = set()
    for unit in units:
        candidates = [item for item in unique_pool if item.chunk_id not in used]
        if not candidates or len(selected) >= max_chunks:
            break
        best = max(
            enumerate(candidates),
            key=lambda pair: (
                _lexical_score(pair[1].evidence_text, unit),
                pair[1].score,
                -pair[0],
            ),
        )[1]
        selected.append((best, unit))
        used.add(best.chunk_id)

    global_focus = question_text + "\n" + "\n".join(options.values())
    represented = {item.doc_id for item, _ in selected}
    for doc_id in allowed_docs:
        if len(selected) >= max_chunks or doc_id in represented:
            continue
        candidate = next(
            (
                item
                for item in unique_pool
                if item.doc_id == doc_id and item.chunk_id not in used
            ),
            None,
        )
        if candidate is None:
            continue
        selected.append((candidate, global_focus))
        used.add(candidate.chunk_id)
        represented.add(doc_id)

    for item in unique_pool:
        if len(selected) >= max_chunks:
            break
        if item.chunk_id in used:
            continue
        selected.append((item, global_focus))
        used.add(item.chunk_id)

    while selected:
        headers = [
            (
                f"[官方证据窗口{number}] doc_id={item.doc_id}; "
                f"page={item.metadata.get('page', '')}; "
                f"section={str(item.metadata.get('section', '')).strip()}; "
                f"score={item.score:.4f}"
            )
            for number, (item, _) in enumerate(selected, start=1)
        ]
        fixed = sum(len(value) for value in headers) + len(selected) + 2 * (
            len(selected) - 1
        )
        if fixed + 48 * len(selected) <= max_chars:
            break
        selected.pop()
    if not selected:
        raise ValueError("V38 证据预算无法容纳窗口头信息")

    headers = [
        (
            f"[官方证据窗口{number}] doc_id={item.doc_id}; "
            f"page={item.metadata.get('page', '')}; "
            f"section={str(item.metadata.get('section', '')).strip()}; "
            f"score={item.score:.4f}"
        )
        for number, (item, _) in enumerate(selected, start=1)
    ]
    fixed = sum(len(value) for value in headers) + len(selected) + 2 * (
        len(selected) - 1
    )
    body_budget = max_chars - fixed
    base, remainder = divmod(body_budget, len(selected))
    blocks: list[str] = []
    for index, (header, (item, focus)) in enumerate(
        zip(headers, selected, strict=True)
    ):
        excerpt = _focused_excerpt(
            item.evidence_text,
            focus_text=focus,
            max_chars=base + int(index < remainder),
        )
        blocks.append(f"{header}\n{excerpt}")
    return "\n\n".join(blocks), [item for item, _ in selected]


def _extract_accuracy_payload_v38(text: str) -> dict[str, Any]:
    """提取裁决 JSON，同时保留枚举型 confidence 等扩展字段。"""
    candidates = [str(text).strip()]
    candidates.extend(
        re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", str(text), flags=re.I | re.S)
    )
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for match in re.finditer(r"\{", candidate):
            try:
                payload, _ = decoder.raw_decode(candidate[match.start() :])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
    raise ValueError("模型响应中没有可解析的裁决 JSON 对象")


def build_accuracy_messages_v38(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    current_answers: list[str],
    max_evidence_chars: int,
    max_documents: int,
    max_chunks: int,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    """构造逐选项、开放世界且可审计的准确率裁决提示。"""
    evidence_text, selected = _complete_option_evidence_v38(
        evidence,
        question_text=question.question,
        options=question.options,
        max_chars=max_evidence_chars,
        max_documents=max_documents,
        max_chunks=max_chunks,
    )
    options_text = (
        "\n".join(f"{key}. {value}" for key, value in question.options.items())
        or "（无选项，必须按计算题要求复算）"
    )
    option_schema = ",".join(
        f'"{key}":{{"verdict":"support|refute|insufficient","basis":"原文或计算"}}'
        for key in question.options
    )
    json_schema = (
        '{"answers":["答案"],"decision":"keep|change",'
        '"confidence":"high|medium|low","basis_type":"direct_clause",'
        f'"option_audit":{{{option_schema}}},"calculation":{{}},'
        '"reasoning":"定位依据：...关键信息：...分析推导：...结论：最终答案为...。",'
        '"doc_ids":["实际使用的文档ID"]}'
    )
    system = (
        "你是金融长文本答案正确率裁决员，只依据用户提供的官方原文。"
        "必须逐项判断所有选项；未检索到不能视为错误，不能用证据缺失排除选项。"
        "若任何影响答案的选项仍证据不足，decision必须为keep且answers保持当前答案。"
        "只有原文直接支持入选项、直接反驳未入选项，或确定性计算完整闭环时才允许change。"
        "计算题必须写出原始数值、公式、未取整结果、四舍五入规则和单位。"
        "只输出合法JSON，不输出Markdown。字段固定为answers、decision、confidence、"
        "basis_type、option_audit、calculation、reasoning、doc_ids。"
        "decision只能为keep或change；confidence只能为high、medium或low；"
        "basis_type只能为direct_clause、direct_table、deterministic_calculation、"
        "multi_document_entailment或insufficient。option_audit必须覆盖每个选项，"
        "每项包含verdict和basis，verdict只能为support、refute或insufficient。"
        f"严格使用对象结构，不得把option_audit写成数组。JSON示例：{json_schema}。"
        "非计算题calculation必须为{}，不得填写空字符串；计算题则填写raw_values、"
        "formula、unrounded、rounding和unit。"
        "reasoning须依次包含定位依据、关键信息、分析推导、结论并自包含。"
    )
    user = (
        f"qid：{question.qid}\n领域：{question.domain}\n题型：{question.type}\n"
        f"问题：{question.question}\n选项：\n{options_text}\n\n"
        f"答案格式：{_format_requirements(question)}\n"
        f"当前答案：{_answer_text(current_answers)}\n\n"
        "请把当前答案仅视为待审候选，不得因模型偏好修改。若change，必须用完整正反证据闭环；"
        "若keep，answers必须逐字返回当前答案。\n\n"
        f"官方原文证据：\n{evidence_text}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], selected


def parse_accuracy_response_v38(
    question: BQuestion,
    text: str,
    *,
    current_answers: list[str],
    allowed_doc_ids: set[str],
) -> dict[str, Any]:
    """解析裁决并拒绝由证据缺失驱动的答案变化。"""
    payload = _extract_accuracy_payload_v38(text)
    answers = normalize_response_answers_v35(question, payload.get("answers", []))
    current = [str(value).strip() for value in current_answers]
    decision = str(payload.get("decision", "")).strip().lower()
    confidence = str(payload.get("confidence", "")).strip().lower()
    basis_type = str(payload.get("basis_type", "")).strip().lower()
    if decision not in _DECISIONS_V38:
        raise ValueError(f"{question.qid} 的 decision 非法")
    if confidence not in _CONFIDENCE_V38:
        raise ValueError(f"{question.qid} 的 confidence 非法")
    if basis_type not in _BASIS_TYPES_V38:
        raise ValueError(f"{question.qid} 的 basis_type 非法")
    if decision == "keep" and answers != current:
        raise ValueError(f"{question.qid} keep 时不得改变答案")
    if decision == "change" and answers == current:
        raise ValueError(f"{question.qid} change 时答案必须发生变化")

    raw_audits = payload.get("option_audit", {})
    if isinstance(raw_audits, list) and len(raw_audits) == len(question.options):
        raw_audits = dict(zip(question.options, raw_audits, strict=True))
    if raw_audits == [] and not question.options:
        raw_audits = {}
    if not isinstance(raw_audits, dict):
        raise ValueError(f"{question.qid} 缺少 option_audit")
    option_audit: dict[str, dict[str, str]] = {}
    expected_keys = set(question.options)
    if expected_keys and set(raw_audits) != expected_keys:
        raise ValueError(f"{question.qid} 的 option_audit 未逐项覆盖所有选项")
    for key, raw in raw_audits.items():
        if not isinstance(raw, dict):
            raise ValueError(f"{question.qid} 的 {key} 裁决结构非法")
        verdict = str(raw.get("verdict", "")).strip().lower()
        basis = str(raw.get("basis", "")).strip()
        if verdict not in _VERDICTS_V38 or not basis:
            raise ValueError(f"{question.qid} 的 {key} 裁决不完整")
        option_audit[str(key)] = {"verdict": verdict, "basis": basis}
    if decision == "change" and any(
        item["verdict"] == "insufficient" for item in option_audit.values()
    ):
        raise ValueError(f"{question.qid} 不得基于证据不足改变答案")

    calculation = payload.get("calculation", {})
    if calculation in ("", None):
        calculation = {}
    if not isinstance(calculation, dict):
        raise ValueError(f"{question.qid} 的 calculation 必须为对象")
    reasoning = str(payload.get("reason") or payload.get("reasoning", "")).strip()
    if not 120 <= len(reasoning) <= 650:
        raise ValueError(f"{question.qid} 的 reasoning 长度不合规")
    positions = [reasoning.find(section) for section in _REASONING_SECTIONS_V38]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError(f"{question.qid} 的 reasoning 四段缺失或顺序错误")
    if _answer_text(answers) not in reasoning.rsplit("结论", 1)[-1]:
        raise ValueError(f"{question.qid} 的结论未包含最终答案")

    declared = [
        str(value).strip()
        for value in payload.get("doc_ids", [])
        if str(value).strip()
    ]
    outside = sorted(set(declared) - set(allowed_doc_ids))
    if outside:
        raise ValueError(f"{question.qid} 声明了窗口外 doc_id: {outside}")
    if not declared:
        raise ValueError(f"{question.qid} 未声明实际使用的 doc_id")

    return {
        "answers": answers,
        "decision": decision,
        "confidence": confidence,
        "basis_type": basis_type,
        "option_audit": option_audit,
        "calculation": calculation,
        "reasoning": reasoning,
        "doc_ids": declared,
    }


def parse_recovered_keep_v38(
    question: BQuestion,
    text: str,
    *,
    current_answers: list[str],
    allowed_doc_ids: set[str],
) -> dict[str, Any]:
    """历史 keep 日志可保留声明文档，但答案变更仍执行严格窗口门禁。"""
    try:
        return parse_accuracy_response_v38(
            question,
            text,
            current_answers=current_answers,
            allowed_doc_ids=allowed_doc_ids,
        )
    except ValueError as exc:
        if "窗口外 doc_id" not in str(exc):
            raise
        original_error = exc
    payload = _extract_accuracy_payload_v38(text)
    declared = {
        str(value).strip()
        for value in payload.get("doc_ids", [])
        if str(value).strip()
    }
    parsed = parse_accuracy_response_v38(
        question,
        text,
        current_answers=current_answers,
        allowed_doc_ids=set(allowed_doc_ids) | declared,
    )
    if parsed["decision"] != "keep":
        raise original_error
    return parsed


def build_accuracy_verifier_messages_v38(
    original_messages: list[dict[str, str]],
    *,
    primary_response: str,
    current_answers: list[str],
) -> list[dict[str, str]]:
    """在相同原文上要求第二次独立复核变更。"""
    return [
        *original_messages,
        {"role": "assistant", "content": primary_response},
        {
            "role": "user",
            "content": (
                "请独立复核上一个裁决，不得默认接受其答案。重新逐项检查原文的正向支持和明确反证；"
                "不能因为当前证据没有出现某项就判定该项错误。"
                f"原候选答案为{_answer_text(current_answers)}。"
                "若无法完整证明变化，必须keep原候选答案。仍按完全相同JSON结构输出。"
            ),
        },
    ]


def combine_accuracy_attempts_v38(
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    """累计所有参与最终裁决的主审、修复和复核调用。"""
    if not attempts:
        raise ValueError("V38 至少需要一次模型调用")
    totals = {
        key: sum(int(attempt["token_usage"][key]) for attempt in attempts)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    if totals["prompt_tokens"] + totals["completion_tokens"] != totals["total_tokens"]:
        raise ValueError("V38 模型调用 Token 不守恒")
    calls = [
        {
            "stage": str(attempt.get("stage", "primary")),
            "token_usage": dict(attempt["token_usage"]),
            "response": str(attempt["response"]),
            "reasoning_content": str(attempt.get("reasoning_content", "")),
        }
        for attempt in attempts
    ]
    return {"token_usage": totals, "calls": calls}


def primary_verifier_agree_v38(
    primary: dict[str, Any], verifier: dict[str, Any]
) -> bool:
    """答案变更只在两次高置信裁决的决定与答案完全一致时晋升。"""
    return (
        primary.get("decision") == verifier.get("decision")
        and list(primary.get("answers", [])) == list(verifier.get("answers", []))
        and primary.get("confidence") == "high"
        and verifier.get("confidence") == "high"
    )


def build_accuracy_row_v38(
    *,
    qid: str,
    current_answers: list[str],
    option_keys: tuple[str, ...],
    primary: dict[str, Any],
    verifier: dict[str, Any] | None,
    attempts: list[dict[str, Any]],
) -> dict[str, Any]:
    """把主审与复核结果合成一行，并在门禁失败时保留当前答案。"""
    agrees = verifier is not None and primary_verifier_agree_v38(primary, verifier)
    primary_passes = promote_accuracy_change_v38(
        primary,
        current_answers=current_answers,
        option_keys=option_keys,
    )
    verifier_passes = verifier is not None and promote_accuracy_change_v38(
        verifier,
        current_answers=current_answers,
        option_keys=option_keys,
    )
    promoted = bool(agrees and primary_passes and verifier_passes)
    final = verifier if promoted and verifier is not None else primary
    combined = combine_accuracy_attempts_v38(attempts)
    return {
        "qid": qid,
        "current_answers": list(current_answers),
        "proposed_answers": list(final.get("answers", [])),
        "answers": (
            list(final.get("answers", [])) if promoted else list(current_answers)
        ),
        "decision": str(final.get("decision", "")),
        "confidence": str(final.get("confidence", "")),
        "basis_type": str(final.get("basis_type", "")),
        "option_audit": final.get("option_audit", {}),
        "calculation": final.get("calculation", {}),
        "reasoning": str(final.get("reasoning", "")),
        "doc_ids": list(final.get("doc_ids", [])),
        "promoted": promoted,
        "primary_verifier_agree": bool(agrees),
        "token_usage": combined["token_usage"],
        "calls": combined["calls"],
    }


def verify_accuracy_run_v38(run_dir: Path) -> dict[str, int]:
    """独立复核运行目录中每道题的调用守恒与双审一致性。"""
    rows_path = Path(run_dir) / "answer_results.jsonl"
    rows = [
        json.loads(line)
        for line in rows_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    total_tokens = 0
    promoted = 0
    for row in rows:
        calls = row.get("calls", [])
        summed = combine_accuracy_attempts_v38(calls)["token_usage"]
        if summed != row.get("token_usage"):
            raise ValueError(f"{row.get('qid')} 的调用 usage 不守恒")
        total_tokens += int(summed["total_tokens"])
        if row.get("promoted"):
            promoted += 1
            if not row.get("primary_verifier_agree"):
                raise ValueError(f"{row.get('qid')} 晋升但双审不一致")
    return {
        "question_count": len(rows),
        "promoted_count": promoted,
        "total_tokens": total_tokens,
    }


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="验证 V38 正确率裁决运行目录。")
    parser.add_argument("--verify-run", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify_accuracy_run_v38(args.verify_run), ensure_ascii=False))


if __name__ == "__main__":
    _main()
