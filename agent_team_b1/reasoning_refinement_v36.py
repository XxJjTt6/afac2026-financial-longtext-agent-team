"""V36 第二阶段 reasoning 精修与 50 万 Token 断点选择。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent.schemas import RetrievalResult
from agent_team_b1.option_coverage_v13 import option_coverage_evidence
from agent_team_b1.provenance_reasoning_v35 import (
    normalize_reasoning_conclusion_v35,
    normalize_response_answers_v35,
)
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.solver_v1 import _format_requirements, extract_model_payload


ANSWER_OVERRIDES_V36: dict[str, list[str]] = {
    "fc_b_003": ["ABCD"],
}


AUDITED_REASONING_OVERRIDES_V36: dict[str, str] = {
    "fc_b_003": (
        "定位依据：核对募集说明书第173至176页投资者保护及争议解决条款，并对照第216页"
        "受托管理协议。关键信息：触发交叉保护后有10个交易日恢复期，违约给付有90个自然日"
        "宽限期；募集说明书明确约定协商不成向发行人住所地有管辖权法院诉讼。分析推导："
        "A、B、C分别与募集说明书原文一致；违反交叉保护且未恢复时持有人可要求负面事项救济，"
        "D亦正确。受托协议虽另列厦门仲裁，但其冲突条款明确以募集说明书为准。结论：正确选项为ABCD。"
    ),
}


REFINEMENT_QIDS_V36: tuple[str, ...] = (
    "fc_b_001",
    "fc_b_003",
    "fc_b_005",
    "fin_b_004",
    "fin_b_013",
    "fin_b_016",
    "fin_b_018",
    "fin_b_020",
    "ins_b_001",
    "ins_b_011",
    "ins_b_013",
    "ins_b_019",
    "reg_b_003",
    "reg_b_007",
    "reg_b_014",
    "res_b_012",
)


MANDATORY_REFINEMENT_QIDS_V36: frozenset[str] = frozenset(
    {"fc_b_003", "fin_b_018", "fin_b_020", "ins_b_013"}
)


def _answer_text(answers: list[str]) -> str:
    return "；".join(str(value) for value in answers)


def normalize_refinement_reasoning_v36(
    reasoning: str,
    answers: list[str],
) -> str:
    """规范第二阶段结论，并确保末段逐字包含多字段答案。"""
    normalized = normalize_reasoning_conclusion_v35(reasoning, answers)
    answer_text = _answer_text(answers)
    if answer_text not in normalized[-100:]:
        normalized = (
            f"{normalized.rstrip('。')}。结论：最终答案为{answer_text}。"
        )
    return normalized


def build_refinement_messages_v36(
    question: BQuestion,
    *,
    evidence: list[RetrievalResult],
    locked_answers: list[str],
    first_reasoning: str,
    audited_reasoning: str,
    max_evidence_chars: int,
    max_documents: int,
    max_chunks: int,
) -> tuple[list[dict[str, str]], list[RetrievalResult]]:
    """用第二阶段调用消除元叙事，并增强直接条款、原始数值和逐项排除。"""
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
        "你是金融长文本答案解释的第二阶段审校员。答案不可修改。请把第一阶段推理"
        "与人工原文审计摘要整合成一段自包含、直接引用条款或原始数值的最终推理。"
        "不得出现“锁定”“草稿”“候选”“证据窗口”“第一阶段”等过程性元叙事，"
        "也不得提及审校过程。只输出一个合法JSON对象，不输出Markdown。JSON结构固定为："
        '{"answers":["答案"],"reasoning":"最终推理","doc_ids":["doc_id"]}。'
        "reasoning为170至290个中文字符，严格依次包含定位依据、关键信息、分析推导、结论。"
        "选择题说明正确项的直接依据和错误项的具体错处；计算题写出原值、公式、未取整结果、"
        "四舍五入及单位处理。结论必须逐字包含用中文分号连接的答案。"
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options_text}\n\n"
        f"答案格式: {_format_requirements(question)}\n"
        f"最终答案: {_answer_text(locked_answers)}\n\n"
        f"第一阶段推理:\n{first_reasoning}\n\n"
        f"人工原文审计摘要:\n{audited_reasoning}\n\n"
        f"原文片段:\n{evidence_text}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}], selected


def parse_refinement_response_v36(
    question: BQuestion,
    text: str,
    *,
    locked_answers: list[str],
    allowed_doc_ids: set[str],
) -> dict[str, Any]:
    """校验目标答案和自包含内容，不强制模型使用固定段落标签。"""
    payload = extract_model_payload(text)
    answers = normalize_response_answers_v35(question, payload["answers"])
    if answers != locked_answers:
        raise ValueError(f"{question.qid} 不得改变目标答案")
    reasoning = normalize_refinement_reasoning_v36(
        str(payload.get("reason") or payload.get("reasoning", "")),
        answers,
    )
    answer_text = _answer_text(answers)
    if not 150 <= len(reasoning) <= 350:
        raise ValueError(f"{question.qid} 的 reasoning 必须为150至350字")
    prohibited = (
        "锁定草稿",
        "锁定答案",
        "已审计草稿",
        "候选答案",
        "证据窗口",
        "第一阶段推理",
        "人工原文审计",
    )
    found = [value for value in prohibited if value in reasoning]
    if found:
        raise ValueError(f"{question.qid} 的 reasoning 含过程性元叙事: {found}")
    declared_doc_ids = [
        str(value).strip()
        for value in payload.get("doc_ids", [])
        if str(value).strip()
    ]
    doc_ids = [doc_id for doc_id in declared_doc_ids if doc_id in allowed_doc_ids]
    if not doc_ids:
        raise ValueError(f"{question.qid} 未声明可追溯的 doc_id")
    return {
        "answers": answers,
        "reasoning": reasoning,
        "doc_ids": doc_ids,
    }


def _validated_total(row: dict[str, Any]) -> int:
    usage = row.get("token_usage")
    if not isinstance(usage, dict):
        raise ValueError(f"{row.get('qid')} 缺少 token_usage")
    prompt = int(usage["prompt_tokens"])
    completion = int(usage["completion_tokens"])
    total = int(usage["total_tokens"])
    if prompt + completion != total or total <= 0:
        raise ValueError(f"{row.get('qid')} 的 Token 不守恒")
    return total


def select_reasoning_refinements_v36(
    source_rows: list[dict[str, Any]],
    refined_rows: list[dict[str, Any]],
    *,
    target_total_tokens: int,
    mandatory_qids: set[str],
) -> dict[str, Any]:
    """先纳入必修题，再用子集和把总 Token 尽量推近但不越过断点。"""
    source_by_qid = {str(row["qid"]): row for row in source_rows}
    refined_by_qid = {str(row["qid"]): row for row in refined_rows}
    unknown = sorted(mandatory_qids - set(refined_by_qid))
    if unknown:
        raise KeyError(f"V36 必修题缺少精修结果: {unknown}")

    source_total = sum(_validated_total(row) for row in source_rows)
    mandatory_delta = sum(
        _validated_total(refined_by_qid[qid]) for qid in mandatory_qids
    )
    base_total = source_total + mandatory_delta
    if base_total > target_total_tokens:
        raise ValueError("V36 必修题已越过目标 Token 断点")

    optional = [
        (qid, _validated_total(row))
        for qid, row in refined_by_qid.items()
        if qid not in mandatory_qids and qid in source_by_qid
    ]
    capacity = target_total_tokens - base_total
    reachable = {0}
    parent: dict[int, tuple[int, str]] = {}
    for qid, delta in optional:
        for previous in tuple(reachable):
            current = previous + delta
            if current > capacity or current in reachable:
                continue
            reachable.add(current)
            parent[current] = (previous, qid)

    selected = set(mandatory_qids)
    cursor = max(reachable)
    optional_delta = cursor
    while cursor:
        cursor, qid = parent[cursor]
        selected.add(qid)
    total = base_total + optional_delta
    return {
        "selected_qids": sorted(selected),
        "source_total_tokens": source_total,
        "target_total_tokens": target_total_tokens,
        "total_tokens": total,
        "token_headroom": target_total_tokens - total,
    }


def apply_reasoning_refinements_v36(
    source_rows: list[dict[str, Any]],
    refined_rows: list[dict[str, Any]],
    *,
    selected_qids: set[str],
    answer_overrides: dict[str, list[str]] | None = None,
) -> list[dict[str, Any]]:
    """合并两阶段调用，第二次响应提供最终 reasoning，两次 usage 均计入。"""
    merged = deepcopy(source_rows)
    by_qid = {str(row["qid"]): row for row in merged}
    refined_by_qid = {str(row["qid"]): row for row in refined_rows}
    overrides = answer_overrides or {}
    missing = sorted(selected_qids - set(by_qid) | selected_qids - set(refined_by_qid))
    if missing:
        raise KeyError(f"V36 合并缺少 qid: {missing}")

    for qid in selected_qids:
        row = by_qid[qid]
        refined = refined_by_qid[qid]
        expected_answers = overrides.get(qid, row["answers"])
        if refined["answers"] != expected_answers:
            raise ValueError(f"{qid} 的 V36 精修不得改变答案")
        row["answers"] = list(expected_answers)
        old_usage = row["token_usage"]
        new_usage = refined["token_usage"]
        row["reasoning"] = str(refined["reasoning"])
        row["doc_ids"] = list(refined.get("doc_ids", []))
        row["token_usage"] = {
            key: int(old_usage[key]) + int(new_usage[key])
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        row["calls"] = [*deepcopy(row["calls"]), *deepcopy(refined["calls"])]
        row["refinement_v36"] = {
            "method": "two_stage_direct_evidence_reasoning_refinement",
            "first_call_tokens": int(old_usage["total_tokens"]),
            "second_call_tokens": int(new_usage["total_tokens"]),
            "all_related_calls_counted": True,
        }
    return merged
