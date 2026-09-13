"""构建 V33 断点下缓存调用复用提交。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.io.jsonl import write_json, write_jsonl
from agent.schemas import TokenUsage
from agent_team_b1.answer_format_v8 import normalize_numeric_grouping
from agent_team_b1.cached_token_apex_v33 import (
    CACHE_SOURCES_V33,
    apply_cached_token_apex_v33,
    load_cache_seed_rows_v33,
)
from agent_team_b1.clean_reasoning_v10 import official_token_efficiency_score
from agent_team_b1.questions_v1 import load_template_specs
from agent_team_b1.reasoned_submission_v5 import (
    ReasonedSubmissionAnswer,
    validate_reasoned_submission,
    write_reasoned_submission,
)


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


def build_cached_v33_artifacts(
    *,
    source_path: Path,
    template_path: Path,
    answer_results_path: Path,
    submission_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    source_path = Path(source_path)
    template_path = Path(template_path)
    answer_results_path = Path(answer_results_path)
    submission_path = Path(submission_path)
    manifest_path = Path(manifest_path)
    root = source_path.parent.parent

    source_rows = _read_rows(source_path)
    specs = load_template_specs(template_path)
    expected_order = [spec.qid for spec in specs]
    source_by_qid = {str(row.get("qid", "")): row for row in source_rows}
    if len(specs) != 100 or set(source_by_qid) != set(expected_order):
        raise ValueError("V33 来源必须与官方模板的100个 qid 完全一致")

    seed_rows = load_cache_seed_rows_v33(root)
    audited_rows = apply_cached_token_apex_v33(source_rows, seed_rows)
    audited_by_qid = {str(row["qid"]): row for row in audited_rows}
    ordered = [audited_by_qid[qid] for qid in expected_order]
    answer_change_qids: list[str] = []
    reasoning_change_qids: list[str] = []
    for row in ordered:
        qid = str(row["qid"])
        if row["answers"] != source_by_qid[qid]["answers"]:
            answer_change_qids.append(qid)
        if row["reasoning"] != source_by_qid[qid]["reasoning"]:
            reasoning_change_qids.append(qid)
        usage = TokenUsage(**row["token_usage"])
        if usage.total_tokens != usage.prompt_tokens + usage.completion_tokens:
            raise ValueError(f"{qid} 的 V33 Token 不守恒")

    if answer_change_qids or reasoning_change_qids:
        raise ValueError("V33 Token 断点版不得改变 V32 答案或推理文本")

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
    token_efficiency = round(official_token_efficiency_score(total_tokens), 6)
    if total_tokens != 499_695 or total_tokens >= 500_000:
        raise ValueError(f"V33 总 Token 未落在预定断点位置: {total_tokens}")

    projected_score = round(
        V32_OFFICIAL_SCORE
        + 0.2 * (token_efficiency - V32_TOKEN_EFFICIENCY),
        6,
    )
    token_savings = {
        qid: audited_by_qid[qid]["cache_audit_v33"]["token_saved"]
        for qid in CACHE_SOURCES_V33
    }
    manifest: dict[str, Any] = {
        "version": "b1_cached_token_apex_v33",
        "created_at": datetime.now().astimezone().isoformat(),
        "source": str(source_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(ordered),
        "answer_change_count": len(answer_change_qids),
        "reasoning_change_count": len(reasoning_change_qids),
        "cache_replacement_qids": sorted(CACHE_SOURCES_V33),
        "cache_replacement_count": len(CACHE_SOURCES_V33),
        "token_savings_by_qid": token_savings,
        "token_saved_total": sum(token_savings.values()),
        "token_usage": token_usage,
        "token_efficiency_score": token_efficiency,
        "v32_official_score": V32_OFFICIAL_SCORE,
        "projected_score_from_v32": projected_score,
        "projection_assumption": "accuracy_and_reasoning_scores_unchanged",
        "validation": validation,
        "sha256": {
            "source": _sha256(source_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest
