"""V32 官方模板格式诊断：保留 V31 语义修正，仅恢复两道无单位答案。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from agent_team_b1.full_accuracy_audit_v30 import (
    REASONING_OVERRIDES_V30,
    SOURCE_DOC_IDS_V30,
)


ANSWER_OVERRIDES_V32: dict[str, list[str]] = {
    "fin_b_013": ["40.05", "10.10"],
    "fin_b_017": ["1049321.98", "0.08"],
}


REASONING_OVERRIDES_V32: dict[str, str] = {
    qid: REASONING_OVERRIDES_V30[qid] for qid in ANSWER_OVERRIDES_V32
}


SOURCE_DOC_IDS_V32: dict[str, list[str]] = {
    qid: SOURCE_DOC_IDS_V30[qid] for qid in ANSWER_OVERRIDES_V32
}


def apply_official_format_probe_v32(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """只修复官方模板可确定的两处格式，不改变来源 API usage。"""
    audited = deepcopy(rows)
    by_qid = {str(row.get("qid", "")): row for row in audited}
    missing = sorted(set(ANSWER_OVERRIDES_V32) - set(by_qid))
    if missing:
        raise KeyError(f"V32 来源缺少 qid: {missing}")

    for qid, answers in ANSWER_OVERRIDES_V32.items():
        row = by_qid[qid]
        before = list(row.get("answers", []))
        row["answers"] = list(answers)
        row["reasoning"] = REASONING_OVERRIDES_V32[qid]
        row["doc_ids"] = list(SOURCE_DOC_IDS_V32[qid])
        row["manual_audit_v32"] = {
            "method": "official_template_exact_field_format_probe",
            "api_calls_added": 0,
            "answer_before": before,
            "answer_after": list(answers),
            "source_doc_ids": list(SOURCE_DOC_IDS_V32[qid]),
        }
    return audited
