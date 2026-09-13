"""构建V45未舍入计算修正版提交。"""

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
from agent_team_b1.questions_v1 import load_template_specs
from agent_team_b1.reasoned_submission_v5 import (
    ReasonedSubmissionAnswer,
    validate_reasoned_submission,
    write_reasoned_submission,
)
from agent_team_b1.submission_v39 import _validate_row_calls


EXPECTED_TOTAL_TOKENS_V45 = 498_816


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_v45_artifacts(
    *,
    v42_results_path: Path,
    fin14_correction_path: Path,
    template_path: Path,
    answer_results_path: Path,
    submission_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    """用一条有完整Qwen调用记录的未舍入结果替换V42对应整行。"""
    paths = {
        "v42": Path(v42_results_path),
        "correction": Path(fin14_correction_path),
        "template": Path(template_path),
        "answer_results": Path(answer_results_path),
        "submission": Path(submission_path),
        "manifest": Path(manifest_path),
    }
    specs = load_template_specs(paths["template"])
    expected_order = [spec.qid for spec in specs]
    old_rows = _read_jsonl(paths["v42"])
    if [row["qid"] for row in old_rows] != expected_order or len(old_rows) != 100:
        raise ValueError("V42结果必须按官方模板完整覆盖100题")

    correction = json.loads(paths["correction"].read_text(encoding="utf-8"))
    if correction.get("qid") != "fin_b_014":
        raise ValueError("V45只接受fin_b_014修正行")
    if correction.get("answers") != ["1.12", "9.82", "8.69"]:
        raise ValueError("fin_b_014必须使用未舍入差值8.69")
    if correction.get("model") != "qwen3.7-plus":
        raise ValueError("V45修正行必须由qwen3.7-plus生成")
    if "8.694991" not in str(correction.get("reasoning", "")):
        raise ValueError("fin_b_014 reasoning必须展示未舍入差值")
    _validate_row_calls(correction)

    final_rows = [
        deepcopy(correction) if row["qid"] == "fin_b_014" else deepcopy(row)
        for row in old_rows
    ]
    changed = [
        row["qid"]
        for old, row in zip(old_rows, final_rows, strict=True)
        if old != row
    ]
    if changed != ["fin_b_014"]:
        raise ValueError(f"V45答案面必须只改变fin_b_014: {changed}")

    write_jsonl(paths["answer_results"], final_rows)
    answer_map = {
        row["qid"]: ReasonedSubmissionAnswer(
            qid=row["qid"],
            answers=[normalize_numeric_grouping(str(value)) for value in row["answers"]],
            reasoning=str(row["reasoning"]),
            token_usage=TokenUsage(**row["token_usage"]),
        )
        for row in final_rows
    }
    write_reasoned_submission(paths["template"], paths["submission"], answer_map)
    validation = validate_reasoned_submission(paths["template"], paths["submission"])
    token_usage = dict(validation["token_usage"])
    if int(token_usage["total_tokens"]) != EXPECTED_TOTAL_TOKENS_V45:
        raise ValueError(f"V45 Token汇总不符: {token_usage}")

    manifest = {
        "version": "b1_fin14_unrounded_v45",
        "created_at": datetime.now().astimezone().isoformat(),
        "question_count": len(final_rows),
        "answer_change_vs_v42": {
            "fin_b_014": {
                "before": ["1.12", "9.82", "8.70"],
                "after": ["1.12", "9.82", "8.69"],
            }
        },
        "intermediate_rounding_forbidden": True,
        "row_level_source_binding": True,
        "token_usage": token_usage,
        "token_headroom_below_500k": 499_999 - int(token_usage["total_tokens"]),
        "validation": validation,
        "sha256": {
            "v42_results": _sha256(paths["v42"]),
            "fin14_correction": _sha256(paths["correction"]),
            "answer_results": _sha256(paths["answer_results"]),
            "submission": _sha256(paths["submission"]),
        },
    }
    write_json(paths["manifest"], manifest)
    return manifest
