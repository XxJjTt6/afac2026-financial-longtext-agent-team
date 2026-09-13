"""V33 在 50 万 Token 断点下执行保守的单轮证据复核。"""

from __future__ import annotations

from typing import Any

from agent.schemas import RetrievalResult
from agent_team_b1.clean_reasoning_v10 import REASONING_SECTIONS
from agent_team_b1.option_coverage_v13 import option_coverage_evidence
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements, extract_model_payload
from agent_team_b1.submission_v1 import normalize_answers


def _answer_text(answers: list[str]) -> str:
    return "；".join(str(value) for value in answers)


def build_token_apex_messages_v33(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    candidate_answers: list[str],
    max_evidence_chars: int,
    max_documents: int,
    max_chunks: int,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    """构造候选非真值、证据优先且禁止低置信度改答案的单轮提示。"""
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
        "你是金融长文档证据审计专家。只能依据题面和官方证据窗口作答，不得凭常识补全。"
        "当前候选答案只是待审计结果，不是真值；必须先独立逐项核验，再与候选比较。"
        "只有官方证据直接推翻候选、并能指出具体漏选误选或计算错误时才允许change；"
        "证据不充分或仅有推测时必须keep。多选题逐项检查每个子句及绝对词，"
        "计算题使用未取整原值复算并严格遵守答案格式。"
        "最后只输出一个合法JSON对象，不要输出Markdown或其他文字。JSON结构固定为："
        '{"answers":["答案"],"reasoning":"自包含推理摘要","doc_ids":["doc_id"],'
        '"audit":{"decision":"keep或change","confidence":"high或medium或low",'
        '"change_basis":"候选保留依据或直接推翻候选的页码、数值、条款"}}。'
        "reasoning必须为160至320个中文字符，并依次使用定位依据、关键信息、分析推导、结论四个标签。"
        "选择题要说明正确项成立依据和错误项具体错处；计算题写明原值、公式、代入和取值。"
        "结论必须逐字包含最终answers，doc_ids只能填写实际使用的证据文档。"
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options_text}\n\n"
        f"答案格式: {_format_requirements(question)}\n"
        f"当前候选答案: {_answer_text(candidate_answers)}\n\n"
        f"官方证据窗口:\n{evidence_text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], selected


def parse_token_apex_response_v33(
    question: BQuestion,
    text: str,
    *,
    candidate_answers: list[str],
    allowed_doc_ids: set[str],
) -> dict[str, Any]:
    """解析一次审计响应，并拒绝无直接高置信证据的答案变化。"""
    payload = extract_model_payload(text)
    answers = normalize_answers(question, payload["answers"])
    reasoning = str(payload.get("reason") or payload.get("reasoning", "")).strip()
    if not 150 <= len(reasoning) <= 350:
        raise ValueError(f"{question.qid} 的 reasoning 必须为150至350字")
    positions = [reasoning.find(section) for section in REASONING_SECTIONS]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError(f"{question.qid} 的 reasoning 四段标签缺失或顺序错误")
    conclusion = reasoning.rsplit("结论", 1)[-1]
    if _answer_text(answers) not in conclusion:
        raise ValueError(f"{question.qid} 的 reasoning 结论未逐字包含答案")

    doc_ids = [str(value).strip() for value in payload.get("doc_ids", []) if str(value).strip()]
    if not doc_ids:
        raise ValueError(f"{question.qid} 未声明实际使用的 doc_id")
    disallowed = sorted(set(doc_ids) - allowed_doc_ids)
    if disallowed:
        raise ValueError(f"{question.qid} 声明了窗口外 doc_id: {disallowed}")

    audit = payload.get("audit")
    if not isinstance(audit, dict):
        raise ValueError(f"{question.qid} 缺少 audit 对象")
    decision = str(audit.get("decision", "")).strip().lower()
    confidence = str(audit.get("confidence", "")).strip().lower()
    change_basis = str(audit.get("change_basis", "")).strip()
    changed = answers != candidate_answers
    expected_decision = "change" if changed else "keep"
    if decision != expected_decision:
        raise ValueError(f"{question.qid} 的 audit decision 与答案变化不一致")
    if confidence not in {"high", "medium", "low"}:
        raise ValueError(f"{question.qid} 的 audit confidence 非法")
    if changed and confidence != "high":
        raise ValueError(f"{question.qid} 只有高置信度直接证据才允许改变答案")
    if changed and len(change_basis) < 20:
        raise ValueError(f"{question.qid} 改答案依据不足20字")

    return {
        "answers": answers,
        "reasoning": reasoning,
        "doc_ids": doc_ids,
        "audit": {
            "decision": decision,
            "confidence": confidence,
            "change_basis": change_basis,
        },
        "answer_changed": changed,
    }


def select_token_apex_replacements(
    source_rows: list[dict[str, Any]],
    audited_rows: list[dict[str, Any]],
    *,
    target_total_tokens: int,
    approved_changed_qids: set[str],
) -> dict[str, Any]:
    """选择最小充分节省量，使总 Token 刚好落在断点下方。"""
    if target_total_tokens <= 0:
        raise ValueError("target_total_tokens 必须为正整数")
    source_by_qid = {str(row["qid"]): row for row in source_rows}
    audit_by_qid = {str(row["qid"]): row for row in audited_rows}
    unknown = sorted(approved_changed_qids - set(audit_by_qid))
    if unknown:
        raise KeyError(f"批准的变更 qid 缺少审计结果: {unknown}")

    def tokens(row: dict[str, Any]) -> int:
        return int(row["token_usage"]["total_tokens"])

    selected = set(approved_changed_qids)
    source_total = sum(tokens(row) for row in source_rows)
    mandatory_delta = sum(
        tokens(audit_by_qid[qid]) - tokens(source_by_qid[qid]) for qid in selected
    )
    base_total = source_total + mandatory_delta
    required_savings = max(0, base_total - target_total_tokens)

    optional: list[tuple[str, int]] = []
    for qid, audited in audit_by_qid.items():
        if qid in selected or qid not in source_by_qid:
            continue
        if audited.get("answers") != source_by_qid[qid].get("answers"):
            continue
        saving = tokens(source_by_qid[qid]) - tokens(audited)
        if saving > 0:
            optional.append((qid, saving))

    if required_savings:
        max_saving = max((saving for _, saving in optional), default=0)
        cap = required_savings + max_saving
        reachable = {0}
        parent: dict[int, tuple[int, str]] = {}
        for qid, saving in optional:
            for previous in tuple(reachable):
                current = previous + saving
                if current > cap or current in reachable:
                    continue
                reachable.add(current)
                parent[current] = (previous, qid)
        candidates = [value for value in reachable if value >= required_savings]
        if not candidates:
            raise ValueError("可用同答案审计结果不足以把 Token 降到目标值")
        achieved = min(candidates)
        cursor = achieved
        while cursor:
            cursor, qid = parent[cursor]
            selected.add(qid)

    total = source_total + sum(
        tokens(audit_by_qid[qid]) - tokens(source_by_qid[qid]) for qid in selected
    )
    if total > target_total_tokens:
        raise AssertionError("V33 Token 选择器未跨过目标断点")
    return {
        "selected_qids": sorted(selected),
        "source_total_tokens": source_total,
        "target_total_tokens": target_total_tokens,
        "total_tokens": total,
        "token_headroom": target_total_tokens - total,
    }
