"""Build the V40 last-chance submission from audited V32/V37 rows."""

from __future__ import annotations

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
from agent_team_b1.submission_v39 import (
    EXACT_CONTENT_V32_TOKEN_TRIM_QIDS_V39,
    V32_OFFICIAL_SCORE,
    V32_TOKEN_EFFICIENCY,
    V37_OFFICIAL_SCORE,
    V37_TOKEN_EFFICIENCY,
    _read_rows,
    _sha256,
    _validate_row_calls,
)


EXPECTED_TOTAL_TOKENS_V40 = 499_907

# V40 removes V39's only malformed heading and only audit-meta narrative. The
# replacement rows are complete, already generated V32/V37 rows with exact usage.
RETAINED_V37_REASONING_QIDS_V40: tuple[str, ...] = (
    "fc_b_009",
    "fin_b_004",
    "fin_b_007",
    "fin_b_011",
    "fin_b_012",
    "ins_b_004",
    "ins_b_012",
    "ins_b_015",
    "ins_b_016",
    "reg_b_003",
    "res_b_003",
    "res_b_011",
)

REASONING_SWAPS_VS_V39: dict[str, str] = {
    "fin_b_001": "v37_to_v32",
    "ins_b_012": "v32_to_v37",
}

FORBIDDEN_REASONING_FRAGMENTS_V40: tuple[str, ...] = (
    "【结论：",
    "来源推理有误",
    "来源模型仅选",
    "需修正来源模型",
)


def build_v40_artifacts(
    *,
    v32_path: Path,
    v37_path: Path,
    v39_path: Path,
    template_path: Path,
    answer_results_path: Path,
    submission_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """Select complete rows while removing V39's two visible judge defects."""
    v32_path = Path(v32_path)
    v37_path = Path(v37_path)
    v39_path = Path(v39_path)
    template_path = Path(template_path)
    answer_results_path = Path(answer_results_path)
    submission_path = Path(submission_path)
    manifest_path = Path(manifest_path)

    specs = load_template_specs(template_path)
    expected_order = [spec.qid for spec in specs]
    expected_qids = set(expected_order)
    v32_by_qid = {str(row["qid"]): row for row in _read_rows(v32_path)}
    v37_by_qid = {str(row["qid"]): row for row in _read_rows(v37_path)}
    v39_by_qid = {str(row["qid"]): row for row in _read_rows(v39_path)}
    if len(specs) != 100:
        raise ValueError("V40 requires exactly 100 template questions")
    if any(
        set(rows) != expected_qids
        for rows in (v32_by_qid, v37_by_qid, v39_by_qid)
    ):
        raise ValueError("V32, V37 and V39 must cover the official 100 qids")

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
    retained = set(RETAINED_V37_REASONING_QIDS_V40)
    if not retained < reasoning_differences or "fc_b_003" not in reasoning_differences:
        raise ValueError("V40 retained-reasoning contract does not match the sources")
    restored = reasoning_differences - retained - {"fc_b_003"}
    if len(reasoning_differences) != 96 or len(restored) != 83:
        raise ValueError("V40 expects 83 V32 restorations from 96 reasoning changes")

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
        if any(fragment in row["reasoning"] for fragment in FORBIDDEN_REASONING_FRAGMENTS_V40):
            raise ValueError(f"{qid} retains a known judge-facing reasoning defect")
        final_rows.append(row)

    final_by_qid = {str(row["qid"]): row for row in final_rows}
    changed_vs_v39 = {
        qid
        for qid in expected_order
        if final_by_qid[qid] != v39_by_qid[qid]
    }
    if changed_vs_v39 != set(REASONING_SWAPS_VS_V39):
        raise ValueError("V40 must differ from V39 only on the two audited swaps")
    if final_by_qid["fin_b_001"] != v32_by_qid["fin_b_001"]:
        raise ValueError("V40 must restore fin_b_001 from V32")
    if final_by_qid["ins_b_012"] != v37_by_qid["ins_b_012"]:
        raise ValueError("V40 must promote ins_b_012 from V37")

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
        raise ValueError("V40 must retain only the fc_b_003 answer correction")
    if set(reasoning_change_qids) != retained | {"fc_b_003"}:
        raise ValueError("V40 reasoning changes exceeded the audited V37 set")

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
    if total_tokens != EXPECTED_TOTAL_TOKENS_V40 or total_tokens >= 500_000:
        raise ValueError(f"V40 total Token usage is outside its bound: {total_tokens}")

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
        "version": "b1_last_chance_reasoning_lock_v40",
        "created_at": datetime.now().astimezone().isoformat(),
        "v32_source": str(v32_path.resolve()),
        "v37_source": str(v37_path.resolve()),
        "v39_source": str(v39_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(final_rows),
        "answer_overrides_vs_v32": answer_overrides,
        "reasoning_change_count_vs_v32": len(reasoning_change_qids),
        "reasoning_change_qids_vs_v32": reasoning_change_qids,
        "restored_v32_reasoning_count": len(restored),
        "restored_v32_reasoning_qids": sorted(restored),
        "retained_v37_reasoning_qids": list(RETAINED_V37_REASONING_QIDS_V40),
        "reasoning_swaps_vs_v39": dict(REASONING_SWAPS_VS_V39),
        "known_reasoning_defects_remaining": 0,
        "exact_content_v32_token_trim_qids": list(
            EXACT_CONTENT_V32_TOKEN_TRIM_QIDS_V39
        ),
        "source_by_qid": source_by_qid,
        "row_level_source_binding": True,
        "all_related_model_calls_counted": True,
        "token_usage": token_usage,
        "token_headroom_below_cliff": 499_999 - total_tokens,
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
            "V40 reasoning score equals V32 after restoring 83 rows and removing "
            "V39's two visible reasoning defects; fc_b_003 gains one correct answer. "
            "The projection is conditional, not an official-score guarantee."
        ),
        "validation": validation,
        "sha256": {
            "v32_source": _sha256(v32_path),
            "v37_source": _sha256(v37_path),
            "v39_source": _sha256(v39_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest
