import pandas as pd

from scoring import (
    calculate_fines,
    calculate_points,
    format_pred_display,
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
