"""Tests for schedule_service timezone conversion and helpers."""

from datetime import datetime, timezone, timedelta

import pandas as pd

from schedule_service import (
    VN_TZ,
    enrich_matches_with_schedule,
    format_date_header_vn,
    format_time_vn,
    group_color,
    group_label_vn,
    match_round_color,
    match_round_label_vn,
    load_wc_schedule,
)


def test_load_wc_schedule_has_104_matches():
    df = load_wc_schedule()
    assert len(df) == 104
    assert "kickoff_vn" in df.columns
    assert df["kickoff_vn"].notna().all()


def test_match1_utc_to_vn():
    """Mexico vs South Africa: 2026-06-11 19:00 UTC → 2026-06-12 02:00 UTC+7."""
    df = load_wc_schedule()
    row = df[df["match_number"] == 1].iloc[0]
    kickoff_vn = row["kickoff_vn"].to_pydatetime()
    assert kickoff_vn.hour == 2
    assert kickoff_vn.minute == 0
    assert kickoff_vn.day == 12
    assert kickoff_vn.month == 6
    assert kickoff_vn.utcoffset() == timedelta(hours=7)


def test_match3_canada_bosnia():
    """Canada vs Bosnia: 2026-06-12 19:00 UTC → 2026-06-13 02:00 UTC+7 (matches kickoffclock WIB)."""
    df = load_wc_schedule()
    row = df[df["match_number"] == 3].iloc[0]
    kickoff_vn = row["kickoff_vn"].to_pydatetime()
    assert kickoff_vn.hour == 2
    assert kickoff_vn.day == 13


def test_format_time_vn():
    dt = datetime(2026, 6, 13, 2, 0, tzinfo=VN_TZ)
    assert format_time_vn(dt) == "02:00"


def test_format_date_header_vn():
    dt = datetime(2026, 6, 13, 2, 0, tzinfo=VN_TZ)
    assert "THỨ BẢY" in format_date_header_vn(dt)
    assert "13 THÁNG 6" in format_date_header_vn(dt)


def test_group_label_vn():
    assert group_label_vn("Group A") == "BẢNG A"
    assert group_label_vn("Round of 32") == "VÒNG 1/16"
    assert group_label_vn("Round of 16") == "VÒNG 1/8"
    assert group_label_vn("Quarterfinals") == "TỨ KẾT"
    assert group_label_vn("Semifinals") == "BÁN KẾT"
    assert group_label_vn("Final") == "CHUNG KẾT"


def test_group_color_knockout():
    assert group_color("Round of 32") == "#38bdf8"
    assert group_color("Final") == "#fbbf24"


def test_match_round_label_vn():
    assert match_round_label_vn(group_round="Group D") == "BẢNG D"
    assert match_round_label_vn(group_round="Round of 32") == "VÒNG 1/16"
    assert match_round_label_vn(match_label="W73 vs W75", group_round="Round of 16") == "VÒNG 1/8"
    assert match_round_label_vn(match_label="W73 vs W75", stage_id=3) == "VÒNG 1/8"
    assert match_round_label_vn(match_label="W101 vs W102", stage_id=7) == "CHUNG KẾT"


def test_match_round_color():
    assert match_round_color(group_round="Group A") == "#ef4444"
    assert match_round_color(group_round="Round of 16") == "#6366f1"
    assert match_round_color(stage_id=7) == "#fbbf24"


def test_enrich_matches_with_schedule_sheet_overrides_csv():
    matches = pd.DataFrame(
        {
            "match_number": [1, 2],
            "team_a": ["Mexico", "South Korea"],
            "team_b": ["South Africa", "Czech Republic"],
            "stage_id": [1, 1],
            "match_label": ["Group A", "Group A"],
            "real_score_a": [pd.NA, pd.NA],
            "real_score_b": [pd.NA, pd.NA],
            "kickoff_at": ["2026-06-12 04:00", "2026-06-12 11:00"],
        }
    )
    enriched = enrich_matches_with_schedule(matches)
    assert "kickoff_vn" in enriched.columns
    assert "venue_line" in enriched.columns
    assert enriched.iloc[0]["kickoff_vn"].hour == 4
    assert enriched.iloc[0]["kickoff_at"] == "2026-06-12 04:00"
    assert enriched.iloc[1]["kickoff_vn"].hour == 11


def test_enrich_matches_with_schedule_csv_fallback_when_sheet_empty():
    matches = pd.DataFrame(
        {
            "match_number": [1],
            "team_a": ["Mexico"],
            "team_b": ["South Africa"],
            "stage_id": [1],
            "match_label": ["Group A"],
            "real_score_a": [pd.NA],
            "real_score_b": [pd.NA],
            "kickoff_at": [pd.NA],
        }
    )
    enriched = enrich_matches_with_schedule(matches)
    assert enriched.iloc[0]["kickoff_vn"].hour == 2
    assert enriched.iloc[0]["kickoff_at"] == "2026-06-12 02:00"
