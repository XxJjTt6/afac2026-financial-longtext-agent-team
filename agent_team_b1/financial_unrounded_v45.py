"""V45用年报原始金额修复禁止中间舍入的计算题。"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import re
import subprocess
from typing import Any


_TWO_DECIMALS = Decimal("0.01")

_BYD_2024 = {
    "revenue": Decimal("777102455000"),
    "net_profit": Decimal("40254346000"),
    "operating_cash_flow": Decimal("133453873000"),
}

_BYD_2025 = {
    "revenue": Decimal("803964958000"),
    "net_profit": Decimal("32619022000"),
    "operating_cash_flow": Decimal("59135544000"),
}


def _display(value: Decimal) -> str:
    return str(value.quantize(_TWO_DECIMALS, rounding=ROUND_HALF_UP))


def calculate_fin_b_014_v45() -> dict[str, Any]:
    """从未舍入的利润率与现金流率计算三个最终答案字段。"""
    net_margin_drop = (
        _BYD_2024["net_profit"] / _BYD_2024["revenue"]
        - _BYD_2025["net_profit"] / _BYD_2025["revenue"]
    ) * Decimal("100")
    cash_flow_margin_drop = (
        _BYD_2024["operating_cash_flow"] / _BYD_2024["revenue"]
        - _BYD_2025["operating_cash_flow"] / _BYD_2025["revenue"]
    ) * Decimal("100")
    unrounded_difference = cash_flow_margin_drop - net_margin_drop

    return {
        "answers": [
            _display(net_margin_drop),
            _display(cash_flow_margin_drop),
            _display(unrounded_difference),
        ],
        "net_margin_drop": net_margin_drop,
        "cash_flow_margin_drop": cash_flow_margin_drop,
        "unrounded_difference": unrounded_difference,
        "source_values": {
            "2024": dict(_BYD_2024),
            "2025": dict(_BYD_2025),
        },
    }


def verify_fin_b_014_sources_v45(
    *,
    report_2024_path: Path,
    report_2025_path: Path,
) -> dict[str, dict[str, Any]]:
    """确认计算使用的六个原始金额存在于两份官方年报对应物理页。"""
    reports = {
        "2024": (Path(report_2024_path), (10, 11), _BYD_2024),
        "2025": (Path(report_2025_path), (11,), _BYD_2025),
    }
    evidence: dict[str, dict[str, Any]] = {}
    for year, (path, pages, values) in reports.items():
        extracted = subprocess.run(
            [
                "pdftotext",
                "-f",
                str(pages[0]),
                "-l",
                str(pages[-1]),
                "-layout",
                str(path),
                "-",
            ],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        digits = re.sub(r"\D", "", extracted)
        source_values = [str(int(value)) for value in values.values()]
        missing = [value for value in source_values if value not in digits]
        if missing:
            raise ValueError(
                f"{path.name}第{pages[0]}至{pages[-1]}物理页缺少原始金额: {missing}"
            )
        evidence[year] = {
            "physical_pages": list(pages),
            "values": source_values,
        }
    return evidence
