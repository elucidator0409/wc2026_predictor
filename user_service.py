"""User eligibility helpers for late joiners."""

from __future__ import annotations

import re

from zoneinfo import ZoneInfo

import pandas as pd

from schedule_service import kickoff_vn_storage_value

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _to_vn_timestamp(value) -> pd.Timestamp | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    if getattr(ts, "tzinfo", None) is None:
        return ts.tz_localize(VN_TZ)
    return ts.tz_convert(VN_TZ)


def get_next_upcoming_match(matches_df: pd.DataFrame) -> pd.Series | None:
    """First pending match by kickoff_vn, then match_number."""
    if matches_df.empty:
        return None

    pending = matches_df[
        matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna()
    ].copy()
    if pending.empty:
        return None

    sort_cols = [c for c in ("kickoff_vn", "match_number") if c in pending.columns]
    pending = pending.sort_values(sort_cols or ["match_number"])
    return pending.iloc[0]


def suggest_next_user_id(users_df: pd.DataFrame) -> str:
    """Suggest next U## id from existing user_id values."""
    if users_df.empty or "user_id" not in users_df.columns:
        return "U01"

    max_num = 0
    for uid in users_df["user_id"].astype(str):
        match = re.fullmatch(r"U(\d+)", uid.strip(), flags=re.IGNORECASE)
        if match:
            max_num = max(max_num, int(match.group(1)))

    return f"U{max_num + 1:02d}"


def user_active_from(user_row: pd.Series) -> pd.Timestamp | None:
    """Return active_from_kickoff; None means full match history."""
    val = user_row.get("active_from_kickoff")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, str) and not val.strip():
        return None
    ts = _to_vn_timestamp(val)
    return ts


def is_match_eligible(match_row: pd.Series, active_from: pd.Timestamp | None) -> bool:
    """True when match counts toward this user's standings."""
    if active_from is None:
        return True

    kickoff_ts = _to_vn_timestamp(match_row.get("kickoff_vn"))
    active_ts = _to_vn_timestamp(active_from)
    if kickoff_ts is None or active_ts is None:
        return False

    return kickoff_ts >= active_ts


def eligible_finished_matches(
    finished_matches_df: pd.DataFrame,
    user_row: pd.Series,
) -> pd.DataFrame:
    """Finished matches that count for one user."""
    active_from = user_active_from(user_row)
    if active_from is None:
        return finished_matches_df

    mask = finished_matches_df.apply(
        lambda row: is_match_eligible(row, active_from),
        axis=1,
    )
    return finished_matches_df[mask].copy()


def active_from_storage_value(next_match: pd.Series) -> str | None:
    """Persist kickoff of the next upcoming match for a new user."""
    return kickoff_vn_storage_value(next_match.get("kickoff_vn"))
