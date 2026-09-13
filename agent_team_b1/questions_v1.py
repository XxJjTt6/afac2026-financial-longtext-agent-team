"""B 榜题目与官方提交模板的独立数据契约。"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal


AnswerKind = Literal["single", "multi", "tf", "freeform"]
ANSWER_COLUMNS = tuple(f"answer_{number}" for number in range(1, 5))
TOKEN_COLUMNS = ("prompt_tokens", "completion_tokens", "total_tokens")
SUBMISSION_COLUMNS = ("qid", *ANSWER_COLUMNS, *TOKEN_COLUMNS)


@dataclass(frozen=True)
class TemplateSpec:
    """官方模板为一道题声明的答案字段数量与格式示例。"""

    qid: str
    expected_answers: int
    examples: tuple[str, ...]


@dataclass(frozen=True)
class BQuestion:
    """不污染 A 榜共享 schema 的 B 榜题目对象。"""

    qid: str
    domain: str
    split: str
    question: str
    type: str
    options: dict[str, str]
    answer_kind: AnswerKind
    expected_answers: int
    template_examples: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def infer_answer_kind(type_name: str, options: dict[str, str]) -> AnswerKind:
    """根据官方中文题型推断作答方式，并拒绝未知的带选项题型。"""
    normalized = type_name.strip()
    mapping: dict[str, AnswerKind] = {
        "单选题": "single",
        "多选题": "multi",
        "判断题": "tf",
        "计算题": "freeform",
        "抽取题": "freeform",
    }
    if normalized in mapping:
        return mapping[normalized]
    if not options:
        return "freeform"
    raise ValueError(f"未知 B 榜题型: {type_name!r}")


def load_template_specs(path: Path) -> list[TemplateSpec]:
    """按官方模板顺序读取每题需要填写的答案字段。"""
    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != SUBMISSION_COLUMNS:
            raise ValueError(f"提交模板表头不匹配: {reader.fieldnames}")
        rows = list(reader)
    if not rows or rows[0].get("qid") != "summary":
        raise ValueError("提交模板首行必须是 summary")

    specs: list[TemplateSpec] = []
    seen: set[str] = set()
    for row in rows[1:]:
        qid = str(row.get("qid", "")).strip()
        if not qid:
            raise ValueError("提交模板包含空 qid")
        if qid in seen:
            raise ValueError(f"提交模板包含重复 qid: {qid}")
        seen.add(qid)
        values = tuple(str(row.get(column, "")).strip() for column in ANSWER_COLUMNS)
        nonempty_indexes = [index for index, value in enumerate(values) if value]
        if not nonempty_indexes or nonempty_indexes != list(range(nonempty_indexes[-1] + 1)):
            raise ValueError(f"{qid} 的答案字段必须从 answer_1 连续填写")
        expected = nonempty_indexes[-1] + 1
        specs.append(TemplateSpec(qid=qid, expected_answers=expected, examples=values[:expected]))
    return specs


def _read_question_file(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("questions"), list):
        return list(data["questions"])
    raise ValueError(f"无法识别题目文件结构: {path}")


def load_b_questions(
    question_root: Path,
    template_path: Path,
    *,
    expected_count: int | None = None,
) -> list[BQuestion]:
    """加载混合 JSON/JSONL B 榜题目，并严格对齐官方模板顺序。"""
    root = Path(question_root)
    paths = sorted([*root.glob("*.json"), *root.glob("*.jsonl")])
    if not paths:
        raise FileNotFoundError(f"未找到 B 榜题目文件: {root}")

    raw_by_qid: dict[str, dict[str, Any]] = {}
    for path in paths:
        for row in _read_question_file(path):
            qid = str(row.get("qid", "")).strip()
            if not qid:
                raise ValueError(f"{path} 包含空 qid")
            if qid in raw_by_qid:
                raise ValueError(f"题目文件包含重复 qid: {qid}")
            raw_by_qid[qid] = row

    specs = load_template_specs(Path(template_path))
    template_ids = [spec.qid for spec in specs]
    missing = sorted(set(template_ids) - set(raw_by_qid))
    extra = sorted(set(raw_by_qid) - set(template_ids))
    if missing or extra:
        raise ValueError(f"题目与模板 qid 不一致: missing={missing}, extra={extra}")
    if expected_count is not None and len(specs) != expected_count:
        raise ValueError(f"B 榜题数应为 {expected_count}，实际为 {len(specs)}")

    spec_by_qid = {spec.qid: spec for spec in specs}
    questions: list[BQuestion] = []
    for qid in template_ids:
        row = raw_by_qid[qid]
        options = {
            str(key).strip().upper(): str(value).strip()
            for key, value in dict(row.get("options") or {}).items()
        }
        spec = spec_by_qid[qid]
        kind = infer_answer_kind(str(row.get("type", "")), options)
        if kind != "freeform" and spec.expected_answers != 1:
            raise ValueError(f"{qid} 为选择题，但模板要求 {spec.expected_answers} 个答案字段")
        questions.append(
            BQuestion(
                qid=qid,
                domain=str(row.get("domain", "")).strip(),
                split=str(row.get("split", "B")).strip(),
                question=str(row.get("question", "")).strip(),
                type=str(row.get("type", "")).strip(),
                options=options,
                answer_kind=kind,
                expected_answers=spec.expected_answers,
                template_examples=spec.examples,
            )
        )
    return questions

