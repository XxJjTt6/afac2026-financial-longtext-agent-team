"""证据约束的 B 榜首轮求解与独立复核。"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from agent.schemas import RetrievalResult, TokenUsage
from agent_team_b1.questions_v1 import BQuestion
from agent_team_b1.submission_v1 import normalize_answers


class _Retriever(Protocol):
    def retrieve(
        self,
        question: BQuestion,
        restrict_to_doc_ids: bool = True,
    ) -> list[RetrievalResult]: ...


class _LLM(Protocol):
    def chat(self, messages: list[dict[str, str]], **kwargs: Any): ...


@dataclass
class B1AnswerResult:
    qid: str
    answers: list[str]
    confidence: float
    reason: str
    doc_ids: list[str]
    evidence: list[RetrievalResult]
    token_usage: TokenUsage
    reviewed: bool
    risk_flags: list[str] = field(default_factory=list)
    raw_responses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = [item.to_dict() for item in self.evidence]
        data["token_usage"] = self.token_usage.to_dict()
        return data


def extract_model_payload(text: str) -> dict[str, Any]:
    """从纯 JSON、Markdown 代码块或带说明的响应中提取首个 JSON 对象。"""
    candidates = [text.strip()]
    candidates.extend(re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.I | re.S))
    decoder = json.JSONDecoder()
    for candidate in candidates:
        for match in re.finditer(r"\{", candidate):
            try:
                payload, _ = decoder.raw_decode(candidate[match.start() :])
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            answers = payload.get("answers", payload.get("answer"))
            if isinstance(answers, str) or not isinstance(answers, list):
                answers = [answers]
            payload["answers"] = [str(value) for value in answers if value is not None]
            try:
                payload["confidence"] = float(payload.get("confidence", 0.0) or 0.0)
            except (TypeError, ValueError):
                payload["confidence"] = 0.0
            payload["reason"] = str(payload.get("reason", "")).strip()
            raw_doc_ids = payload.get("doc_ids") or []
            if isinstance(raw_doc_ids, str):
                raw_doc_ids = [raw_doc_ids]
            payload["doc_ids"] = [str(value).strip() for value in raw_doc_ids if str(value).strip()]
            return payload
    raise ValueError("模型响应中没有可解析的 JSON 对象")


def _format_requirements(question: BQuestion) -> str:
    common = (
        f"answers 数组必须恰好包含 {question.expected_answers} 个元素。"
        "不要把解释、单位说明或引用混入 answers。"
    )
    if question.answer_kind != "freeform":
        return (
            common
            + "只填写大写选项字母；多选按 A、B、C、D 顺序连续书写，不加分隔符。"
            + "多选题可能只有一个正确选项，也可能有多个，必须逐项依据证据判断。"
        )
    return (
        common
        + "严格按题目顺序填写多个答案。数字、百分数、日期、排序和文本遵守题目要求；"
        + "百分数保留要求的小数位并带%，日期写作 YYYY年M月D日，排序使用英文半角 > 且两侧无空格。"
    )


def _evidence_text(evidence: list[RetrievalResult], max_chars: int) -> str:
    blocks: list[str] = []
    used = 0
    for number, item in enumerate(evidence, start=1):
        page = item.metadata.get("page", "")
        section = item.metadata.get("section", "")
        header = f"[证据{number}] doc_id={item.doc_id}; page={page}; section={section}; score={item.score:.4f}"
        block = f"{header}\n{item.evidence_text.strip()}"
        if blocks and used + len(block) > max_chars:
            break
        blocks.append(block)
        used += len(block)
    return "\n\n".join(blocks)


def build_messages(
    question: BQuestion,
    evidence: list[RetrievalResult],
    *,
    review: bool,
    prior: dict[str, Any] | None = None,
    max_evidence_chars: int = 28000,
) -> list[dict[str, str]]:
    """构建只允许依据官方证据、且输出结构可机器校验的提示。"""
    options = "\n".join(f"{key}. {value}" for key, value in question.options.items()) or "（无选项）"
    review_instruction = ""
    if review:
        review_instruction = (
            "\n这是独立复核轮。上一轮结果如下：\n"
            + json.dumps(prior or {}, ensure_ascii=False)
            + "\n不要默认上一轮正确。请重新核对每个选项或每个原始数值；如冲突，以官方证据和可复算公式为准。"
        )
    system = (
        "你是金融文档证据核验专家。只能依据用户提供的官方材料证据作答，不得凭常识补全。"
        "先在内部逐项核对；最终只输出一个合法 JSON 对象，不要输出 Markdown。"
        "JSON 结构固定为："
        '{"answers":["答案"],"confidence":0.0,"reason":"简明但可复核的依据或计算式",'
        '"doc_ids":["实际使用的doc_id"]}。'
    )
    user = (
        f"qid: {question.qid}\n领域: {question.domain}\n题型: {question.type}\n"
        f"问题: {question.question}\n选项:\n{options}\n\n"
        f"输出要求: {_format_requirements(question)}"
        f"{review_instruction}\n\n官方材料检索证据:\n{_evidence_text(evidence, max_evidence_chars)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def risk_flags(
    question: BQuestion,
    answers: list[str],
    confidence: float,
    reason: str,
    doc_ids: list[str],
) -> list[str]:
    flags: list[str] = []
    if question.answer_kind == "freeform":
        flags.append("freeform_requires_review")
    if confidence < 0.8:
        flags.append("low_confidence")
    if len(reason) < 20:
        flags.append("weak_explanation")
    if not doc_ids:
        flags.append("missing_doc_ids")
    if len(answers) != question.expected_answers:
        flags.append("answer_count_mismatch")
    cross_markers = ("分别", "两份", "三份", "各文件", "排序", "比较", "两次")
    if any(marker in question.question for marker in cross_markers):
        flags.append("cross_source_or_order_sensitive")
    return flags


class B1Solver:
    """单题先求解、后按风险或全量策略进行证据复核。"""

    def __init__(
        self,
        retriever: _Retriever,
        llm: _LLM,
        *,
        review_all: bool = True,
        max_correction_calls: int = 1,
        max_evidence_chars: int = 28000,
        max_tokens: int = 1800,
    ) -> None:
        self.retriever = retriever
        self.llm = llm
        self.review_all = review_all
        self.max_correction_calls = max_correction_calls
        self.max_evidence_chars = max_evidence_chars
        self.max_tokens = max_tokens

    def _call(
        self,
        question: BQuestion,
        evidence: list[RetrievalResult],
        *,
        review: bool,
        prior: dict[str, Any] | None = None,
    ):
        return self.llm.chat(
            build_messages(
                question,
                evidence,
                review=review,
                prior=prior,
                max_evidence_chars=self.max_evidence_chars,
            ),
            temperature=0.0,
            max_tokens=self.max_tokens,
            enable_thinking=True,
        )

    @staticmethod
    def _candidate(question: BQuestion, text: str) -> dict[str, Any]:
        payload = extract_model_payload(text)
        payload["answers"] = normalize_answers(question, payload["answers"])
        return payload

    def solve(self, question: BQuestion) -> B1AnswerResult:
        evidence = self.retriever.retrieve(question, restrict_to_doc_ids=False)
        if not evidence:
            raise ValueError(f"{question.qid} 未检索到任何官方证据")

        usage = TokenUsage()
        raw_responses: list[str] = []
        response = self._call(question, evidence, review=False)
        usage.add(response.usage)
        raw_responses.append(response.text)
        try:
            candidate = self._candidate(question, response.text)
        except ValueError as exc:
            last_error = exc
            candidate = None
            for _ in range(self.max_correction_calls):
                repair = self._call(
                    question,
                    evidence,
                    review=True,
                    prior={"invalid_response": response.text, "validation_error": str(last_error)},
                )
                usage.add(repair.usage)
                raw_responses.append(repair.text)
                try:
                    candidate = self._candidate(question, repair.text)
                    break
                except ValueError as repair_error:
                    last_error = repair_error
            if candidate is None:
                raise last_error

        flags = risk_flags(
            question,
            candidate["answers"],
            candidate["confidence"],
            candidate["reason"],
            candidate["doc_ids"],
        )
        reviewed = False
        review_fallback = False
        if self.review_all or flags:
            review = self._call(question, evidence, review=True, prior=candidate)
            usage.add(review.usage)
            raw_responses.append(review.text)
            reviewed = True
            try:
                reviewed_candidate = self._candidate(question, review.text)
            except ValueError as exc:
                reviewed_candidate = None
                last_error = exc
                for _ in range(self.max_correction_calls):
                    repair = self._call(
                        question,
                        evidence,
                        review=True,
                        prior={
                            "last_valid_candidate": candidate,
                            "invalid_review": review.text,
                            "validation_error": str(last_error),
                        },
                    )
                    usage.add(repair.usage)
                    raw_responses.append(repair.text)
                    try:
                        reviewed_candidate = self._candidate(question, repair.text)
                        break
                    except ValueError as repair_error:
                        last_error = repair_error
                if reviewed_candidate is None:
                    review_fallback = True
            if reviewed_candidate is not None:
                candidate = reviewed_candidate
            flags = risk_flags(
                question,
                candidate["answers"],
                candidate["confidence"],
                candidate["reason"],
                candidate["doc_ids"],
            )
            if review_fallback:
                flags.append("invalid_review_fell_back_to_first_pass")

        return B1AnswerResult(
            qid=question.qid,
            answers=candidate["answers"],
            confidence=candidate["confidence"],
            reason=candidate["reason"],
            doc_ids=candidate["doc_ids"],
            evidence=evidence,
            token_usage=usage,
            reviewed=reviewed,
            risk_flags=flags,
            raw_responses=raw_responses,
        )
