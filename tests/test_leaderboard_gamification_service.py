import pandas as pd

from leaderboard_gamification_service import (
    _build_streak_timeline,
    _format_streak_history_html,
    _max_streak_window,
    build_activity_feed,
    compute_streak_milestones,
)


def _timeline_row(
    user_id,
    name,
    order,
    form_code,
    *,
    has_pred=True,
    pred_outcome="A",
    team_a="Mexico",
    team_b="RSA",
    team_a_fifa="MEX",
    team_b_fifa="RSA",
):
    return {
        "user_id": user_id,
        "name": name,
        "global_order": order,
        "form_code": form_code,
        "has_pred": has_pred,
        "pred_outcome": pred_outcome,
        "pred_advanced_team_id": None,
        "team_a": team_a,
        "team_b": team_b,
        "team_a_fifa": team_a_fifa,
        "team_b_fifa": team_b_fifa,
        "stage_id": 1,
    }


def test_max_streak_window_picks_longest_segment():
    rows = [
        _timeline_row("U1", "A", 1, "W"),
        _timeline_row("U1", "A", 2, "W"),
        _timeline_row("U1", "A", 3, "L"),
        _timeline_row("U1", "A", 4, "W"),
        _timeline_row("U1", "A", 5, "W"),
        _timeline_row("U1", "A", 6, "W"),
    ]
    count, window = _max_streak_window(rows, {"W"})
    assert count == 3
    assert [r["global_order"] for r in window] == [4, 5, 6]


def test_compute_streak_milestones_win_and_lose_with_history():
    timeline = pd.DataFrame(
        [
            _timeline_row("U01", "Alice", 1, "W", pred_outcome="A", team_a="Mexico"),
            _timeline_row("U01", "Alice", 2, "W", pred_outcome="A", team_a="Korea", team_a_fifa="KOR"),
            _timeline_row("U01", "Alice", 3, "W", pred_outcome="A", team_a="Canada", team_a_fifa="CAN"),
            _timeline_row("U02", "Bob", 1, "L", pred_outcome="A"),
            _timeline_row("U02", "Bob", 2, "D", has_pred=False, pred_outcome=None),
            _timeline_row("U02", "Bob", 3, "L", pred_outcome="B", team_b="France", team_b_fifa="FRA"),
            _timeline_row("U02", "Bob", 4, "W"),
        ]
    )
    streaks = compute_streak_milestones(
        timeline,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        name_to_fifa={"Mexico": "MEX", "Korea": "KOR", "Canada": "CAN", "France": "FRA"},
    )
    assert streaks["win_streak"]["user_id"] == "U01"
    assert streaks["win_streak"]["streak"] == 3
    assert "lb-streak-arrow" in streaks["win_streak"]["history_html"]
    assert "thắng" in streaks["win_streak"]["history_html"]

    assert streaks["lose_streak"]["user_id"] == "U02"
    assert streaks["lose_streak"]["streak"] == 3
    assert "Bỏ lỡ" in streaks["lose_streak"]["history_html"]
    assert "lb-streak-arrow" in streaks["lose_streak"]["history_html"]


def test_format_streak_history_html_stack_layout():
    window = [
        _timeline_row("U01", "Alice", 1, "W", pred_outcome="A"),
        _timeline_row("U01", "Alice", 2, "W", pred_outcome="B", team_b="France", team_b_fifa="FRA"),
    ]
    html_out = _format_streak_history_html(
        window,
        name_to_fifa={"France": "FRA"},
        id_to_name={},
        layout="stack",
    )
    assert "lb-streak-card-history--stack" in html_out
    assert "lb-streak-history-step" in html_out
    assert html_out.count("lb-streak-history-step") == 2


def test_format_streak_history_html_draw_shows_both_teams():
    window = [
        _timeline_row(
            "U01",
            "Alice",
            1,
            "W",
            pred_outcome="D",
            team_a="USA",
            team_b="Korea",
            team_a_fifa="USA",
            team_b_fifa="KOR",
        ),
    ]
    html_out = _format_streak_history_html(
        window,
        name_to_fifa={"USA": "USA", "Korea": "KOR"},
        id_to_name={},
    )
    assert "lb-streak-pick-draw" in html_out
    assert "pred-hist-matchup-line" in html_out
    assert "Hòa" in html_out
    assert "USA" in html_out or "KOR" in html_out


def test_format_streak_history_html_missed_pick():
    window = [
        _timeline_row("U02", "Bob", 1, "D", has_pred=False, pred_outcome=None),
        _timeline_row("U02", "Bob", 2, "L", pred_outcome="B", team_b="France", team_b_fifa="FRA"),
    ]
    html = _format_streak_history_html(
        window,
        name_to_fifa={"France": "FRA"},
        id_to_name={},
    )
    assert "Bỏ lỡ" in html
    assert "lb-streak-arrow" in html
    assert "thắng" in html


def test_compute_streak_milestones_upset_hero():
    scored_df = pd.DataFrame(
        [
            {
                "user_id": "U03",
                "name": "Carol",
                "match_id": "1",
                "pred_outcome": "B",
                "actual_outcome": "B",
                "kickoff_vn": pd.Timestamp("2026-06-12 02:00"),
                "match_number": 2,
                "team_a": "France",
                "team_b": "Germany",
                "team_a_fifa": "FRA",
                "team_b_fifa": "GER",
                "group_round": "Bảng E",
            },
            {
                "user_id": "U01",
                "name": "Alice",
                "match_id": "1",
                "pred_outcome": "A",
                "actual_outcome": "B",
                "kickoff_vn": pd.Timestamp("2026-06-12 02:00"),
                "match_number": 2,
            },
            {
                "user_id": "U02",
                "name": "Bob",
                "match_id": "1",
                "pred_outcome": "A",
                "actual_outcome": "B",
                "kickoff_vn": pd.Timestamp("2026-06-12 02:00"),
                "match_number": 2,
            },
        ]
    )
    consensus_df = pd.DataFrame(
        [
            {
                "match_id": "1",
                "favorite_pick": "A",
                "consensus_votes": 2,
                "total_votes": 3,
            }
        ]
    )
    streaks = compute_streak_milestones(
        pd.DataFrame(),
        scored_df,
        consensus_df,
        pd.DataFrame([{"user_id": "U03", "name": "Carol"}]),
    )
    assert streaks["upset_hero"]["user_id"] == "U03"
    assert streaks["upset_hero"]["name"] == "Carol"
    assert "đám đông" in streaks["upset_hero"]["detail"]


def test_build_activity_feed_pred_recent_and_fine():
    now = pd.Timestamp.now(tz="Asia/Ho_Chi_Minh")
    users_df = pd.DataFrame([{"user_id": "U11", "name": "Hoàng"}])
    preds_df = pd.DataFrame(
        [
            {
                "user_id": "U11",
                "match_id": "10",
                "pred_outcome": "A",
                "pred_advanced_team_id": None,
                "timestamp": (now - pd.Timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
            }
        ]
    )
    matches_df = pd.DataFrame(
        [
            {
                "id": "10",
                "group_round": "Bảng E",
                "match_label": None,
                "stage_id": 1,
                "kickoff_vn": now + pd.Timedelta(days=1),
                "real_score_a": pd.NA,
                "real_score_b": pd.NA,
            },
            {
                "id": "1",
                "group_round": "Bảng A",
                "match_label": None,
                "stage_id": 1,
                "kickoff_vn": pd.Timestamp("2026-06-11 20:00"),
                "real_score_a": 1,
                "real_score_b": 0,
                "team_a": "France",
                "team_b": "Germany",
                "match_number": 1,
            },
        ]
    )
    finished_df = matches_df[matches_df["real_score_a"].notna()].copy()
    preds_df = pd.concat(
        [
            preds_df,
            pd.DataFrame(
                [
                    {
                        "user_id": "U11",
                        "match_id": "1",
                        "pred_outcome": "B",
                        "pred_advanced_team_id": None,
                        "timestamp": "2026-06-10 12:00:00",
                    }
                ]
            ),
        ],
        ignore_index=True,
    )
    leaderboard_df = pd.DataFrame(
        [{"user_id": "U11", "name": "Hoàng", "rank": 1, "points": 10}]
    )

    events = build_activity_feed(
        users_df, preds_df, matches_df, finished_df, leaderboard_df
    )
    kinds = {e["kind"] for e in events}
    assert "pred_recent" in kinds
    assert "fine_hit" in kinds
    pred_events = [e for e in events if e["kind"] == "pred_recent"]
    assert any("Hoàng" in e["text"] for e in pred_events)
    fine_events = [e for e in events if e["kind"] == "fine_hit"]
    assert any("quỹ phạt" in e["text"] for e in fine_events)


def test_build_activity_feed_title_race():
    users_df = pd.DataFrame(
        [
            {"user_id": "U01", "name": "TonyDo"},
            {"user_id": "U14", "name": "Elu"},
        ]
    )
    leaderboard_df = pd.DataFrame(
        [
            {"user_id": "U01", "name": "TonyDo", "rank": 1, "points": 30},
            {"user_id": "U14", "name": "Elu", "rank": 2, "points": 28},
        ]
    )
    events = build_activity_feed(
        users_df,
        pd.DataFrame(),
        pd.DataFrame(),
        pd.DataFrame(),
        leaderboard_df,
    )
    title = [e for e in events if e["kind"] == "title_race"]
    assert len(title) == 1
    assert "TonyDo" in title[0]["text"]
    assert "Elu" in title[0]["text"]
    assert title[0]["tone"] == "warn"


def test_build_streak_timeline_from_finished_matches():
    users_df = pd.DataFrame([{"user_id": "1", "name": "Alice"}])
    preds_df = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "1", "pred_outcome": "A", "pred_advanced_team_id": None},
            {"user_id": "1", "match_id": "2", "pred_outcome": "B", "pred_advanced_team_id": None},
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
                "team_b": "RSA",
                "team_a_fifa": "MEX",
                "team_b_fifa": "RSA",
                "kickoff_vn": pd.Timestamp("2026-06-11 20:00"),
            },
            {
                "match_id": "2",
                "match_number": 2,
                "real_score_a": 0,
                "real_score_b": 1,
                "stage_id": 1,
                "team_a": "France",
                "team_b": "Germany",
                "team_a_fifa": "FRA",
                "team_b_fifa": "GER",
                "kickoff_vn": pd.Timestamp("2026-06-12 02:00"),
            },
        ]
    )
    timeline = _build_streak_timeline(users_df, preds_df, finished)
    assert len(timeline) == 2
    assert timeline.iloc[0]["form_code"] == "W"
    assert timeline.iloc[1]["form_code"] == "W"
