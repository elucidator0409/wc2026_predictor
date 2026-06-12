import pandas as pd

from prediction_matrix_service import EMPTY_CELL, build_prediction_matrix
from scoring import format_pred_admin_cell


def test_format_pred_admin_cell_outcomes():
    assert format_pred_admin_cell(None) == "—"
    assert format_pred_admin_cell("") == "—"
    assert format_pred_admin_cell("A") == "A thắng"
    assert format_pred_admin_cell("B") == "B thắng"
    assert format_pred_admin_cell("D") == "Hòa"
    assert format_pred_admin_cell("D", is_knockout=True, adv_team_name="Mexico", name_to_fifa={"Mexico": "MEX"}) == "Hòa (PEN: MEX)"


def test_build_prediction_matrix_shape_and_empty_cells():
    matches_df = pd.DataFrame(
        [
            {
                "match_id": "1",
                "match_number": 1,
                "kickoff_vn": pd.Timestamp("2026-06-11 20:00"),
                "team_a": "Mexico",
                "team_b": "South Africa",
                "team_a_fifa": "MEX",
                "team_b_fifa": "RSA",
                "stage_id": 1,
            },
            {
                "match_id": "2",
                "match_number": 2,
                "kickoff_vn": pd.Timestamp("2026-06-12 02:00"),
                "team_a": "Korea Republic",
                "team_b": "Czechia",
                "team_a_fifa": "KOR",
                "team_b_fifa": "CZE",
                "stage_id": 1,
            },
        ]
    )
    users_df = pd.DataFrame(
        [
            {"user_id": "1", "name": "Alice"},
            {"user_id": "2", "name": "Bob"},
        ]
    )
    preds_df = pd.DataFrame(
        [
            {"user_id": "1", "match_id": "1", "pred_outcome": "A", "pred_advanced_team_id": None},
            {"user_id": "2", "match_id": "1", "pred_outcome": "D", "pred_advanced_team_id": None},
            {"user_id": "1", "match_id": "2", "pred_outcome": "B", "pred_advanced_team_id": None},
        ]
    )
    teams_df = pd.DataFrame(
        [
            {"id": "10", "team_name": "Mexico", "fifa_code": "MEX"},
            {"id": "11", "team_name": "South Africa", "fifa_code": "RSA"},
        ]
    )

    matrix = build_prediction_matrix(matches_df, preds_df, users_df, teams_df)

    assert list(matrix.columns) == ["Trận", "Cặp đấu", "Alice", "Bob"]
    assert len(matrix) == 2
    assert matrix.iloc[0]["Trận"] == 1
    assert matrix.iloc[0]["Cặp đấu"] == "MEX - RSA"
    assert matrix.iloc[0]["Alice"] == "A thắng"
    assert matrix.iloc[0]["Bob"] == "Hòa"
    assert matrix.iloc[1]["Alice"] == "B thắng"
    assert matrix.iloc[1]["Bob"] == EMPTY_CELL


def test_build_prediction_matrix_knockout_pen():
    matches_df = pd.DataFrame(
        [
            {
                "match_id": "50",
                "match_number": 50,
                "kickoff_vn": pd.Timestamp("2026-07-01 20:00"),
                "team_a": "Mexico",
                "team_b": "Brazil",
                "team_a_fifa": "MEX",
                "team_b_fifa": "BRA",
                "stage_id": 2,
            },
        ]
    )
    users_df = pd.DataFrame([{"user_id": "1", "name": "Alice"}])
    preds_df = pd.DataFrame(
        [
            {
                "user_id": "1",
                "match_id": "50",
                "pred_outcome": "D",
                "pred_advanced_team_id": "10",
            },
        ]
    )
    teams_df = pd.DataFrame(
        [
            {"id": "10", "team_name": "Mexico", "fifa_code": "MEX"},
            {"id": "20", "team_name": "Brazil", "fifa_code": "BRA"},
        ]
    )

    matrix = build_prediction_matrix(matches_df, preds_df, users_df, teams_df)

    assert matrix.iloc[0]["Alice"] == "Hòa (PEN: MEX)"
