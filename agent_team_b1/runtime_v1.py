"""B1 长任务的并发、重试和进程级调用预算配置。"""

from __future__ import annotations

import math
from dataclasses import replace

from agent.config import Settings


def configure_b1_settings(
    settings: Settings,
    *,
    question_count: int,
    workers: int,
    review_all: bool,
    max_correction_calls: int,
) -> Settings:
    """按最坏调用路径放宽进程配额，避免全量任务在中途自我熔断。"""
    worker_count = max(1, workers)
    retries = max(settings.max_retries, 4)
    calls_per_question = 1 + int(review_all) + max(0, max_correction_calls)
    logical_calls = max(1, question_count) * calls_per_question
    attempt_budget = math.ceil(logical_calls * 1.1) * (retries + 1)
    return replace(
        settings,
        question_workers=worker_count,
        qwen_workers=max(1, min(worker_count, 3)),
        qwen_request_limit=max(settings.qwen_request_limit, attempt_budget),
        request_timeout_seconds=max(settings.request_timeout_seconds, 180),
        max_retries=retries,
        answer_max_tokens=max(settings.answer_max_tokens, 1800),
    )
