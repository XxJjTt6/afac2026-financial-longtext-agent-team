"""B 榜补充规则要求的 reasoning CSV 生成与离线验证。"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from agent.schemas import TokenUsage
from agent_team_b1.questions_v1 import ANSWER_COLUMNS, TOKEN_COLUMNS, load_template_specs
from agent_team_b1.submission_v1 import PLACEHOLDERS


REASONED_SUBMISSION_COLUMNS = ("qid", *ANSWER_COLUMNS, *TOKEN_COLUMNS, "reasoning")


@dataclass(frozen=True)
class ReasonedSubmissionAnswer:
    qid: str
    answers: list[str]
    reasoning: str
    token_usage: TokenUsage


def write_reasoned_submission(
    template_path: Path,
    output_path: Path,
    answers: dict[str, ReasonedSubmissionAnswer],
) -> None:
    """沿用官方题序，新增 reasoning 并从逐题 API usage 汇总 summary。"""
    specs = load_template_specs(Path(template_path))
    expected_ids = [spec.qid for spec in specs]
    missing = sorted(set(expected_ids) - set(answers))
    extra = sorted(set(answers) - set(expected_ids))
    if missing or extra:
        raise ValueError(f"答案与模板 qid 不一致: missing={missing}, extra={extra}")

    total = TokenUsage()
    rows: list[dict[str, str | int]] = []
    for spec in specs:
        answer = answers[spec.qid]
        if len(answer.answers) != spec.expected_answers:
            raise ValueError(
                f"{spec.qid} 答案字段数应为 {spec.expected_answers}，实际为 {len(answer.answers)}"
            )
        total.add(answer.token_usage)
        row: dict[str, str | int] = {column: "" for column in REASONED_SUBMISSION_COLUMNS}
        row["qid"] = spec.qid
        for index, value in enumerate(answer.answers):
            row[ANSWER_COLUMNS[index]] = value
        row.update(answer.token_usage.to_dict())
        row["reasoning"] = answer.reasoning.strip()
        rows.append(row)

    summary: dict[str, str | int] = {column: "" for column in REASONED_SUBMISSION_COLUMNS}
    summary["qid"] = "summary"
    summary.update(total.to_dict())
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REASONED_SUBMISSION_COLUMNS)
        writer.writeheader()
        writer.writerow(summary)
        writer.writerows(rows)


def _parse_usage(row: dict[str, str], qid: str) -> TokenUsage:
    values: dict[str, int] = {}
    for column in TOKEN_COLUMNS:
        raw = str(row.get(column, "")).strip()
        if not raw.isdigit():
            raise ValueError(f"{qid} 的 {column} 不是非负整数: {raw!r}")
        values[column] = int(raw)
    if values["total_tokens"] != values["prompt_tokens"] + values["completion_tokens"]:
        raise ValueError(f"{qid} 的 Token 不守恒")
    return TokenUsage(**values)


def validate_reasoned_submission(template_path: Path, submission_path: Path) -> dict[str, object]:
    """按最新 B 榜补充说明校验必要字段、推理摘要和 Token 守恒。"""
    specs = load_template_specs(Path(template_path))
    with Path(submission_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != REASONED_SUBMISSION_COLUMNS:
            raise ValueError(f"提交文件表头不匹配: {reader.fieldnames}")
        rows = list(reader)
    if len(rows) != len(specs) + 1 or not rows or rows[0].get("qid") != "summary":
        raise ValueError("提交文件必须包含首行 summary 和全部题目")

    expected_order = [spec.qid for spec in specs]
    actual_order = [str(row.get("qid", "")) for row in rows[1:]]
    if actual_order != expected_order:
        raise ValueError("提交题目顺序或 qid 与官方模板不一致")
    if str(rows[0].get("reasoning", "")).strip():
        raise ValueError("summary 行的 reasoning 应留空")

    accumulated = TokenUsage()
    for spec, row in zip(specs, rows[1:], strict=True):
        values = [str(row.get(column, "")).strip() for column in ANSWER_COLUMNS]
        required = values[: spec.expected_answers]
        unused = values[spec.expected_answers :]
        if any(not value for value in required):
            raise ValueError(f"{spec.qid} 存在空必填答案")
        if any(unused):
            raise ValueError(f"{spec.qid} 填写了模板未使用的答案字段")
        if any(value in PLACEHOLDERS or value.startswith("999999.99") for value in required):
            raise ValueError(f"{spec.qid} 包含占位符")
        if spec.examples == ("A",) and not re.fullmatch(r"[A-D]+", required[0]):
            raise ValueError(f"{spec.qid} 的选择题答案格式非法: {required[0]!r}")
        reasoning = str(row.get("reasoning", "")).strip()
        if len(reasoning) < 20:
            raise ValueError(f"{spec.qid} 的 reasoning 少于 20 字")
        if len(reasoning) > 1000:
            raise ValueError(f"{spec.qid} 的 reasoning 过长")
        usage = _parse_usage(row, spec.qid)
        if usage.prompt_tokens <= 0 or usage.completion_tokens <= 0:
            raise ValueError(f"{spec.qid} 的 Token usage 不能为 0")
        accumulated.add(usage)

    summary = _parse_usage(rows[0], "summary")
    if summary.to_dict() != accumulated.to_dict():
        raise ValueError("summary Token 与逐题汇总不一致")
    return {
        "question_count": len(specs),
        "token_usage": summary.to_dict(),
        "reasoning_min_chars": min(len(str(row["reasoning"]).strip()) for row in rows[1:]),
        "reasoning_max_chars": max(len(str(row["reasoning"]).strip()) for row in rows[1:]),
    }
