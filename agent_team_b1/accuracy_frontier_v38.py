"""V38 正确率优先候选池与答案变更晋升门禁。"""

from __future__ import annotations

from typing import Any


ACCURACY_AUDIT_QIDS_V38: tuple[str, ...] = (
    "fc_b_003",
    "fc_b_007",
    "fin_b_003",
    "fin_b_005",
    "fin_b_008",
    "fin_b_010",
    "fin_b_012",
    "fin_b_015",
    "ins_b_010",
    "ins_b_013",
    "ins_b_015",
    "ins_b_017",
    "ins_b_019",
    "reg_b_001",
    "res_b_003",
    "res_b_004",
    "res_b_009",
    "res_b_013",
    "res_b_017",
    "res_b_018",
    "res_b_020",
)


RESIDUAL_ACCURACY_AUDIT_QIDS_V38: tuple[str, ...] = (
    "fc_b_004",
    "fc_b_006",
    "fc_b_015",
    "fin_b_001",
    "fin_b_004",
    "fin_b_006",
    "fin_b_007",
    "fin_b_009",
    "fin_b_011",
    "fin_b_019",
    "ins_b_004",
    "ins_b_006",
    "ins_b_008",
    "ins_b_012",
    "ins_b_014",
    "ins_b_016",
    "ins_b_020",
    "reg_b_017",
    "res_b_002",
    "res_b_006",
    "res_b_008",
    "res_b_010",
    "res_b_014",
    "res_b_015",
    "res_b_016",
    "res_b_019",
)


def remaining_accuracy_qids_v38(
    all_qids: tuple[str, ...],
    *,
    primary_qids: tuple[str, ...] = ACCURACY_AUDIT_QIDS_V38,
    residual_qids: tuple[str, ...] = RESIDUAL_ACCURACY_AUDIT_QIDS_V38,
) -> tuple[str, ...]:
    """按官方题序返回尚未进入前两轮裁决的题目。"""
    reviewed = set(primary_qids) | set(residual_qids)
    return tuple(qid for qid in all_qids if qid not in reviewed)


DIRECT_BASIS_TYPES_V38: set[str] = {
    "direct_clause",
    "direct_table",
    "deterministic_calculation",
    "multi_document_entailment",
}


_CALCULATION_FIELDS_V38 = (
    "raw_values",
    "formula",
    "unrounded",
    "rounding",
    "unit",
)


def _complete_calculation_trace(result: dict[str, Any]) -> bool:
    calculation = result.get("calculation")
    if not isinstance(calculation, dict):
        return False
    if any(field not in calculation for field in _CALCULATION_FIELDS_V38):
        return False
    raw_values = calculation.get("raw_values")
    if not isinstance(raw_values, list) or not raw_values:
        return False
    return all(str(calculation[field]).strip() for field in _CALCULATION_FIELDS_V38[1:])


def promote_accuracy_change_v38(
    result: dict[str, Any],
    *,
    current_answers: list[str],
    option_keys: tuple[str, ...],
) -> bool:
    """只有完整正反证据闭环的高置信变更才能进入提交。"""
    if result.get("decision") != "change" or result.get("confidence") != "high":
        return False
    if result.get("basis_type") not in DIRECT_BASIS_TYPES_V38:
        return False
    answers = [str(value).strip() for value in result.get("answers", [])]
    if not answers or answers == [str(value).strip() for value in current_answers]:
        return False

    audits = result.get("option_audit")
    if not isinstance(audits, dict):
        return False
    if any(
        isinstance(audit, dict) and audit.get("verdict") == "insufficient"
        for audit in audits.values()
    ):
        return False

    if option_keys:
        selected = set("".join(answers))
        if not selected or not selected.issubset(set(option_keys)):
            return False
        for key in option_keys:
            audit = audits.get(key)
            expected = "support" if key in selected else "refute"
            if not isinstance(audit, dict) or audit.get("verdict") != expected:
                return False

    if result.get("basis_type") == "deterministic_calculation":
        return _complete_calculation_trace(result)
    return True
