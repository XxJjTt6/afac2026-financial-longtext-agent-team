"""Build the V39 row-level recovery submission from V32 and V37."""

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
from agent_team_b1.questions_v1 import load_template_specs
from agent_team_b1.reasoned_submission_v5 import (
    ReasonedSubmissionAnswer,
    validate_reasoned_submission,
    write_reasoned_submission,
)


EXPECTED_TOTAL_TOKENS_V39 = 499_399
V32_OFFICIAL_SCORE = 90.716644
V32_TOKEN_EFFICIENCY = 88.65822
V37_OFFICIAL_SCORE = 91.3741
V37_TOKEN_EFFICIENCY = 99.8724

# These V37 texts are more self-contained or materially equivalent to V32.
# Keeping them also provides the Token capacity needed to restore 83 weaker rows.
RETAINED_V37_REASONING_QIDS_V39: tuple[str, ...] = (
    "fc_b_009",
    "fin_b_001",
    "fin_b_004",
    "fin_b_007",
    "fin_b_011",
    "fin_b_012",
    "ins_b_004",
    "ins_b_015",
    "ins_b_016",
    "reg_b_003",
    "res_b_003",
    "res_b_011",
)

# V32 and V37 contain identical answer and reasoning text for this qid. The
# complete V32 row is cheaper and moves the fused submission below the cliff.
EXACT_CONTENT_V32_TOKEN_TRIM_QIDS_V39: tuple[str, ...] = ("reg_b_021",)


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _validate_row_calls(row: dict[str, Any]) -> None:
    qid = str(row.get("qid", ""))
    usage = row.get("token_usage")
    calls = row.get("calls")
    if not isinstance(usage, dict) or not isinstance(calls, list) or not calls:
        raise ValueError(f"{qid} lacks a complete usage and call chain")
    summed = {
        key: sum(int(call["token_usage"][key]) for call in calls)
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    normalized = {
        key: int(usage[key])
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    if summed != normalized:
        raise ValueError(f"{qid} call usage does not match row usage")
    if normalized["total_tokens"] != (
        normalized["prompt_tokens"] + normalized["completion_tokens"]
    ):
        raise ValueError(f"{qid} token usage is not conserved")


def build_v39_artifacts(
    *,
    v32_path: Path,
    v37_path: Path,
    template_path: Path,
    answer_results_path: Path,
    submission_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Fuse complete V32/V37 rows without rebinding text to unrelated usage."""
    v32_path = Path(v32_path)
    v37_path = Path(v37_path)
    template_path = Path(template_path)
    answer_results_path = Path(answer_results_path)
    submission_path = Path(submission_path)
    manifest_path = Path(manifest_path)

    specs = load_template_specs(template_path)
    expected_order = [spec.qid for spec in specs]
    v32_by_qid = {str(row["qid"]): row for row in _read_rows(v32_path)}
    v37_by_qid = {str(row["qid"]): row for row in _read_rows(v37_path)}
    expected_qids = set(expected_order)
    if len(specs) != 100:
        raise ValueError("V39 requires exactly 100 template questions")
    if set(v32_by_qid) != expected_qids or set(v37_by_qid) != expected_qids:
        raise ValueError("V32 and V37 must cover the official 100 qids")

    answer_differences = {
        qid
        for qid in expected_order
        if v32_by_qid[qid]["answers"] != v37_by_qid[qid]["answers"]
    }
    if answer_differences != {"fc_b_003"}:
        raise ValueError("V37 must differ from V32 only on fc_b_003 answers")

    reasoning_differences = {
        qid
        for qid in expected_order
        if v32_by_qid[qid]["reasoning"] != v37_by_qid[qid]["reasoning"]
    }
    retained = set(RETAINED_V37_REASONING_QIDS_V39)
    if not retained < reasoning_differences or "fc_b_003" not in reasoning_differences:
        raise ValueError("V39 retained-reasoning contract does not match the sources")
    restored = reasoning_differences - retained - {"fc_b_003"}
    if len(reasoning_differences) != 96 or len(restored) != 83:
        raise ValueError("V39 expects 83 V32 reasoning restorations from 96 differences")

    final_rows: list[dict[str, Any]] = []
    source_by_qid: dict[str, str] = {}
    for qid in expected_order:
        if qid in restored or qid in EXACT_CONTENT_V32_TOKEN_TRIM_QIDS_V39:
            row = deepcopy(v32_by_qid[qid])
            source_by_qid[qid] = "v32"
        else:
            row = deepcopy(v37_by_qid[qid])
            source_by_qid[qid] = "v37"
        _validate_row_calls(row)
        final_rows.append(row)

    final_by_qid = {str(row["qid"]): row for row in final_rows}
    answer_overrides = {
        qid: list(final_by_qid[qid]["answers"])
        for qid in expected_order
        if final_by_qid[qid]["answers"] != v32_by_qid[qid]["answers"]
    }
    reasoning_change_qids = sorted(
        qid
        for qid in expected_order
        if final_by_qid[qid]["reasoning"] != v32_by_qid[qid]["reasoning"]
    )
    if answer_overrides != {"fc_b_003": ["ABCD"]}:
        raise ValueError("V39 must retain only the fc_b_003 answer correction")
    if set(reasoning_change_qids) != retained | {"fc_b_003"}:
        raise ValueError("V39 reasoning changes exceeded the retained V37 set")

    write_jsonl(answer_results_path, final_rows)
    answer_map = {
        row["qid"]: ReasonedSubmissionAnswer(
            qid=row["qid"],
            answers=[
                normalize_numeric_grouping(str(value)) for value in row["answers"]
            ],
            reasoning=str(row["reasoning"]),
            token_usage=TokenUsage(**row["token_usage"]),
        )
        for row in final_rows
    }
    write_reasoned_submission(template_path, submission_path, answer_map)
    submission_text = submission_path.read_text(encoding="utf-8-sig")
    submission_path.write_text(submission_text, encoding="utf-8-sig", newline="\n")
    validation = validate_reasoned_submission(template_path, submission_path)
    token_usage = dict(validation["token_usage"])
    total_tokens = int(token_usage["total_tokens"])
    if total_tokens != EXPECTED_TOTAL_TOKENS_V39 or total_tokens >= 500_000:
        raise ValueError(f"V39 total Token usage is outside its bound: {total_tokens}")

    token_efficiency = round(official_token_efficiency_score(total_tokens), 6)
    projected_score = round(
        V32_OFFICIAL_SCORE
        + 0.2 * (token_efficiency - V32_TOKEN_EFFICIENCY)
        + 0.5,
        6,
    )
    v37_measured_gain = round(V37_OFFICIAL_SCORE - V32_OFFICIAL_SCORE, 6)
    v37_token_contribution = round(
        0.2 * (V37_TOKEN_EFFICIENCY - V32_TOKEN_EFFICIENCY), 6
    )
    manifest: dict[str, Any] = {
        "version": "b1_official_feedback_recovery_v39",
        "created_at": datetime.now().astimezone().isoformat(),
        "v32_source": str(v32_path.resolve()),
        "v37_source": str(v37_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(final_rows),
        "answer_overrides_vs_v32": answer_overrides,
        "reasoning_change_count_vs_v32": len(reasoning_change_qids),
        "reasoning_change_qids_vs_v32": reasoning_change_qids,
        "restored_v32_reasoning_count": len(restored),
        "restored_v32_reasoning_qids": sorted(restored),
        "exact_content_v32_token_trim_qids": list(
            EXACT_CONTENT_V32_TOKEN_TRIM_QIDS_V39
        ),
        "retained_v37_reasoning_qids": list(RETAINED_V37_REASONING_QIDS_V39),
        "source_by_qid": source_by_qid,
        "row_level_source_binding": True,
        "all_related_model_calls_counted": True,
        "token_usage": token_usage,
        "token_efficiency_score": token_efficiency,
        "v32_official_score": V32_OFFICIAL_SCORE,
        "v37_official_score": V37_OFFICIAL_SCORE,
        "v37_measured_gain": v37_measured_gain,
        "v37_token_contribution": v37_token_contribution,
        "v37_non_token_contribution": round(
            v37_measured_gain - v37_token_contribution, 6
        ),
        "projected_score_if_fc3_accuracy_gains_one": projected_score,
        "projection_assumption": (
            "V39 reasoning score equals V32 after restoring 83 rows; the projection "
            "is conditional and not an official-score guarantee"
        ),
        "validation": validation,
        "sha256": {
            "v32_source": _sha256(v32_path),
            "v37_source": _sha256(v37_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest
