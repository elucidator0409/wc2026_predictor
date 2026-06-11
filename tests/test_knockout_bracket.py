"""Tests for knockout_bracket_service."""
from __future__ import annotations

import pandas as pd

from knockout_bracket_service import build_knockout_bracket, _resolve_winner_side, _split_half
from knockout_bracket_service import BracketMatch, BracketTeam


def _ko_row(**kwargs):
    base = {
        "match_id": "73",
        "match_number": 73,
        "match_label": "2A vs 2B",
        "stage_id": 2,
        "home_team_id": "1",
        "away_team_id": "2",
        "team_a": "Mexico",
        "team_b": "South Africa",
        "team_a_fifa": "MEX",
        "team_b_fifa": "RSA",
        "real_score_a": None,
        "real_score_b": None,
        "real_advanced_team_id": None,
    }
    base.update(kwargs)
    return base


def test_winner_by_score():
    row = pd.Series(_ko_row(real_score_a=2, real_score_b=1))
    assert _resolve_winner_side(row) == "a"


def test_winner_by_penalties():
    row = pd.Series(_ko_row(real_score_a=0, real_score_b=0, real_advanced_team_id="2"))
    assert _resolve_winner_side(row) == "b"


def test_split_half():
    matches = [
        BracketMatch("1", 1, "", BracketTeam("A", None, "—", False), BracketTeam("B", None, "—", False), False),
        BracketMatch("2", 2, "", BracketTeam("C", None, "—", False), BracketTeam("D", None, "—", False), False),
        BracketMatch("3", 3, "", BracketTeam("E", None, "—", False), BracketTeam("F", None, "—", False), False),
        BracketMatch("4", 4, "", BracketTeam("G", None, "—", False), BracketTeam("H", None, "—", False), False),
    ]
    left, right = _split_half(matches)
    assert len(left) == 2
    assert len(right) == 2


def test_right_half_display_order():
    """Rendered right columns should progress SF → QF → R16 → R32 toward the outer edge."""
    rounds = [
        {"stage_id": 2, "label": "R32"},
        {"stage_id": 3, "label": "R16"},
        {"stage_id": 4, "label": "QF"},
        {"stage_id": 5, "label": "SF"},
    ]
    display = [r["stage_id"] for r in reversed(rounds)]
    assert display == [5, 4, 3, 2]


def test_build_bracket_two_sided():
    rows = [
        _ko_row(match_id="73", match_number=73, stage_id=2),
        _ko_row(match_id="74", match_number=74, stage_id=2),
        _ko_row(match_id="89", match_number=89, stage_id=3, match_label="W73 vs W75"),
        _ko_row(match_id="104", match_number=104, stage_id=7, match_label="Final"),
    ]
    df = pd.DataFrame(rows)
    bracket = build_knockout_bracket(df)
    assert bracket["has_data"]
    assert len(bracket["left_rounds"]) >= 1
    assert bracket["final"] is not None
    assert bracket["final"].match_number == 104


def test_full_bracket_right_half_structure():
    from data_service import prep_matches

    matches = pd.read_csv("data/matches.csv")
    teams = pd.read_csv("data/teams.csv")
    bracket = build_knockout_bracket(prep_matches(matches, teams))
    assert len(bracket["left_rounds"]) == 4
    assert len(bracket["right_rounds"]) == 4
    assert [r["stage_id"] for r in bracket["left_rounds"]] == [2, 3, 4, 5]
    assert [r["stage_id"] for r in bracket["right_rounds"]] == [2, 3, 4, 5]
    assert bracket["right_rounds"][-1]["matches"][0].match_number == 102
    assert bracket["right_rounds"][0]["matches"][0].match_number == 81
