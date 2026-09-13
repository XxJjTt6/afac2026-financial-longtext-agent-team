"""构建 V37 独立可读 reasoning 精修与 50 万 Token 断点提交。"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.io.jsonl import write_json, write_jsonl
from agent.schemas import TokenUsage
from agent_team_b1.answer_format_v8 import normalize_numeric_grouping
from agent_team_b1.clean_reasoning_v10 import official_token_efficiency_score
from agent_team_b1.provenance_reasoning_v35 import normalize_response_answers_v35
from agent_team_b1.questions_v1 import load_b_questions, load_template_specs
from agent_team_b1.reasoned_submission_v5 import (
    ReasonedSubmissionAnswer,
    validate_reasoned_submission,
    write_reasoned_submission,
)
from agent_team_b1.solver_v1 import extract_model_payload
from agent_team_b1.standalone_reasoning_v37 import (
    ANSWER_OVERRIDES_V37,
    PROMOTED_REFINEMENT_QIDS_V37,
    REFINEMENT_QIDS_V37,
    normalize_final_format_v37,
    promote_format_only_result_v37,
)


TARGET_TOTAL_TOKENS_V37 = 499_999
EXPECTED_SOURCE_TOKENS_V37 = 456_852
EXPECTED_REFINEMENT_TOKENS_V37 = 42_510
EXPECTED_TOTAL_TOKENS_V37 = 499_362
V32_OFFICIAL_SCORE = 90.7166
V32_TOKEN_EFFICIENCY = 88.65822

ABANDONED_REFINEMENT_QIDS_V37: tuple[str, ...] = tuple(
    qid
    for qid in REFINEMENT_QIDS_V37
    if qid not in set(PROMOTED_REFINEMENT_QIDS_V37)
)


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sum_call_usage(calls: list[dict[str, Any]]) -> dict[str, int]:
    return {
        key: sum(int(call["token_usage"][key]) for call in calls)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def _add_usage(left: dict[str, Any], right: dict[str, Any]) -> dict[str, int]:
    return {
        key: int(left[key]) + int(right[key])
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }


def build_v37_artifacts(
    *,
    source_path: Path,
    refined_path: Path,
    format_only_attempt_path: Path,
    template_path: Path,
    answer_results_path: Path,
    submission_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """仅晋升九道已验证精修，并严格累计所有参与最终内容的调用。"""
    source_path = Path(source_path)
    refined_path = Path(refined_path)
    format_only_attempt_path = Path(format_only_attempt_path)
    template_path = Path(template_path)
    answer_results_path = Path(answer_results_path)
    submission_path = Path(submission_path)
    manifest_path = Path(manifest_path)

    source_rows = _read_rows(source_path)
    refined_rows = _read_rows(refined_path)
    format_only_attempts = json.loads(
        format_only_attempt_path.read_text(encoding="utf-8")
    )
    if not isinstance(format_only_attempts, list):
        raise ValueError("V37 仅格式规范化调用日志必须为列表")

    specs = load_template_specs(template_path)
    questions = load_b_questions(
        template_path.parent / "question_b",
        template_path,
        expected_count=100,
    )
    expected_order = [spec.qid for spec in specs]
    question_by_qid = {question.qid: question for question in questions}
    source_by_qid = {str(row["qid"]): row for row in source_rows}
    if len(specs) != 100 or set(source_by_qid) != set(expected_order):
        raise ValueError("V37 来源必须与官方模板的100个 qid 完全一致")

    source_total = sum(
        int(row["token_usage"]["total_tokens"]) for row in source_rows
    )
    if source_total != EXPECTED_SOURCE_TOKENS_V37:
        raise ValueError("V37 的 V35 来源 Token 与已审计基线不一致")

    format_only = promote_format_only_result_v37(
        "fc_b_003",
        format_only_attempts,
        required_answers=ANSWER_OVERRIDES_V37["fc_b_003"],
    )
    refined_by_qid = {str(row["qid"]): row for row in refined_rows}
    strict_qids = set(PROMOTED_REFINEMENT_QIDS_V37) - {"fc_b_003"}
    if set(refined_by_qid) != strict_qids:
        raise ValueError("V37 严格通过结果必须恰好覆盖八道晋升题")
    promoted_by_qid = {**refined_by_qid, "fc_b_003": format_only}

    merged_by_qid = deepcopy(source_by_qid)
    for qid in PROMOTED_REFINEMENT_QIDS_V37:
        source = merged_by_qid[qid]
        refined = promoted_by_qid[qid]
        expected_answers = ANSWER_OVERRIDES_V37.get(qid, source["answers"])
        if refined["answers"] != expected_answers:
            raise ValueError(f"{qid} 的 V37 精修不得改变锁定答案")

        source_calls = source.get("calls")
        refined_calls = refined.get("calls")
        if not isinstance(source_calls, list) or not isinstance(refined_calls, list):
            raise ValueError(f"{qid} 缺少可审计的模型调用")
        if _sum_call_usage(source_calls) != source["token_usage"]:
            raise ValueError(f"{qid} 的 V35 来源调用 Token 不完整")
        if _sum_call_usage(refined_calls) != refined["token_usage"]:
            raise ValueError(f"{qid} 的 V37 精修调用 Token 不完整")

        payload = extract_model_payload(str(refined_calls[-1].get("response", "")))
        response_answers = normalize_response_answers_v35(
            question_by_qid[qid], payload["answers"]
        )
        response_reasoning = str(
            payload.get("reason") or payload.get("reasoning", "")
        ).strip()
        if qid == "fc_b_003":
            response_reasoning = normalize_final_format_v37(
                response_reasoning, response_answers
            )
        response_doc_ids = [
            str(value).strip()
            for value in payload.get("doc_ids", [])
            if str(value).strip()
        ]
        if (
            response_answers != refined["answers"]
            or response_reasoning != refined["reasoning"]
            or response_doc_ids != refined["doc_ids"]
        ):
            raise ValueError(f"{qid} 的最终内容与最后一次 Qwen 响应不一致")

        source["answers"] = list(expected_answers)
        source["reasoning"] = str(refined["reasoning"])
        source["doc_ids"] = list(refined["doc_ids"])
        source["token_usage"] = _add_usage(
            source["token_usage"], refined["token_usage"]
        )
        source["calls"] = [*deepcopy(source_calls), *deepcopy(refined_calls)]
        if qid != "fc_b_003":
            source["evidence_refs"] = deepcopy(refined.get("evidence_refs", []))
        source["refinement_v37"] = {
            "method": "standalone_reasoning_judge_refinement",
            "source_tokens": int(
                source["token_usage"]["total_tokens"]
                - refined["token_usage"]["total_tokens"]
            ),
            "refinement_tokens": int(refined["token_usage"]["total_tokens"]),
            "refinement_call_count": len(refined_calls),
            "all_related_calls_counted": True,
            "format_only_normalization": qid == "fc_b_003",
        }

        reasoning = str(source["reasoning"])
        if not 150 <= len(reasoning) <= 350:
            raise ValueError(f"{qid} 的 V37 reasoning 长度不合规")
        answer_text = "；".join(str(value) for value in source["answers"])
        compact_answer = "".join(str(value) for value in source["answers"])
        if answer_text not in reasoning[-120:] and compact_answer not in reasoning[-120:]:
            raise ValueError(f"{qid} 的 V37 reasoning 末段未包含最终答案")

    ordered = [merged_by_qid[qid] for qid in expected_order]
    answer_changes = {
        row["qid"]: row["answers"]
        for row in ordered
        if row["answers"] != source_by_qid[row["qid"]]["answers"]
    }
    if answer_changes != ANSWER_OVERRIDES_V37:
        raise ValueError("V37 最终答案变化超出唯一高置信修正")

    refinement_total = sum(
        int(promoted_by_qid[qid]["token_usage"]["total_tokens"])
        for qid in PROMOTED_REFINEMENT_QIDS_V37
    )
    if refinement_total != EXPECTED_REFINEMENT_TOKENS_V37:
        raise ValueError("V37 晋升调用 Token 与已审计结果不一致")

    write_jsonl(answer_results_path, ordered)
    answer_map = {
        row["qid"]: ReasonedSubmissionAnswer(
            qid=row["qid"],
            answers=[
                normalize_numeric_grouping(str(value)) for value in row["answers"]
            ],
            reasoning=str(row["reasoning"]),
            token_usage=TokenUsage(**row["token_usage"]),
        )
        for row in ordered
    }
    write_reasoned_submission(template_path, submission_path, answer_map)
    submission_text = submission_path.read_text(encoding="utf-8-sig")
    submission_path.write_text(
        submission_text, encoding="utf-8-sig", newline="\n"
    )
    validation = validate_reasoned_submission(template_path, submission_path)
    token_usage = dict(validation["token_usage"])
    total_tokens = int(token_usage["total_tokens"])
    if total_tokens != EXPECTED_TOTAL_TOKENS_V37:
        raise ValueError("V37 最终总 Token 与审计值不一致")
    if total_tokens >= 500_000 or total_tokens > TARGET_TOTAL_TOKENS_V37:
        raise ValueError("V37 最终总 Token 越过官方效率断点")

    token_efficiency = round(official_token_efficiency_score(total_tokens), 6)
    projected_score = round(
        V32_OFFICIAL_SCORE
        + 0.2 * (token_efficiency - V32_TOKEN_EFFICIENCY),
        6,
    )
    manifest: dict[str, Any] = {
        "version": "b1_standalone_reasoning_judge_v37",
        "created_at": datetime.now().astimezone().isoformat(),
        "source": str(source_path.resolve()),
        "refined_source": str(refined_path.resolve()),
        "format_only_attempt_source": str(format_only_attempt_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(ordered),
        "answer_change_count": len(answer_changes),
        "answer_overrides": answer_changes,
        "promoted_refinement_qids": list(PROMOTED_REFINEMENT_QIDS_V37),
        "strict_refinement_qids": sorted(strict_qids),
        "format_only_refinement_qids": ["fc_b_003"],
        "abandoned_qids": list(ABANDONED_REFINEMENT_QIDS_V37),
        "abandoned_responses_contributed_to_final_content": False,
        "all_related_model_calls_counted": True,
        "source_total_tokens": source_total,
        "refinement_total_tokens": refinement_total,
        "target_total_tokens": TARGET_TOTAL_TOKENS_V37,
        "token_headroom": TARGET_TOTAL_TOKENS_V37 - total_tokens,
        "token_usage": token_usage,
        "token_efficiency_score": token_efficiency,
        "projected_score_from_token_change_only": projected_score,
        "reasoning_and_answer_gain_not_in_projection": True,
        "validation": validation,
        "sha256": {
            "source": _sha256(source_path),
            "refined_source": _sha256(refined_path),
            "format_only_attempt_source": _sha256(format_only_attempt_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest
