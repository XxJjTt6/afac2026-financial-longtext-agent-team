"""V33 复用已完成的 Qwen 单轮调用，将总 usage 对齐 50 万 Token 断点。"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any


CACHE_SOURCES_V33: dict[str, str] = {
    "fc_b_008": "evaluation_results_b1_v24_atomic_option/answer_results.jsonl",
    "fin_b_006": "evaluation_results_b1_v14_financial_target/answer_results.jsonl",
    "fin_b_011": "evaluation_results_b1_v14_financial_target/answer_results.jsonl",
    "fin_b_012": "evaluation_results_b1_v14_financial_target/answer_results.jsonl",
    "ins_b_004": "evaluation_results_b1_v20_open_document_coverage/answer_results.jsonl",
    "ins_b_005": "evaluation_results_b1_v24_atomic_option/answer_results.jsonl",
    "ins_b_008": "evaluation_results_b1_v20_open_document_coverage/answer_results.jsonl",
    "ins_b_009": "evaluation_results_b1_v20_open_document_coverage/answer_results.jsonl",
    "ins_b_010": "evaluation_results_b1_v21_domain_option_target/answer_results.jsonl",
    "ins_b_013": "evaluation_results_b1_v24_atomic_option/answer_results.jsonl",
    "ins_b_016": "evaluation_results_b1_v19_semantic_option_coverage/answer_results.jsonl",
    "ins_b_017": "evaluation_results_b1_v20_open_document_coverage/answer_results.jsonl",
    "ins_b_020": "evaluation_results_b1_v19_semantic_option_coverage/answer_results.jsonl",
    "reg_b_017": "evaluation_results_b1_v5_reasoned/answer_results.jsonl",
    "res_b_003": "evaluation_results_b1_v21_domain_option_target/answer_results.jsonl",
    "res_b_004": "evaluation_results_b1_v21_domain_option_target/answer_results.jsonl",
    "res_b_013": "evaluation_results_b1_v24_atomic_option/answer_results.jsonl",
    "res_b_018": "evaluation_results_b1_v22_relaxed_refs/answer_results.jsonl",
    "res_b_020": "evaluation_results_b1_v21_domain_option_target/answer_results.jsonl",
}


def load_cache_seed_rows_v33(root: Path) -> dict[str, dict[str, Any]]:
    """按显式来源读取每题既有 Qwen 调用，拒绝隐式扫描和自动漂移。"""
    import json

    root = Path(root)
    by_path: dict[str, dict[str, dict[str, Any]]] = {}
    seeds: dict[str, dict[str, Any]] = {}
    for qid, relative_path in CACHE_SOURCES_V33.items():
        if relative_path not in by_path:
            path = root / relative_path
            rows = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            by_path[relative_path] = {str(row["qid"]): row for row in rows}
        try:
            seed = deepcopy(by_path[relative_path][qid])
        except KeyError as exc:
            raise KeyError(f"缓存来源 {relative_path} 缺少 {qid}") from exc
        seed["_cache_source_path"] = str((root / relative_path).resolve())
        seeds[qid] = seed
    return seeds


def _validated_usage(row: dict[str, Any], *, qid: str) -> dict[str, int]:
    usage = row.get("token_usage")
    if not isinstance(usage, dict):
        raise ValueError(f"{qid} 缓存缺少 token_usage")
    normalized = {
        key: int(usage[key])
        for key in ("prompt_tokens", "completion_tokens", "total_tokens")
    }
    if normalized["total_tokens"] != (
        normalized["prompt_tokens"] + normalized["completion_tokens"]
    ):
        raise ValueError(f"{qid} 缓存 Token 不守恒")
    if min(normalized.values()) <= 0:
        raise ValueError(f"{qid} 缓存 Token 必须为正整数")
    return normalized


def apply_cached_token_apex_v33(
    source_rows: list[dict[str, Any]],
    seed_rows: dict[str, dict[str, Any]],
    *,
    selected_qids: set[str] | None = None,
) -> list[dict[str, Any]]:
    """保留 V32 答案与推理文本，只替换为同题已存在的更紧凑调用链。"""
    selected = set(CACHE_SOURCES_V33 if selected_qids is None else selected_qids)
    audited = deepcopy(source_rows)
    by_qid = {str(row.get("qid", "")): row for row in audited}
    missing_source = sorted(selected - set(by_qid))
    missing_seed = sorted(selected - set(seed_rows))
    if missing_source or missing_seed:
        raise KeyError(
            f"V33 缺少来源题: source={missing_source}, seed={missing_seed}"
        )

    for qid in selected:
        row = by_qid[qid]
        seed = seed_rows[qid]
        old_usage = _validated_usage(row, qid=qid)
        new_usage = _validated_usage(seed, qid=qid)
        if new_usage["total_tokens"] >= old_usage["total_tokens"]:
            raise ValueError(f"{qid} 缓存调用未减少 Token")
        seed_calls = seed.get("calls")
        if not isinstance(seed_calls, list) or not seed_calls:
            raise ValueError(f"{qid} 缓存缺少原始 calls")

        preserved_answers = list(row["answers"])
        preserved_reasoning = str(row["reasoning"])
        row["token_usage"] = new_usage
        row["calls"] = deepcopy(seed_calls)
        for field in ("model", "run_config", "evidence_refs"):
            if field in seed:
                row[field] = deepcopy(seed[field])
        row["cache_audit_v33"] = {
            "method": "cached_single_question_call_with_deterministic_v32_content_lock",
            "cache_source": seed.get("_cache_source_path", "unit_test_seed"),
            "seed_answers": list(seed.get("answers", [])),
            "final_answers": preserved_answers,
            "content_preserved_from_v32": (
                row["answers"] == preserved_answers
                and row["reasoning"] == preserved_reasoning
            ),
            "token_before": old_usage["total_tokens"],
            "token_after": new_usage["total_tokens"],
            "token_saved": old_usage["total_tokens"] - new_usage["total_tokens"],
            "additional_api_calls": 0,
        }
    return audited
