import pandas as pd

from user_service import (
    active_from_storage_value,
    eligible_finished_matches,
    get_next_upcoming_match,
    is_match_eligible,
    suggest_next_user_id,
    user_active_from,
)


def _match_row(match_id="1", match_number=1, kickoff="2026-06-11 20:00", score_a=None, score_b=None):
    return {
        "match_id": match_id,
        "match_number": match_number,
        "kickoff_vn": pd.Timestamp(kickoff).tz_localize("Asia/Ho_Chi_Minh"),
        "real_score_a": score_a,
        "real_score_b": score_b,
        "team_a": "Mexico",
        "team_b": "South Africa",
    }


def test_suggest_next_user_id():
    users_df = pd.DataFrame(
        [
            {"user_id": "U01", "name": "Alice"},
            {"user_id": "U14", "name": "Bob"},
        ]
    )
    assert suggest_next_user_id(users_df) == "U15"
    assert suggest_next_user_id(pd.DataFrame()) == "U01"


def test_get_next_upcoming_match():
    matches_df = pd.DataFrame(
        [
            _match_row("1", 1, "2026-06-11 20:00", 1, 0),
            _match_row("2", 2, "2026-06-12 02:00"),
            _match_row("3", 3, "2026-06-13 02:00"),
        ]
    )
    next_match = get_next_upcoming_match(matches_df)
    assert next_match is not None
    assert str(next_match["match_id"]) == "2"


def test_is_match_eligible_for_late_joiner():
    active_from = pd.Timestamp("2026-06-12 02:00").tz_localize("Asia/Ho_Chi_Minh")
    old_match = pd.Series(_match_row("1", 1, "2026-06-11 20:00", 1, 0))
    new_match = pd.Series(_match_row("2", 2, "2026-06-12 02:00", 2, 1))

    assert is_match_eligible(old_match, active_from) is False
    assert is_match_eligible(new_match, active_from) is True
    assert is_match_eligible(old_match, None) is True


def test_eligible_finished_matches():
    finished = pd.DataFrame(
        [
            _match_row("1", 1, "2026-06-11 20:00", 1, 0),
            _match_row("2", 2, "2026-06-12 02:00", 2, 1),
        ]
    )
    user = pd.Series(
        {
            "user_id": "U15",
            "name": "Late",
            "active_from_kickoff": pd.Timestamp("2026-06-12 02:00").tz_localize("Asia/Ho_Chi_Minh"),
        }
    )

    eligible = eligible_finished_matches(finished, user)
    assert len(eligible) == 1
    assert str(eligible.iloc[0]["match_id"]) == "2"


def test_user_active_from_empty_means_full_history():
    user = pd.Series({"user_id": "U01", "name": "Alice", "active_from_kickoff": pd.NaT})
    assert user_active_from(user) is None


def test_is_match_eligible_naive_kickoff():
    active_from = pd.Timestamp("2026-06-12 02:00").tz_localize("Asia/Ho_Chi_Minh")
    match = pd.Series({"kickoff_vn": pd.Timestamp("2026-06-12 02:00")})
    assert is_match_eligible(match, active_from) is True


def test_active_from_storage_value():
    match = pd.Series(_match_row("2", 2, "2026-06-12 02:00"))
    assert active_from_storage_value(match) == "2026-06-12 02:00"
