"""World Cup 2026 schedule helpers — UTC kickoffs converted to UTC+7 (VN/WIB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

VN_TZ = timezone(timedelta(hours=7))
SCHEDULE_PATH = Path(__file__).parent / "data" / "world-cup-2026-schedule.csv"

VN_WEEKDAYS = (
    "Thứ Hai",
    "Thứ Ba",
    "Thứ Tư",
    "Thứ Năm",
    "Thứ Sáu",
    "Thứ Bảy",
    "Chủ Nhật",
)
VN_WEEKDAYS_SHORT = ("T2", "T3", "T4", "T5", "T6", "T7", "CN")

GROUP_COLORS: dict[str, str] = {
    "A": "#ef4444",
    "B": "#3b82f6",
    "C": "#06b6d4",
    "D": "#8b5cf6",
    "E": "#f59e0b",
    "F": "#10b981",
    "G": "#ec4899",
    "H": "#6366f1",
    "I": "#14b8a6",
    "J": "#f97316",
    "K": "#84cc16",
    "L": "#a855f7",
}


def _parse_kickoff_utc(date_str: str, time_str: str) -> datetime:
    dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=timezone.utc)


def load_wc_schedule(path: Path | None = None) -> pd.DataFrame:
    """Load official schedule CSV and add UTC+7 kickoff columns."""
    csv_path = path or SCHEDULE_PATH
    df = pd.read_csv(csv_path)
    df = df.rename(
        columns={
            "Match": "match_number",
            "Date (UTC)": "date_utc",
            "Kickoff (UTC)": "time_utc",
            "Kickoff (ET)": "kickoff_et",
            "Team A": "schedule_team_a",
            "Team B": "schedule_team_b",
            "Group / Round": "group_round",
            "Host Country": "host_country",
        }
    )
    df["match_number"] = pd.to_numeric(df["match_number"], errors="coerce").astype("Int64")
    df["kickoff_utc"] = df.apply(
        lambda r: _parse_kickoff_utc(str(r["date_utc"]), str(r["time_utc"])),
        axis=1,
    )
    df["kickoff_vn"] = df["kickoff_utc"].dt.tz_convert(VN_TZ)
    df["kickoff_vn_date"] = df["kickoff_vn"].dt.date
    df["venue_line"] = df["Venue"].astype(str) + " · " + df["City"].astype(str)
    return df


def kickoff_vn_storage_value(kickoff_vn) -> str | None:
    """Format UTC+7 kickoff for matches.csv / Google Sheets (`YYYY-MM-DD HH:MM`)."""
    if kickoff_vn is None or (isinstance(kickoff_vn, float) and pd.isna(kickoff_vn)):
        return None
    if pd.isna(kickoff_vn):
        return None
    dt = kickoff_vn.to_pydatetime() if hasattr(kickoff_vn, "to_pydatetime") else kickoff_vn
    return dt.strftime("%Y-%m-%d %H:%M")


def format_time_vn(dt: datetime) -> str:
    """24-hour kickoff time in UTC+7."""
    return dt.strftime("%H:%M")


def format_date_compact_vn(dt: datetime) -> str:
    """Short date label, e.g. T6, 13/06."""
    return f"{VN_WEEKDAYS_SHORT[dt.weekday()]}, {dt.day:02d}/{dt.month:02d}"


def format_date_header_vn(dt: datetime) -> str:
    """Full date header, e.g. THỨ SÁU, 12 THÁNG 6, 2026."""
    return f"{VN_WEEKDAYS[dt.weekday()].upper()}, {dt.day} THÁNG {dt.month}, {dt.year}"


def group_letter(group_round: str | None) -> str | None:
    if not group_round or not isinstance(group_round, str):
        return None
    text = group_round.strip()
    if text.lower().startswith("group "):
        return text.split()[-1].upper()
    return None


def group_color(group_round: str | None) -> str:
    letter = group_letter(group_round)
    if letter and letter in GROUP_COLORS:
        return GROUP_COLORS[letter]
    return "#64748b"


def group_label_vn(group_round: str | None) -> str:
    if not group_round or not isinstance(group_round, str):
        return "TBD"
    text = group_round.strip()
    letter = group_letter(text)
    if letter:
        return f"BẢNG {letter}"
    mapping = {
        "Round of 16": "Vòng 1/8",
        "Quarter-final": "Tứ kết",
        "Semi-final": "Bán kết",
        "Third Place": "Tranh hạng 3",
        "Final": "Chung kết",
    }
    return mapping.get(text, text)


def is_group_stage(group_round: str | None, stage_id: int | None = None) -> bool:
    if stage_id is not None:
        return int(stage_id) == 1
    if not group_round:
        return False
    return str(group_round).strip().lower().startswith("group")


def enrich_matches_with_schedule(
    matches_df: pd.DataFrame,
    schedule_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Merge sheet matches with official schedule times (UTC+7)."""
    schedule = schedule_df if schedule_df is not None else load_wc_schedule()
    schedule_cols = [
        "match_number",
        "kickoff_utc",
        "kickoff_vn",
        "kickoff_vn_date",
        "kickoff_et",
        "group_round",
        "Venue",
        "City",
        "venue_line",
        "host_country",
    ]
    sched = schedule[schedule_cols].copy()
    sched["match_number"] = sched["match_number"].astype(int)

    merged = matches_df.copy()
    merged["match_number"] = pd.to_numeric(merged["match_number"], errors="coerce").astype(int)
    merged = merged.merge(sched, on="match_number", how="left", suffixes=("", "_sched"))

    if "kickoff_at" in merged.columns:
        fallback = pd.to_datetime(merged["kickoff_at"], errors="coerce")
        if fallback.dt.tz is None:
            fallback = fallback.dt.tz_localize(VN_TZ)
        else:
            fallback = fallback.dt.tz_convert(VN_TZ)
        merged["kickoff_vn"] = merged["kickoff_vn"].fillna(fallback)

    merged["kickoff_vn_date"] = merged["kickoff_vn"].apply(
        lambda x: x.date() if pd.notna(x) and hasattr(x, "date") else pd.NA
    )
    merged["kickoff_at"] = merged["kickoff_vn"].apply(kickoff_vn_storage_value)
    return merged.sort_values(["kickoff_vn", "match_number"], na_position="last").reset_index(drop=True)
