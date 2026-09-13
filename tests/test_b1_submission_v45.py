import csv
import json
from pathlib import Path

from agent_team_b1.submission_v45 import build_v45_artifacts


ROOT = Path(__file__).resolve().parents[1]


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_v45_replaces_only_fin14_with_the_unrounded_qwen_row(tmp_path: Path) -> None:
    answer_results = tmp_path / "answer_results.jsonl"
    submission = tmp_path / "answer.csv"
    manifest_path = tmp_path / "manifest.json"

    manifest = build_v45_artifacts(
        v42_results_path=(
            ROOT
            / "evaluation_results_b1_v42_raw_pdf_accuracy_recovery"
            / "answer_results.jsonl"
        ),
        fin14_correction_path=(
            ROOT
            / "evaluation_results_b1_v45_fin14_unrounded"
            / "answer_result.json"
        ),
        template_path=ROOT / "upload_b" / "submit.csv",
        answer_results_path=answer_results,
        submission_path=submission,
        manifest_path=manifest_path,
    )

    old_rows = {
        row["qid"]: row
        for row in _read_jsonl(
            ROOT
            / "evaluation_results_b1_v42_raw_pdf_accuracy_recovery"
            / "answer_results.jsonl"
        )
    }
    new_rows = {row["qid"]: row for row in _read_jsonl(answer_results)}

    assert {qid for qid in new_rows if new_rows[qid] != old_rows[qid]} == {
        "fin_b_014"
    }
    assert new_rows["fin_b_014"]["answers"] == ["1.12", "9.82", "8.69"]
    assert new_rows["fin_b_014"]["token_usage"]["total_tokens"] == 966
    assert manifest["answer_change_vs_v42"] == {
        "fin_b_014": {"before": ["1.12", "9.82", "8.70"], "after": ["1.12", "9.82", "8.69"]}
    }
    assert manifest["token_usage"]["total_tokens"] == 498_816

    with submission.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_qid = {row["qid"]: row for row in rows}
    assert by_qid["summary"]["total_tokens"] == "498816"
    assert by_qid["fin_b_014"]["answer_1"] == "1.12"
    assert by_qid["fin_b_014"]["answer_2"] == "9.82"
    assert by_qid["fin_b_014"]["answer_3"] == "8.69"
    assert "8.694991" in by_qid["fin_b_014"]["reasoning"]
