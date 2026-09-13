from decimal import Decimal
from pathlib import Path

from agent_team_b1.financial_unrounded_v45 import (
    calculate_fin_b_014_v45,
    verify_fin_b_014_sources_v45,
)


ROOT = Path(__file__).resolve().parents[1]


def test_fin_b_014_uses_unrounded_intermediate_values_for_the_final_difference() -> None:
    result = calculate_fin_b_014_v45()

    assert result["answers"] == ["1.12", "9.82", "8.69"]
    assert result["net_margin_drop"] == Decimal(
        "1.122787347243862635008704894"
    )
    assert result["cash_flow_margin_drop"] == Decimal(
        "9.817778418613921683525262597"
    )
    assert result["unrounded_difference"] == Decimal(
        "8.694991071370059048516557703"
    )


def test_fin_b_014_rejects_subtracting_already_rounded_display_values() -> None:
    result = calculate_fin_b_014_v45()

    rounded_first = Decimal(result["answers"][0])
    rounded_second = Decimal(result["answers"][1])

    assert rounded_second - rounded_first == Decimal("8.70")
    assert result["answers"][2] == "8.69"
    assert result["answers"][2] != str(rounded_second - rounded_first)


def test_fin_b_014_source_values_are_present_in_the_official_annual_reports() -> None:
    source_root = ROOT / "public_dataset_upload" / "raw" / "financial_reports"

    evidence = verify_fin_b_014_sources_v45(
        report_2024_path=source_root / "annual_byd_2024_report.PDF",
        report_2025_path=source_root / "annual_byd_2025_report.PDF",
    )

    assert evidence == {
        "2024": {
            "physical_pages": [10, 11],
            "values": ["777102455000", "40254346000", "133453873000"],
        },
        "2025": {
            "physical_pages": [11],
            "values": ["803964958000", "32619022000", "59135544000"],
        },
    }
