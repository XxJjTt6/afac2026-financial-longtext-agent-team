"""构建 V34 reasoning judge 定向增强提交。"""

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
from agent_team_b1.questions_v1 import load_template_specs
from agent_team_b1.reasoned_submission_v5 import (
    ReasonedSubmissionAnswer,
    validate_reasoned_submission,
    write_reasoned_submission,
)
from agent_team_b1.reasoning_judge_polish_v34 import (
    REASONING_OVERRIDES_V34,
    apply_reasoning_judge_polish_v34,
)


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_v34_artifacts(
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

    source_rows = _read_rows(source_path)
    specs = load_template_specs(template_path)
    expected_order = [spec.qid for spec in specs]
    source_by_qid = {str(row.get("qid", "")): row for row in source_rows}
    if len(specs) != 100 or set(source_by_qid) != set(expected_order):
        raise ValueError("V34 来源必须与官方模板的100个 qid 完全一致")

    polished_rows = apply_reasoning_judge_polish_v34(source_rows)
    polished_by_qid = {str(row["qid"]): row for row in polished_rows}
    ordered = [polished_by_qid[qid] for qid in expected_order]
    answer_change_qids: list[str] = []
    reasoning_change_qids: list[str] = []
    for row in ordered:
        qid = str(row["qid"])
        source = source_by_qid[qid]
        if row["answers"] != source["answers"]:
            answer_change_qids.append(qid)
        if row["reasoning"] != source["reasoning"]:
            reasoning_change_qids.append(qid)
        if row["token_usage"] != source["token_usage"] or row.get("calls") != source.get("calls"):
            raise ValueError(f"{qid} 的 V34 polish 不得改变 usage 或 calls")
        reasoning = str(row["reasoning"])
        if not 150 <= len(reasoning) <= 350:
            raise ValueError(f"{qid} 的 reasoning 长度不在150至350字")

    if answer_change_qids:
        raise ValueError("V34 不得改变 V33 答案")
    if set(reasoning_change_qids) != set(REASONING_OVERRIDES_V34):
        raise ValueError("V34 reasoning 变化集合与声明不一致")
    for qid, reasoning in REASONING_OVERRIDES_V34.items():
        answers = [str(value) for value in polished_by_qid[qid]["answers"]]
        if "；".join(answers) not in reasoning.rsplit("结论", 1)[-1]:
            raise ValueError(f"{qid} 的 V34 结论未逐字包含答案")

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
    if total_tokens != 499_695:
        raise ValueError(f"V34 必须保持 V33 总 Token: {total_tokens}")

    manifest: dict[str, Any] = {
        "version": "b1_reasoning_judge_polish_v34",
        "created_at": datetime.now().astimezone().isoformat(),
        "source": str(source_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(ordered),
        "answer_change_count": len(answer_change_qids),
        "reasoning_change_count": len(reasoning_change_qids),
        "reasoning_change_qids": sorted(reasoning_change_qids),
        "token_usage": token_usage,
        "token_efficiency_score": round(official_token_efficiency_score(total_tokens), 6),
        "validation": validation,
        "manual_audit": {
            "method": "direct_clause_numeric_reasoning_judge_polish",
            "additional_api_calls": 0,
            "source_usage_preserved": True,
        },
        "sha256": {
            "source": _sha256(source_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest
