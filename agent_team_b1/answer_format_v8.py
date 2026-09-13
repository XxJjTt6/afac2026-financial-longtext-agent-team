"""最终提交前的非语义数值表示规范化。"""

from __future__ import annotations

import re


GROUPED_NUMBER = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?$")


def normalize_numeric_grouping(value: str) -> str:
    """仅移除纯数字答案的千分位逗号，不改变语义文本。"""
    stripped = str(value).strip()
    return stripped.replace(",", "") if GROUPED_NUMBER.fullmatch(stripped) else stripped
