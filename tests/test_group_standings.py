"""Tests for group_standings_service."""
from __future__ import annotations

import pandas as pd
import pytest

from group_standings_service import compute_group_standings


def _teams():
    return pd.DataFrame([
        {"id": "1", "team_name": "Mexico", "group_letter": "A"},
        {"id": "2", "team_name": "South Africa", "group_letter": "A"},
        {"id": "3", "team_name": "South Korea", "group_letter": "A"},
        {"id": "4", "team_name": "Czech Republic", "group_letter": "A"},
    ])


def _match(home, away, sa, sb, group="Group A"):
    return {
        "home_team_id": home,
        "away_team_id": away,
        "real_score_a": sa,
        "real_score_b": sb,
        "group_round": group,
        "stage_id": 1,
    }


def test_empty_standings():
    teams = _teams()
    matches = pd.DataFrame(columns=list(_match("1", "2", None, None).keys()))
    result = compute_group_standings(matches, teams)
    assert "A" in result
    assert len(result["A"]) == 4
    assert result["A"]["points"].sum() == 0


def test_win_draw_loss_points():
    teams = _teams()
    matches = pd.DataFrame([
        _match("1", "2", 2, 0),
        _match("3", "4", 1, 1),
    ])
    result = compute_group_standings(matches, teams)
    a = result["A"].set_index("team_id")
    assert a.loc["1", "points"] == 3
    assert a.loc["2", "points"] == 0
    assert a.loc["3", "points"] == 1
    assert a.loc["4", "points"] == 1


def test_goal_difference_ranking():
    teams = _teams()
    matches = pd.DataFrame([
        _match("1", "2", 3, 0),
        _match("1", "3", 1, 0),
        _match("2", "3", 0, 2),
    ])
    result = compute_group_standings(matches, teams)
    top = result["A"].iloc[0]
    assert top["team_id"] == "1"
    assert top["gd"] == 4


def test_knockout_matches_excluded():
    teams = _teams()
    row = _match("1", "2", 2, 1)
    row["stage_id"] = 3
    row["group_round"] = "Round of 16"
    matches = pd.DataFrame([row])
    result = compute_group_standings(matches, teams)
    assert result["A"]["points"].sum() == 0


def test_rank_column():
    teams = _teams()
    matches = pd.DataFrame([_match("1", "2", 1, 0)])
    result = compute_group_standings(matches, teams)
    assert result["A"]["rank"].tolist() == [1, 2, 3, 4]
