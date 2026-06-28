"""Official match lineups from Google Sheet (no external lineup API)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd

from data_service import VN_TZ
from players_service import DEFAULT_FORMATION, FORMATION_4231_SLOTS

LINEUP_PUBLISH_MINUTES = 60
LINEUP_CLOSE_MINUTES = 5
LINEUP_REQUIRED = 11

SLOT_ORDER: tuple[str, ...] = (
    "GK",
    "DF1",
    "DF2",
    "DF3",
    "DF4",
    "DM1",
    "DM2",
    "AM1",
    "AM2",
    "AM3",
    "FW",
)

SLOT_LABELS_VN: dict[str, str] = {
    "GK": "Thủ môn",
    "DF1": "Hậu vệ 1",
    "DF2": "Hậu vệ 2",
    "DF3": "Hậu vệ 3",
    "DF4": "Hậu vệ 4",
    "DM1": "Tiền vệ phòng ngự 1",
    "DM2": "Tiền vệ phòng ngự 2",
    "AM1": "Tiền vệ tấn công 1",
    "AM2": "Tiền vệ tấn công 2",
    "AM3": "Tiền vệ tấn công 3",
    "FW": "Tiền đạo",
}


def _to_vn_datetime(value) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    try:
        dt = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    except (AttributeError, TypeError, ValueError):
        return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=VN_TZ)
    return dt.astimezone(VN_TZ)


def lineups_window_open(kickoff_vn, now=None) -> bool:
    """True when kickoff is within T-60 minutes .. kickoff+5 minutes (VN time)."""
    kickoff = _to_vn_datetime(kickoff_vn)
    if kickoff is None:
        return False
    if now is None:
        now_dt = datetime.now(VN_TZ)
    else:
        now_dt = _to_vn_datetime(now)
        if now_dt is None:
            return False
    open_at = kickoff - timedelta(minutes=LINEUP_PUBLISH_MINUTES)
    close_at = kickoff + timedelta(minutes=LINEUP_CLOSE_MINUTES)
    return open_at <= now_dt < close_at


def build_pitch_xi_from_lineup_rows(rows: list[dict], formation: str = DEFAULT_FORMATION) -> list[dict]:
    """Map Sheet lineup rows to pitch entries using SLOT_ORDER + FORMATION_4231_SLOTS."""
    if not rows:
        return []

    slot_index = {slot: idx for idx, slot in enumerate(SLOT_ORDER)}
    formation_val = formation or DEFAULT_FORMATION
    result: list[dict] = []

    for row in rows:
        slot_key = str(row.get("slot", "")).strip().upper()
        idx = slot_index.get(slot_key)
        if idx is None or idx >= len(FORMATION_4231_SLOTS):
            continue
        role, x_pct, y_pct = FORMATION_4231_SLOTS[idx]
        player_name = str(row.get("player_name", "")).strip()
        result.append(
            {
                "player": {
                    "player_name": player_name,
                    "shirt_number": str(row.get("shirt_number", "")).strip(),
                },
                "slot": role,
                "slot_key": slot_key,
                "x_pct": x_pct,
                "y_pct": y_pct,
                "formation": str(row.get("formation") or formation_val).strip() or DEFAULT_FORMATION,
                "search_name": player_name,
            }
        )

    result.sort(key=lambda item: slot_index.get(str(item.get("slot_key", "")), 99))
    return result


def _team_lineup_rows(lineups_df: pd.DataFrame, match_id: str, fifa_code: str) -> list[dict]:
    if lineups_df.empty or not fifa_code:
        return []
    mid = str(match_id).strip()
    code = str(fifa_code).strip().upper()
    subset = lineups_df[
        (lineups_df["match_id"].astype(str).str.strip() == mid)
        & (lineups_df["fifa_code"].astype(str).str.strip().str.upper() == code)
    ]
    return subset.to_dict("records")


def get_match_lineups(
    lineups_df: pd.DataFrame,
    match_id: str,
    code_a: str,
    code_b: str,
) -> dict:
    rows_a = _team_lineup_rows(lineups_df, match_id, code_a)
    rows_b = _team_lineup_rows(lineups_df, match_id, code_b)

    formation_a = str(rows_a[0].get("formation", DEFAULT_FORMATION)) if rows_a else DEFAULT_FORMATION
    formation_b = str(rows_b[0].get("formation", DEFAULT_FORMATION)) if rows_b else DEFAULT_FORMATION

    xi_a = build_pitch_xi_from_lineup_rows(rows_a, formation_a)
    xi_b = build_pitch_xi_from_lineup_rows(rows_b, formation_b)

    complete_a = len(rows_a) >= LINEUP_REQUIRED
    complete_b = len(rows_b) >= LINEUP_REQUIRED

    return {
        "xi_a": xi_a,
        "xi_b": xi_b,
        "formation_a": formation_a,
        "formation_b": formation_b,
        "is_complete_a": complete_a,
        "is_complete_b": complete_b,
        "is_complete": complete_a and complete_b,
    }
