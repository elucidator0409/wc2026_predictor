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


def test_build_leaderboard_late_joiner_skips_old_missed():
    t1 = pd.Timestamp("2026-06-11 20:00").tz_localize("Asia/Ho_Chi_Minh")
    t2 = pd.Timestamp("2026-06-12 02:00").tz_localize("Asia/Ho_Chi_Minh")

    users_df = pd.DataFrame(
        [
            {"user_id": "1", "name": "Alice", "active_from_kickoff": pd.NaT},
            {
                "user_id": "2",
                "name": "Bob",
                "active_from_kickoff": t2,
            },
        ]
    )
    finished = pd.DataFrame(
        [
            {
                "match_id": "1",
                "match_number": 1,
                "real_score_a": 1,
                "real_score_b": 0,
                "stage_id": 1,
                "team_a": "Mexico",
                "team_b": "South Africa",
                "team_a_fifa": "MEX",
                "team_b_fifa": "RSA",
                "kickoff_vn": t1,
            },
            {
                "match_id": "2",
                "match_number": 2,
                "real_score_a": 2,
                "real_score_b": 1,
                "stage_id": 1,
                "team_a": "France",
                "team_b": "Germany",
                "team_a_fifa": "FRA",
                "team_b_fifa": "GER",
                "kickoff_vn": t2,
            },
        ]
    )
    preds_df = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "2", "pred_outcome": "A", "pred_advanced_team_id": None},
            {"user_id": "2", "match_id": "2", "pred_outcome": "B", "pred_advanced_team_id": None},
        ]
    )

    lb = build_leaderboard(users_df, preds_df, finished)
    alice = lb.loc[lb["name"] == "Alice"].iloc[0]
    bob = lb.loc[lb["name"] == "Bob"].iloc[0]

    assert alice["missed"] == 1
    assert alice["fines"] == 10
    assert alice["total_finished"] == 2

    assert bob["missed"] == 0
    assert bob["fines"] == 10
    assert bob["played"] == 1
    assert bob["total_finished"] == 1
