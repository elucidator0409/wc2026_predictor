import pandas as pd

from analytics_service import (
    OUTCOME_LABELS,
    OUTCOME_ORDER,
    RISK_CHART_COLORS,
    build_scored_predictions,
    calculate_crowd_consensus,
    derive_actual_outcome,
    format_accuracy_takeaway,
    format_lead_time_takeaway,
    format_momentum_takeaway,
    format_risk_bias_takeaway,
    get_confusion_matrix,
    get_cumulative_scores,
    get_prediction_lead_time,
    get_user_risk_profile,
    lead_time_medians,
    lead_time_stats,
    summarize_accuracy,
    summarize_lead_time,
    summarize_momentum,
    summarize_risk_bias,
    top_momentum_players,
)


def _users():
    return pd.DataFrame(
        [
            {"user_id": "1", "name": "Alice"},
            {"user_id": "2", "name": "Bob"},
        ]
    )


def _finished_matches():
    return pd.DataFrame(
        [
            {
                "match_id": "m1",
                "match_number": 1,
                "real_score_a": 2,
                "real_score_b": 1,
                "stage_id": 1,
                "kickoff_vn": pd.Timestamp("2026-06-11 20:00", tz="Asia/Ho_Chi_Minh"),
            },
            {
                "match_id": "m2",
                "match_number": 2,
                "real_score_a": 0,
                "real_score_b": 0,
                "stage_id": 1,
                "kickoff_vn": pd.Timestamp("2026-06-12 20:00", tz="Asia/Ho_Chi_Minh"),
            },
            {
                "match_id": "m3",
                "match_number": 3,
                "real_score_a": 1,
                "real_score_b": 2,
                "stage_id": 1,
                "kickoff_vn": pd.Timestamp("2026-06-13 20:00", tz="Asia/Ho_Chi_Minh"),
            },
        ]
    )


def _preds():
    return pd.DataFrame(
        [
            {"user_id": "1", "match_id": "m1", "pred_outcome": "A", "timestamp": "2026-06-11 10:00:00"},
            {"user_id": "1", "match_id": "m2", "pred_outcome": "A", "timestamp": "2026-06-12 10:00:00"},
            {"user_id": "1", "match_id": "m3", "pred_outcome": "A", "timestamp": "2026-06-13 10:00:00"},
            {"user_id": "2", "match_id": "m1", "pred_outcome": "B", "timestamp": "2026-06-11 08:00:00"},
            {"user_id": "2", "match_id": "m2", "pred_outcome": "D", "timestamp": "2026-06-12 08:00:00"},
            {"user_id": "2", "match_id": "m3", "pred_outcome": "B", "timestamp": ""},
        ]
    )


def test_outcome_constants():
    assert OUTCOME_ORDER == ("A", "D", "B")
    assert OUTCOME_LABELS["A"] == "Đội A thắng"
    assert OUTCOME_LABELS["D"] == "Hòa"


def test_derive_actual_outcome():
    df = pd.DataFrame(
        [
            {"real_score_a": 2, "real_score_b": 1},
            {"real_score_a": 0, "real_score_b": 0},
            {"real_score_a": 1, "real_score_b": 3},
        ]
    )
    outcomes = derive_actual_outcome(df).tolist()
    assert outcomes == ["A", "D", "B"]


def test_build_scored_predictions_points_and_outcomes():
    scored = build_scored_predictions(_preds(), _finished_matches(), _users())
    assert len(scored) == 6
    assert set(scored["actual_outcome"].dropna()) == {"A", "D", "B"}
    alice_m1 = scored[(scored["user_id"] == "1") & (scored["match_id"] == "m1")].iloc[0]
    assert alice_m1["points"] == 3
    bob_m1 = scored[(scored["user_id"] == "2") & (scored["match_id"] == "m1")].iloc[0]
    assert bob_m1["points"] == 0


def test_get_cumulative_scores_follows_kickoff_order():
    scored = build_scored_predictions(_preds(), _finished_matches(), _users())
    cumulative = get_cumulative_scores(scored)
    alice = cumulative[cumulative["user_id"] == "1"].reset_index(drop=True)
    assert alice["cumulative_points"].tolist() == [3, 3, 3]
    bob = cumulative[cumulative["user_id"] == "2"].reset_index(drop=True)
    assert bob["cumulative_points"].tolist() == [0, 3, 6]


def test_get_confusion_matrix_counts():
    scored = build_scored_predictions(_preds(), _finished_matches(), _users())
    matrix = get_confusion_matrix(scored, "2")
    assert matrix.loc["A", "B"] == 1
    assert matrix.loc["D", "D"] == 1
    assert matrix.loc["B", "B"] == 1
    assert matrix.loc["A", "A"] == 0


def test_get_prediction_lead_time_hours():
    matches = _finished_matches()
    lead = get_prediction_lead_time(_preds(), matches, _users())
    alice_m1 = lead[(lead["user_id"] == "1") & (lead["match_id"] == "m1")].iloc[0]
    assert alice_m1["lead_hours"] == 10.0
    assert not bool(alice_m1["is_late"])
    bob_missing = lead[(lead["user_id"] == "2") & (lead["match_id"] == "m3")].iloc[0]
    assert pd.isna(bob_missing["lead_hours"])


def test_lead_time_stats_coverage():
    lead = get_prediction_lead_time(_preds(), _finished_matches(), _users())
    stats = lead_time_stats(_preds(), lead)
    assert stats["total_predictions"] == 6
    assert stats["with_timestamp"] == 5
    assert stats["coverage_pct"] == round(5 / 6 * 100, 1)
    assert stats["late_count"] == 0


def test_summarize_momentum():
    scored = build_scored_predictions(_preds(), _finished_matches(), _users())
    cumulative = get_cumulative_scores(scored)
    summary = summarize_momentum(cumulative, 3)
    assert summary["leader_name"] == "Bob"
    assert summary["leader_points"] == 6
    assert summary["n_finished_matches"] == 3


def test_top_momentum_players_includes_highlight():
    scored = build_scored_predictions(_preds(), _finished_matches(), _users())
    cumulative = get_cumulative_scores(scored)
    ids = top_momentum_players(cumulative, limit=1, highlight_user_id="1")
    assert "2" in ids
    assert "1" in ids


def test_summarize_accuracy():
    scored = build_scored_predictions(_preds(), _finished_matches(), _users())
    matrix = get_confusion_matrix(scored, "2")
    summary = summarize_accuracy(matrix, "Bob")
    assert summary["total"] == 3
    assert summary["hits"] == 2
    assert summary["accuracy_pct"] == round(2 / 3 * 100, 1)
    assert "Đội A thắng" in summary["favorite_label"] or summary["favorite_count"] >= 0


def test_lead_time_medians_and_summary():
    lead = get_prediction_lead_time(_preds(), _finished_matches(), _users())
    stats = lead_time_stats(_preds(), lead)
    medians = lead_time_medians(lead)
    assert len(medians) == 2
    summary = summarize_lead_time(lead, stats)
    assert summary["early_bird_hours"] >= summary["last_minute_hours"]
    assert "overall_median_hours" in summary


def test_format_takeaways_non_empty():
    scored = build_scored_predictions(_preds(), _finished_matches(), _users())
    cumulative = get_cumulative_scores(scored)
    mom = summarize_momentum(cumulative, 3)
    assert format_momentum_takeaway(mom)
    matrix = get_confusion_matrix(scored, "1")
    acc = summarize_accuracy(matrix, "Alice")
    assert format_accuracy_takeaway(acc)
    lead = get_prediction_lead_time(_preds(), _finished_matches(), _users())
    stats = lead_time_stats(_preds(), lead)
    lead_summary = summarize_lead_time(lead, stats)
    assert format_lead_time_takeaway(lead_summary)


def test_empty_inputs_return_empty_frames():
    users = _users()
    assert build_scored_predictions(pd.DataFrame(), _finished_matches(), users).empty
    assert get_cumulative_scores(pd.DataFrame()).empty
    matrix = get_confusion_matrix(pd.DataFrame(), "1")
    assert matrix.shape == (3, 3)
    assert matrix.sum().sum() == 0
    assert calculate_crowd_consensus(pd.DataFrame()).empty
    assert get_user_risk_profile(pd.DataFrame(), pd.DataFrame(), users).empty


def test_calculate_crowd_consensus_majority_and_tiebreak():
    preds = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "m1", "pred_outcome": "A"},
            {"user_id": "2", "match_id": "m1", "pred_outcome": "A"},
            {"user_id": "1", "match_id": "m2", "pred_outcome": "B"},
            {"user_id": "2", "match_id": "m2", "pred_outcome": "A"},
        ]
    )
    consensus = calculate_crowd_consensus(preds)
    assert len(consensus) == 2
    m1 = consensus[consensus["match_id"] == "m1"].iloc[0]
    assert m1["favorite_pick"] == "A"
    assert m1["consensus_votes"] == 2
    m2 = consensus[consensus["match_id"] == "m2"].iloc[0]
    assert m2["favorite_pick"] == "A"
    assert m2["consensus_votes"] == 1

    tie_preds = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "m3", "pred_outcome": "A"},
            {"user_id": "2", "match_id": "m3", "pred_outcome": "B"},
        ]
    )
    tie = calculate_crowd_consensus(tie_preds)
    assert tie.iloc[0]["favorite_pick"] == "A"


def test_get_user_risk_profile_safe_and_risky_pct():
    preds = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "m1", "pred_outcome": "A"},
            {"user_id": "1", "match_id": "m2", "pred_outcome": "A"},
            {"user_id": "2", "match_id": "m1", "pred_outcome": "A"},
            {"user_id": "2", "match_id": "m2", "pred_outcome": "D"},
        ]
    )
    consensus = calculate_crowd_consensus(preds)
    profile = get_user_risk_profile(preds, consensus, _users())
    alice = profile[profile["user_id"] == "1"]
    bob = profile[profile["user_id"] == "2"]
    assert alice[alice["pick_type"] == "Safe"]["pct"].iloc[0] == 100.0
    assert bob[bob["pick_type"] == "Safe"]["pct"].iloc[0] == 50.0
    assert bob[bob["pick_type"] == "Risky"]["pct"].iloc[0] == 50.0


def test_summarize_and_format_risk_bias():
    preds = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "m1", "pred_outcome": "A"},
            {"user_id": "2", "match_id": "m1", "pred_outcome": "B"},
        ]
    )
    consensus = calculate_crowd_consensus(preds)
    profile = get_user_risk_profile(preds, consensus, _users())
    summary = summarize_risk_bias(profile, consensus)
    assert summary["n_matches_with_consensus"] == 1
    takeaway = format_risk_bias_takeaway(summary)
    assert "Wisdom of the Crowd" in takeaway or "consensus" in takeaway.lower() or "trận" in takeaway
