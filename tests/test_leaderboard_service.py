import pandas as pd

from leaderboard_service import (
    FINE_MISSED_MATCH,
    build_leaderboard,
    latest_match_insight,
    podium_entries,
    score_finished_match,
    top_rank_tie_count,
)


def _finished_match(match_id="1", match_number=1):
    return pd.Series(
        {
            "match_id": match_id,
            "match_number": match_number,
            "real_score_a": 1,
            "real_score_b": 0,
            "stage_id": 1,
            "team_a": "Mexico",
            "team_b": "South Africa",
            "team_a_fifa": "MEX",
            "team_b_fifa": "RSA",
            "kickoff_vn": pd.Timestamp("2026-06-11 20:00"),
        }
    )


def test_score_finished_match_missed():
    pts, fine, has_pred = score_finished_match(None, _finished_match())
    assert pts == 0
    assert fine == FINE_MISSED_MATCH
    assert has_pred is False


def test_score_finished_match_correct():
    pred = pd.Series({"pred_outcome": "A", "pred_advanced_team_id": None})
    pts, fine, has_pred = score_finished_match(pred, _finished_match())
    assert pts == 3
    assert fine == 0
    assert has_pred is True


def test_build_leaderboard_ties_and_missed_fines():
    users_df = pd.DataFrame(
        [
            {"user_id": "1", "name": "Alice"},
            {"user_id": "2", "name": "Bob"},
            {"user_id": "3", "name": "Carol"},
        ]
    )
    preds_df = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "1", "pred_outcome": "A", "pred_advanced_team_id": None},
            {"user_id": "2", "match_id": "1", "pred_outcome": "A", "pred_advanced_team_id": None},
            {"user_id": "3", "match_id": "1", "pred_outcome": "B", "pred_advanced_team_id": None},
        ]
    )
    finished = pd.DataFrame([_finished_match().to_dict()])

    lb = build_leaderboard(users_df, preds_df, finished)

    assert len(lb) == 3
    assert set(lb.loc[lb["points"] == 3, "rank"].tolist()) == {1}
    assert lb.loc[lb["name"] == "Carol", "fines"].iloc[0] == 10
    assert lb.loc[lb["name"] == "Alice", "correct"].iloc[0] == 1
    assert top_rank_tie_count(lb) == 2

    entries = podium_entries(lb)
    assert entries[0]["tie_count"] == 2


def test_latest_match_insight():
    users_df = pd.DataFrame(
        [
            {"user_id": "1", "name": "Alice"},
            {"user_id": "2", "name": "Bob"},
        ]
    )
    preds_df = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "1", "pred_outcome": "A", "pred_advanced_team_id": None},
            {"user_id": "2", "match_id": "1", "pred_outcome": "B", "pred_advanced_team_id": None},
        ]
    )
    finished = pd.DataFrame([_finished_match().to_dict()])

    insight = latest_match_insight(finished, preds_df, users_df)

    assert insight["match_number"] == 1
    assert insight["correct"] == 1
    assert insight["wrong"] == 1
    assert insight["missed"] == 0
