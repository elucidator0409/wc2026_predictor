import pandas as pd

from scoring import (
    calculate_fines,
    calculate_points,
    format_history_timestamp,
    format_history_verdict,
    format_matchup_display,
    format_pred_display,
    format_pred_pick,
    is_match_finished,
    normalize_pred_outcome,
    scores_to_outcome,
)


def _row(**kwargs):
    base = {
        "pred_outcome": "A",
        "real_score_a": 2,
        "real_score_b": 1,
        "stage_id": 1,
        "pred_advanced_team_id": None,
        "real_advanced_team_id": None,
    }
    base.update(kwargs)
    return base


def test_scores_to_outcome():
    assert scores_to_outcome(2, 1) == "A"
    assert scores_to_outcome(1, 2) == "B"
    assert scores_to_outcome(1, 1) == "D"


def test_normalize_pred_outcome():
    assert normalize_pred_outcome("a") == "A"
    assert normalize_pred_outcome("b") == "B"
    assert normalize_pred_outcome("w") == "A"
    assert normalize_pred_outcome("l") == "B"
    assert normalize_pred_outcome("d") == "D"
    assert normalize_pred_outcome("X") is None


def test_points_correct_adb():
    assert calculate_points(_row(pred_outcome="A")) == 3
    assert calculate_points(_row(pred_outcome="B")) == 0


def test_points_knockout_pen_bonus():
    row = _row(
        pred_outcome="D",
        real_score_a=1,
        real_score_b=1,
        stage_id=2,
        pred_advanced_team_id="10",
        real_advanced_team_id="10",
    )
    assert calculate_points(row) == 4


def test_points_knockout_pen_wrong():
    row = _row(
        pred_outcome="D",
        real_score_a=1,
        real_score_b=1,
        stage_id=2,
        pred_advanced_team_id="10",
        real_advanced_team_id="11",
    )
    assert calculate_points(row) == 3


def test_fines_correct_and_wrong():
    assert calculate_fines(_row(pred_outcome="A")) == 0
    assert calculate_fines(_row(pred_outcome="B")) == 10


def test_fines_knockout_draw_correct_pen_wrong_still_zero():
    row = _row(
        pred_outcome="D",
        real_score_a=1,
        real_score_b=1,
        stage_id=2,
        pred_advanced_team_id="10",
        real_advanced_team_id="11",
    )
    assert calculate_fines(row) == 0


def test_format_pred_display_no_legacy_codes():
    fifa = {"Canada": "CAN", "Paraguay": "PAR"}
    assert format_pred_display("A", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🇨🇦 Canada - 🇵🇾 Paraguay → 🇨🇦 Canada thắng"
    assert format_pred_display("B", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🇨🇦 Canada - 🇵🇾 Paraguay → 🇵🇾 Paraguay thắng"
    assert format_pred_display("D", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🇨🇦 Canada - 🇵🇾 Paraguay → 🤝 Hòa"
    assert format_pred_display("D") == "🤝 Hòa"
    assert format_pred_display("L", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🇨🇦 Canada - 🇵🇾 Paraguay → 🇵🇾 Paraguay thắng"
    assert format_pred_display("W", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🇨🇦 Canada - 🇵🇾 Paraguay → 🇨🇦 Canada thắng"
    assert "(W)" not in format_pred_display("W", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa)
    assert "(L)" not in format_pred_display("L", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa)


def test_format_matchup_display_compact():
    fifa = {"Canada": "CAN", "Paraguay": "PAR"}
    assert format_matchup_display("Canada", "Paraguay", name_to_fifa=fifa) == "🇨🇦 CAN - 🇵🇾 PAR"


def test_format_matchup_html_uses_flagcdn():
    from scoring import format_matchup_html

    fifa = {"Canada": "CAN", "Paraguay": "PAR"}
    out = format_matchup_html("Canada", "Paraguay", name_to_fifa=fifa)
    assert "flagcdn.com" in out
    assert "CAN" in out and "PAR" in out
    assert "pred-hist-matchup-line" in out


def test_format_pred_pick_html_uses_flagcdn():
    from scoring import format_pred_pick_html

    fifa = {"Canada": "CAN", "Paraguay": "PAR"}
    out = format_pred_pick_html("A", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa)
    assert "flagcdn.com" in out
    assert "thắng" in out
    assert "pred-hist-pick-line" in out


def test_format_pred_pick():
    fifa = {"Canada": "CAN", "Paraguay": "PAR", "Mexico": "MEX"}
    assert format_pred_pick("A", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🇨🇦 thắng"
    assert format_pred_pick("B", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🇵🇾 thắng"
    assert format_pred_pick("D", team_a="Canada", team_b="Paraguay", name_to_fifa=fifa) == "🤝 Hòa"


def test_is_match_finished():
    assert is_match_finished(_row()) is True
    assert is_match_finished(_row(real_score_a=pd.NA, real_score_b=1)) is False


def test_format_history_verdict_pending():
    row = _row(real_score_a=pd.NA, real_score_b=pd.NA)
    assert format_history_verdict(row) == "⏳ Chưa đá"


def test_format_history_verdict_correct():
    assert format_history_verdict(_row(pred_outcome="A")) == "✅ +3"


def test_format_history_verdict_wrong():
    assert format_history_verdict(_row(pred_outcome="B")) == "❌ phạt 10k"


def test_format_history_verdict_knockout_pen_bonus():
    row = _row(
        pred_outcome="D",
        real_score_a=1,
        real_score_b=1,
        stage_id=2,
        pred_advanced_team_id="10",
        real_advanced_team_id="10",
    )
    assert format_history_verdict(row) == "✅ +4"


def test_format_history_timestamp():
    assert format_history_timestamp("2026-06-09 22:12:46") == "09/06 · 22:12"
