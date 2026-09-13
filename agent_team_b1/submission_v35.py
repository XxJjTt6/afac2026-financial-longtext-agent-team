"""构建 V35 调用内容与最终提交完全一致的 reasoning 版本。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agent.io.jsonl import write_json, write_jsonl
from agent.schemas import TokenUsage
from agent_team_b1.answer_format_v8 import normalize_numeric_grouping
from agent_team_b1.clean_reasoning_v10 import (
    REASONING_SECTIONS,
    official_token_efficiency_score,
)
from agent_team_b1.questions_v1 import load_b_questions, load_template_specs
from agent_team_b1.provenance_reasoning_v35 import (
    normalize_reasoning_conclusion_v35,
    normalize_response_answers_v35,
)
from agent_team_b1.reasoned_submission_v5 import (
    ReasonedSubmissionAnswer,
    validate_reasoned_submission,
    write_reasoned_submission,
)
from agent_team_b1.solver_v1 import extract_model_payload


def _read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_v35_artifacts(
    *,
    source_path: Path,
    expected_answers_path: Path,
    template_path: Path,
    answer_results_path: Path,
    submission_path: Path,
    manifest_path: Path,
) -> dict[str, Any]:
    source_path = Path(source_path)
    expected_answers_path = Path(expected_answers_path)
    template_path = Path(template_path)
    answer_results_path = Path(answer_results_path)
    submission_path = Path(submission_path)
    manifest_path = Path(manifest_path)

    source_rows = _read_rows(source_path)
    expected_rows = _read_rows(expected_answers_path)
    specs = load_template_specs(template_path)
    questions = load_b_questions(
        template_path.parent / "question_b",
        template_path,
        expected_count=100,
    )
    question_by_qid = {question.qid: question for question in questions}
    expected_order = [spec.qid for spec in specs]
    source_by_qid = {str(row.get("qid", "")): row for row in source_rows}
    expected_by_qid = {str(row.get("qid", "")): row for row in expected_rows}
    if len(source_rows) != len(source_by_qid):
        raise ValueError("V35 来源存在重复或空 qid")
    if len(specs) != 100 or set(source_by_qid) != set(expected_order):
        raise ValueError("V35 来源必须与官方模板的100个 qid 完全一致")
    if set(expected_by_qid) != set(expected_order):
        raise ValueError("V35 锁定答案来源必须覆盖官方模板的100个 qid")

    ordered = [source_by_qid[qid] for qid in expected_order]
    answer_change_qids: list[str] = []
    for row in ordered:
        qid = str(row["qid"])
        if row["answers"] != expected_by_qid[qid]["answers"]:
            answer_change_qids.append(qid)
        if row.get("model") != "qwen3.7-plus":
            raise ValueError(f"{qid} 未使用 qwen3.7-plus")

        usage = TokenUsage(**row["token_usage"])
        calls = row.get("calls")
        if not isinstance(calls, list) or len(calls) != 1:
            raise ValueError(f"{qid} 必须且只能保留一次最终内容调用")
        call = calls[0]
        if call.get("token_usage") != usage.to_dict():
            raise ValueError(f"{qid} 的调用 usage 与题目 usage 不一致")

        payload = extract_model_payload(str(call.get("response", "")))
        response_answers = normalize_response_answers_v35(
            question_by_qid[qid],
            payload["answers"],
        )
        response_reasoning = normalize_reasoning_conclusion_v35(
            str(payload.get("reason") or payload.get("reasoning", "")),
            response_answers,
        )
        if response_answers != row["answers"] or response_reasoning != row["reasoning"]:
            raise ValueError(f"{qid} 的最终内容与原始调用响应不一致")

        reasoning = str(row["reasoning"])
        if not 150 <= len(reasoning) <= 350:
            raise ValueError(f"{qid} 的 reasoning 长度不在150至350字")
        positions = [reasoning.find(section) for section in REASONING_SECTIONS]
        if any(position < 0 for position in positions) or positions != sorted(positions):
            raise ValueError(f"{qid} 的 reasoning 四段标签缺失或顺序错误")
        answers_text = "；".join(str(value) for value in row["answers"])
        if answers_text not in reasoning.rsplit("结论", 1)[-1]:
            raise ValueError(f"{qid} 的 reasoning 结论未逐字包含答案")

    if answer_change_qids:
        raise ValueError(f"V35 不得改变 V34 锁定答案: {answer_change_qids}")

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
    if not 1 <= total_tokens <= 499_999:
        raise ValueError(f"V35 必须位于50万Token断点下方: {total_tokens}")

    manifest: dict[str, Any] = {
        "version": "b1_provenance_reasoning_v35",
        "created_at": datetime.now().astimezone().isoformat(),
        "source": str(source_path.resolve()),
        "locked_answers_source": str(expected_answers_path.resolve()),
        "answer_results": str(answer_results_path.resolve()),
        "submission": str(submission_path.resolve()),
        "question_count": len(ordered),
        "answer_change_count": len(answer_change_qids),
        "all_final_content_traced_to_calls": True,
        "deterministic_format_normalization": True,
        "token_usage": token_usage,
        "token_efficiency_score": round(
            official_token_efficiency_score(total_tokens), 6
        ),
        "validation": validation,
        "sha256": {
            "source": _sha256(source_path),
            "locked_answers_source": _sha256(expected_answers_path),
            "answer_results": _sha256(answer_results_path),
            "submission": _sha256(submission_path),
        },
    }
    write_json(manifest_path, manifest)
    return manifest
