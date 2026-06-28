from datetime import datetime, timedelta

import pandas as pd

from data_service import VN_TZ
from lineup_service import (
    LINEUP_REQUIRED,
    SLOT_ORDER,
    build_pitch_xi_from_lineup_rows,
    get_match_lineups,
    lineups_window_open,
)


def _kickoff_in(minutes: int) -> pd.Timestamp:
    return pd.Timestamp(datetime.now(VN_TZ) + timedelta(minutes=minutes))


def test_lineups_window_before_publish():
    assert lineups_window_open(_kickoff_in(61)) is False


def test_lineups_window_during_publish():
    assert lineups_window_open(_kickoff_in(30)) is True


def test_lineups_window_after_kickoff():
    assert lineups_window_open(_kickoff_in(-10)) is False


def test_build_pitch_xi_from_lineup_rows():
    rows = []
    for slot in SLOT_ORDER:
        rows.append(
            {
                "player_name": f"Player {slot}",
                "shirt_number": str(SLOT_ORDER.index(slot) + 1),
                "slot": slot,
                "formation": "4-2-3-1",
            }
        )
    xi = build_pitch_xi_from_lineup_rows(rows)
    assert len(xi) == LINEUP_REQUIRED
    assert xi[0]["player"]["player_name"] == "Player GK"
    assert xi[0]["search_name"] == "Player GK"
    assert "x_pct" in xi[0] and "y_pct" in xi[0]


def test_get_match_lineups_complete():
    records = []
    for code in ("POR", "CRO"):
        for slot in SLOT_ORDER:
            records.append(
                {
                    "match_id": "80",
                    "fifa_code": code,
                    "player_name": f"{code}-{slot}",
                    "shirt_number": "1",
                    "slot": slot,
                    "formation": "4-2-3-1",
                    "updated_at": "",
                }
            )
    df = pd.DataFrame(records)
    bundle = get_match_lineups(df, "80", "POR", "CRO")
    assert bundle["is_complete"]
    assert len(bundle["xi_a"]) == LINEUP_REQUIRED
    assert len(bundle["xi_b"]) == LINEUP_REQUIRED


def test_get_match_lineups_incomplete():
    df = pd.DataFrame(
        [
            {
                "match_id": "1",
                "fifa_code": "POR",
                "player_name": "Only One",
                "shirt_number": "1",
                "slot": "GK",
                "formation": "4-2-3-1",
                "updated_at": "",
            }
        ]
    )
    bundle = get_match_lineups(df, "1", "POR", "CRO")
    assert not bundle["is_complete"]
    assert not bundle["is_complete_a"]
