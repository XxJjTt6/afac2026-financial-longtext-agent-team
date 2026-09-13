"""合并 B1 基线、完整索引复核、分歧裁决和确定性复算结果。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


TOKEN_COLUMNS = ("prompt_tokens", "completion_tokens", "total_tokens")


def merge_result_layers(
    base: dict[str, Any],
    *,
    audit: dict[str, Any] | None = None,
    jury: dict[str, Any] | None = None,
    deterministic_override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """答案取最新可信层，Token 和原始响应则累计所有真实调用。"""
    layers: list[tuple[str, dict[str, Any]]] = [("base", base)]
    if audit is not None:
        layers.append(("complete_index_audit", audit))
    if jury is not None:
        layers.append(("jury", jury))

    merged = deepcopy(layers[-1][1])
    usage = {column: 0 for column in TOKEN_COLUMNS}
    raw_responses: list[str] = []
    for _, row in layers:
        row_usage = row.get("token_usage") or {}
        for column in TOKEN_COLUMNS:
            usage[column] += int(row_usage.get(column, 0) or 0)
        raw_responses.extend(str(value) for value in row.get("raw_responses", []))
    if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
        raise ValueError(f"{base.get('qid')} 的多层 Token 不守恒")

    merged["token_usage"] = usage
    merged["raw_responses"] = raw_responses
    layer_names = [name for name, _ in layers]
    if deterministic_override is not None:
        for key in ("answers", "reason", "doc_ids", "confidence"):
            if key in deterministic_override:
                merged[key] = deepcopy(deterministic_override[key])
        layer_names.append("deterministic_override")
    metadata = dict(merged.get("metadata") or {})
    metadata["result_layers"] = layer_names
    merged["metadata"] = metadata
    return merged
