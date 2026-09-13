"""构建 V36 两阶段 reasoning 精修与 Token 断点提交。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.io.jsonl import write_json, write_jsonl
from agent.schemas import TokenUsage
from agent_team_b1.answer_format_v8 import normalize_numeric_grouping
from agent_team_b1.clean_reasoning_v10 import official_token_efficiency_score
from agent_team_b1.provenance_reasoning_v35 import (
    normalize_response_answers_v35,
)
from agent_team_b1.questions_v1 import load_b_questions, load_template_specs
from agent_team_b1.reasoned_submission_v5 import (
    ReasonedSubmissionAnswer,
    validate_reasoned_submission,
    write_reasoned_submission,
)
from agent_team_b1.reasoning_refinement_v36 import (
    ANSWER_OVERRIDES_V36,
    MANDATORY_REFINEMENT_QIDS_V36,
    apply_reasoning_refinements_v36,
    normalize_refinement_reasoning_v36,
    select_reasoning_refinements_v36,
)
from agent_team_b1.solver_v1 import extract_model_payload


TARGET_TOTAL_TOKENS_V36 = 499_999
V32_OFFICIAL_SCORE = 90.7166
V32_TOKEN_EFFICIENCY = 88.65822


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_v36_artifacts(
    *,
    source_path: Path,
    refined_path: Path,
    locked_answers_path: Path,
    template_path: Path,
    answer_results_path: Path,
    submission_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    source_path = Path(source_path)
    refined_path = Path(refined_path)
    locked_answers_path = Path(locked_answers_path)
    template_path = Path(template_path)
    answer_results_path = Path(answer_results_path)
    submission_path = Path(submission_path)
    manifest_path = Path(manifest_path)

    source_rows = _read_rows(source_path)
    refined_rows = _read_rows(refined_path)
    locked_rows = _read_rows(locked_answers_path)
    selection = select_reasoning_refinements_v36(
        source_rows,
        refined_rows,
        target_total_tokens=TARGET_TOTAL_TOKENS_V36,
        mandatory_qids=set(MANDATORY_REFINEMENT_QIDS_V36),
    )
    selected_qids = set(selection["selected_qids"])
    merged_rows = apply_reasoning_refinements_v36(
        source_rows,
        refined_rows,
        selected_qids=selected_qids,
        answer_overrides=ANSWER_OVERRIDES_V36,
    )

    specs = load_template_specs(template_path)
    questions = load_b_questions(
        template_path.parent / "question_b",
        template_path,
        expected_count=100,
    )
    question_by_qid = {question.qid: question for question in questions}
    expected_order = [spec.qid for spec in specs]
    merged_by_qid = {str(row["qid"]): row for row in merged_rows}
    locked_by_qid = {str(row["qid"]): row for row in locked_rows}
    if len(specs) != 100 or set(merged_by_qid) != set(expected_order):
        raise ValueError("V36 来源必须与官方模板的100个 qid 完全一致")
    if set(locked_by_qid) != set(expected_order):
        raise ValueError("V36 锁定答案来源必须覆盖100题")

    ordered = [merged_by_qid[qid] for qid in expected_order]
    for row in ordered:
        qid = str(row["qid"])
        expected_answers = ANSWER_OVERRIDES_V36.get(
            qid,
            locked_by_qid[qid]["answers"],
        )
        if row["answers"] != expected_answers:
            raise ValueError(f"{qid} 的 V36 答案发生变化")
        calls = row.get("calls")
        expected_call_count = 2 if qid in selected_qids else 1
        if not isinstance(calls, list) or len(calls) != expected_call_count:
            raise ValueError(f"{qid} 的调用数与精修选择不一致")
        summed_usage = {
            key: sum(int(call["token_usage"][key]) for call in calls)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        if summed_usage != row["token_usage"]:
            raise ValueError(f"{qid} 未完整计入两阶段调用 usage")

        if qid in selected_qids:
            payload = extract_model_payload(str(calls[-1].get("response", "")))
            response_answers = normalize_response_answers_v35(
                question_by_qid[qid],
                payload["answers"],
            )
            response_reasoning = normalize_refinement_reasoning_v36(
                str(payload.get("reason") or payload.get("reasoning", "")),
                response_answers,
            )
            if (
                response_answers != row["answers"]
                or response_reasoning != row["reasoning"]
            ):
                raise ValueError(f"{qid} 的最终内容与最后一次调用不一致")

        reasoning = str(row["reasoning"])
        if not 150 <= len(reasoning) <= 350:
            raise ValueError(f"{qid} 的 reasoning 长度不合规")
        answers_text = "；".join(str(value) for value in row["answers"])
        if answers_text not in reasoning[-100:]:
            raise ValueError(f"{qid} 的 reasoning 末段未包含最终答案")

    write_jsonl(answer_results_path, ordered)
    answer_map = {
        row["qid"]: ReasonedSubmissionAnswer(
            qid=row["qid"],
            answers=[normalize_numeric_grouping(str(value)) for value in row["answers"]],
            reasoning=str(row["reasoning"]),
            token_usage=TokenUsage(**row["token_usage"]),
        )
        for row in ordered
    }
    write_reasoned_submission(template_path, submission_path, answer_map)
    submission_text = submission_path.read_text(encoding="utf-8-sig")
    submission_path.write_text(submission_text, encoding="utf-8-sig", newline="\n")
    validation = validate_reasoned_submission(template_path, submission_path)
    token_usage = dict(validation["token_usage"])
    total_tokens = int(token_usage["total_tokens"])
    if total_tokens != selection["total_tokens"] or total_tokens > TARGET_TOTAL_TOKENS_V36:
        raise ValueError("V36 总 Token 与选择结果不一致或越过断点")
    token_efficiency = round(official_token_efficiency_score(total_tokens), 6)
    projected_score = round(
        V32_OFFICIAL_SCORE
        + 0.2 * (token_efficiency - V32_TOKEN_EFFICIENCY),
        6,
    )

    manifest: dict[str, Any] = {
        "version": "b1_two_stage_reasoning_apex_v36",
        "created_at": datetime.now().astimezone().isoformat(),
        "source": str(source_path.resolve()),
        "refined_source": str(refined_path.resolve()),
        "locked_answers_source": str(locked_answers_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(ordered),
        "answer_change_count": len(ANSWER_OVERRIDES_V36),
        "answer_overrides": ANSWER_OVERRIDES_V36,
        "selected_refinement_qids": sorted(selected_qids),
        "selected_refinement_count": len(selected_qids),
        "all_related_model_calls_counted": True,
        "selection": selection,
        "token_usage": token_usage,
        "token_efficiency_score": token_efficiency,
        "projected_score_from_token_change_only": projected_score,
        "reasoning_gain_not_in_projection": True,
        "validation": validation,
        "sha256": {
            "source": _sha256(source_path),
            "refined_source": _sha256(refined_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest
