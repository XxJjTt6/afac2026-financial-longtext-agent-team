"""B 榜答案规范化、CSV 生成与严格离线验证。"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

from agent.schemas import TokenUsage
from agent_team_b1.questions_v1 import (
    ANSWER_COLUMNS,
    SUBMISSION_COLUMNS,
    TOKEN_COLUMNS,
    BQuestion,
    load_template_specs,
)


PLACEHOLDERS = {
    "999999.99",
    "999999.99%",
    "公司名称>公司名称",
}


@dataclass(frozen=True)
class SubmissionAnswer:
    qid: str
    answers: list[str]
    token_usage: TokenUsage


def normalize_answers(question: BQuestion, raw_answers: list[object]) -> list[str]:
    """规范化模型答案；只修正表示法，不改动答案的语义值。"""
    values = [str(value).strip() for value in raw_answers if value is not None]
    if question.answer_kind != "freeform":
        combined = "".join(values).upper()
        letters = re.findall(r"[A-Z]", combined)
        allowed = set(question.options)
        illegal = sorted(set(letters) - allowed)
        if illegal:
            raise ValueError(f"{question.qid} 包含非法选项: {illegal}")
        answer = "".join(sorted(set(letters)))
        if not answer:
            raise ValueError(f"{question.qid} 选择题答案为空")
        return [answer]

    if len(values) != question.expected_answers:
        raise ValueError(
            f"{question.qid} 答案字段数应为 {question.expected_answers}，实际为 {len(values)}"
        )
    normalized: list[str] = []
    decimal_places = 1 if "保留一位小数" in question.question else 2
    quantum = Decimal("1").scaleb(-decimal_places)
    for index, value in enumerate(values):
        cleaned = value.replace("％", "%").replace("＞", ">")
        cleaned = re.sub(r"\s*>\s*", ">", cleaned).strip()
        if not cleaned:
            raise ValueError(f"{question.qid} 包含空答案字段")
        if cleaned in PLACEHOLDERS:
            raise ValueError(f"{question.qid} 仍包含官方占位符: {cleaned}")
        example = question.template_examples[index]
        numeric_match = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)(%)?", cleaned)
        if numeric_match and (
            example.startswith("999999.99")
            or numeric_match.group(2) == "%"
        ):
            try:
                number = Decimal(numeric_match.group(1)).quantize(quantum, rounding=ROUND_HALF_UP)
            except InvalidOperation as exc:
                raise ValueError(f"{question.qid} 数字格式非法: {cleaned!r}") from exc
            suffix = "%" if numeric_match.group(2) else ""
            cleaned = f"{number:.{decimal_places}f}{suffix}"
        normalized.append(cleaned)
    return normalized


def write_b_submission(
    template_path: Path,
    output_path: Path,
    answers: dict[str, SubmissionAnswer],
) -> None:
    """沿用官方模板顺序写入答案，并由真实逐题 usage 计算 summary。"""
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
        row: dict[str, str | int] = {column: "" for column in SUBMISSION_COLUMNS}
        row["qid"] = spec.qid
        for index, value in enumerate(answer.answers):
            row[ANSWER_COLUMNS[index]] = value
        row.update(answer.token_usage.to_dict())
        rows.append(row)

    summary: dict[str, str | int] = {column: "" for column in SUBMISSION_COLUMNS}
    summary["qid"] = "summary"
    summary.update(total.to_dict())
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUBMISSION_COLUMNS)
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


def validate_submission(template_path: Path, submission_path: Path) -> dict[str, object]:
    """验证 B 榜 CSV 的行序、答案完整性、占位符和两级 Token 守恒。"""
    specs = load_template_specs(Path(template_path))
    with Path(submission_path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SUBMISSION_COLUMNS:
            raise ValueError(f"提交文件表头不匹配: {reader.fieldnames}")
        rows = list(reader)
    if len(rows) != len(specs) + 1 or not rows or rows[0].get("qid") != "summary":
        raise ValueError("提交文件必须包含首行 summary 和全部题目")

    expected_order = [spec.qid for spec in specs]
    actual_order = [str(row.get("qid", "")) for row in rows[1:]]
    if actual_order != expected_order:
        raise ValueError("提交题目顺序或 qid 与官方模板不一致")

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
        accumulated.add(_parse_usage(row, spec.qid))

    summary = _parse_usage(rows[0], "summary")
    if summary.to_dict() != accumulated.to_dict():
        raise ValueError("summary Token 与逐题汇总不一致")
    return {
        "question_count": len(specs),
        "token_usage": summary.to_dict(),
        "qid_order_sha_input": "\n".join(expected_order),
    }
