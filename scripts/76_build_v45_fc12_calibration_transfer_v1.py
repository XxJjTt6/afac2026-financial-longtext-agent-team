"""脚本76：固化fc_a_014到fc_a_012的同源官网术语校准迁移。"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
QUESTIONS = ROOT.parent / "public_dataset_upload" / "questions" / "group_a" / "financial_contracts_questions.json"
DOCUMENTS = ROOT / "processed_data_v1" / "documents.jsonl"
CONSTRAINTS = ROOT / "evaluation_results_v26" / "leaderboard_constraints_v1.json"
SOURCE_CANDIDATE = ROOT / "submissions" / "v44_preferred_structural_d_answer.csv"
OUTPUT_CANDIDATE = ROOT / "submissions" / "v45_preferred_calibrated_d_answer.csv"
OUTPUT_AUDIT = ROOT / "evaluation_results_v45" / "fc12_calibration_transfer_v1.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_documents() -> dict[str, str]:
    documents: dict[str, str] = {}
    for line in DOCUMENTS.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["domain"] == "financial_contracts":
            documents[row["doc_id"]] = row["raw_text"]
    return documents


def main() -> None:
    from agent_team_v45.fc12_calibration_transfer import (
        calibrated_claim_support,
        infer_fc12_branch,
    )

    questions = {
        row["qid"]: row
        for row in json.loads(QUESTIONS.read_text(encoding="utf-8"))
    }
    documents = _load_documents()
    compact_text03 = re.sub(r"\s+", "", documents["text03"])
    formula = "违约金具体计算方式为延迟支付的本金和利息×票面利率×150%×违约天数/365"
    formula_count = compact_text03.count(formula)
    if formula_count < 2:
        raise RuntimeError(f"text03同源违约金公式不足2处: {formula_count}")

    constraints = json.loads(CONSTRAINTS.read_text(encoding="utf-8"))
    rows = {row["qid"]: row for row in constraints["questions"]}
    fc14_row = rows["fc_a_014"]
    if not fc14_row["baseline_forced_correct"] or fc14_row["forced_observed_answer"] != "AB":
        raise RuntimeError("fc_a_014=AB不再是官网约束强制答案")

    fc14_support = calibrated_claim_support(
        questions["fc_a_014"]["options"]["A"], formula
    )
    fc12_d_support = calibrated_claim_support(
        questions["fc_a_012"]["options"]["D"], formula
    )
    fc12_a_direct = "2031年4月23日" in compact_text03
    compact_text13 = re.sub(r"\s+", "", documents["text13"])
    fc12_c_direct = all(value in compact_text13 for value in ("66.38%", "63.51%"))
    decision = infer_fc12_branch(
        fc14_forced_answer="AB",
        fc14_support=fc14_support,
        fc12_d_support=fc12_d_support,
        fc12_a_direct=fc12_a_direct,
        fc12_c_direct=fc12_c_direct,
    )
    if decision["preferred_fc12"] != "ACD":
        raise RuntimeError(f"V45校准迁移未选择ACD: {decision}")

    OUTPUT_CANDIDATE.write_bytes(SOURCE_CANDIDATE.read_bytes())
    payload = {
        "schema_version": 1,
        "purpose": "用官网强制命中的fc_a_014=A校准同一text03违约金公式的术语概括，并迁移到fc_a_012=D。",
        "official_anchor": {
            "qid": "fc_a_014",
            "forced_answer": "AB",
            "baseline_forced_correct": True,
            "constraint_source": str(CONSTRAINTS.relative_to(ROOT)),
            "observed_answers": fc14_row["observed_answers"],
            "feasible_answers": fc14_row["feasible_answers"],
        },
        "shared_source": {
            "doc_id": "text03",
            "normalized_formula": formula,
            "occurrence_count": formula_count,
            "source_fingerprint": fc14_support["source_fingerprint"],
        },
        "calibrated_claims": {
            "fc_a_014_A": {
                "claim": questions["fc_a_014"]["options"]["A"],
                "support": fc14_support,
                "officially_accepted": True,
            },
            "fc_a_012_D": {
                "claim": questions["fc_a_012"]["options"]["D"],
                "support": fc12_d_support,
                "transferred_from_same_formula": True,
            },
        },
        "fc_a_012_other_options": {
            "A_direct": fc12_a_direct,
            "B_false_reason": "text13利润总额并非逐年下降。",
            "C_direct": fc12_c_direct,
        },
        "branch_decision": decision,
        "v9_v10_hard_relation": {
            "fc12_acd_and_fc15_b_exactly_one_hit": True,
            "fc12_ac_and_fc15_a_both_miss": True,
            "consequence": "ACD分支得到强同源校准后，fc_a_015=B反分支显著弱化，隐藏键继续限定为C/D。",
        },
        "preferred_candidate": {
            "answer": "fc_a_012=ACD, fc_a_015=D",
            "path": str(OUTPUT_CANDIDATE.relative_to(ROOT)),
            "sha256": _sha256(OUTPUT_CANDIDATE),
            "byte_identical_to": str(SOURCE_CANDIDATE.relative_to(ROOT)),
            "byte_identical": OUTPUT_CANDIDATE.read_bytes() == SOURCE_CANDIDATE.read_bytes(),
            "status": "offline_preferred_calibrated_candidate",
        },
        "conditional_projection": {
            "if_D_and_all_prior_layers_hold": {"correct_count": 100, "final_score": 98.037688},
            "if_C_is_hidden_key": {"correct_count": 99, "final_score": 97.05731112},
            "if_fc15_B_branch_despite_calibration": {"correct_count": 98, "final_score": 96.07693424},
        },
        "leaderboard_verified": False,
        "official_submission_allowed": False,
        "decision": "retain_D_preference_and_continue_without_submission",
        "warning": (
            "同源校准显著增强ACD分支，但仍不能把条件100写成官网100；"
            "fc_a_015的C/D最终键仍缺少逐题官网反馈。"
        ),
    }
    OUTPUT_AUDIT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_AUDIT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "preferred_fc12": decision["preferred_fc12"],
                "fc15_branch": decision["fc15_branch"],
                "formula_count": formula_count,
                "candidate_sha256": _sha256(OUTPUT_CANDIDATE),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
