"""构建 V31 语义准确率与官方百分数格式提交。"""

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
from agent_team_b1.semantic_accuracy_v31 import (
    ANSWER_OVERRIDES_V31,
    REASONING_OVERRIDES_V31,
    apply_semantic_accuracy_v31,
)


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_v31_artifacts(
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
    if len(source_rows) != len(source_by_qid):
        raise ValueError("V31 来源存在重复或空 qid")
    if len(specs) != 100 or set(source_by_qid) != set(expected_order):
        raise ValueError("V31 来源必须与官方模板的100个 qid 完全一致")

    audited_rows = apply_semantic_accuracy_v31(source_rows)
    audited_by_qid = {str(row["qid"]): row for row in audited_rows}
    ordered = [audited_by_qid[qid] for qid in expected_order]
    for row in ordered:
        qid = str(row["qid"])
        if row.get("token_usage") != source_by_qid[qid].get("token_usage"):
            raise ValueError(f"{qid} 的 V31 审计不得改动来源 API usage")
        usage = TokenUsage(**row["token_usage"])
        if usage.total_tokens != usage.prompt_tokens + usage.completion_tokens:
            raise ValueError(f"{qid} 的 Token 不守恒")
        reasoning_length = len(str(row.get("reasoning", "")).strip())
        if not 150 <= reasoning_length <= 350:
            raise ValueError(f"{qid} 的 reasoning 长度不在150至350字")

    for qid, answers in ANSWER_OVERRIDES_V31.items():
        row = audited_by_qid[qid]
        if row["answers"] != answers or row["reasoning"] != REASONING_OVERRIDES_V31[qid]:
            raise ValueError(f"{qid} 未完整应用 V31 修正")
        if "；".join(answers) not in str(row["reasoning"]).rsplit("结论", 1)[-1]:
            raise ValueError(f"{qid} 的答案与 reasoning 结论不一致")

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
    validation = validate_reasoned_submission(template_path, submission_path)
    token_usage = dict(validation["token_usage"])
    total_tokens = int(token_usage["total_tokens"])
    answer_deltas = {
        qid: {"before": source_by_qid[qid]["answers"], "after": audited_by_qid[qid]["answers"]}
        for qid in ANSWER_OVERRIDES_V31
        if source_by_qid[qid]["answers"] != audited_by_qid[qid]["answers"]
    }
    if len(answer_deltas) != len(ANSWER_OVERRIDES_V31):
        raise ValueError("V31 应当产生3道相对V30答案修正")

    root = source_path.parent.parent
    v29_path = root / "evaluation_results_b1_v29_reasoning_consistency" / "answer_results.jsonl"
    v29_rows = _read_rows(v29_path)
    v29_by_qid = {str(row["qid"]): row for row in v29_rows}
    net_deltas_from_v29 = {
        qid: {"before": v29_by_qid[qid]["answers"], "after": audited_by_qid[qid]["answers"]}
        for qid in expected_order
        if v29_by_qid[qid]["answers"] != audited_by_qid[qid]["answers"]
    }

    manifest: dict[str, Any] = {
        "version": "b1_semantic_accuracy_v31",
        "created_at": datetime.now().astimezone().isoformat(),
        "source": str(source_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(ordered),
        "answer_change_count": len(answer_deltas),
        "reasoning_repair_count": len(REASONING_OVERRIDES_V31),
        "answer_deltas": answer_deltas,
        "net_answer_change_count_from_v29": len(net_deltas_from_v29),
        "net_answer_deltas_from_v29": net_deltas_from_v29,
        "token_usage": token_usage,
        "token_efficiency_score": round(official_token_efficiency_score(total_tokens), 6),
        "validation": validation,
        "manual_audit": {
            "method": "official_format_and_cross_report_semantic_audit",
            "additional_api_calls": 0,
            "source_api_usage_preserved": True,
        },
        "sha256": {
            "source": _sha256(source_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
        "format_source": "https://tianchi.aliyun.com/competition/entrance/532486/customize880",
    }
    write_json(manifest_path, manifest)
    return manifest
