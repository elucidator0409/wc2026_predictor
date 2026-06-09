"""Tests for schedule_service timezone conversion and helpers."""

from datetime import datetime, timezone, timedelta

import pandas as pd

from schedule_service import (
    VN_TZ,
    enrich_matches_with_schedule,
    format_date_header_vn,
    format_time_vn,
    group_label_vn,
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
    assert group_label_vn("Round of 16") == "Vòng 1/8"
    assert group_label_vn("Final") == "Chung kết"


def test_enrich_matches_with_schedule():
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
    assert enriched.iloc[0]["kickoff_vn"].hour == 2
    assert enriched.iloc[0]["kickoff_at"] == "2026-06-12 02:00"
