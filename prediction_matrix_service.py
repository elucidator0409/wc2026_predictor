"""Build wide prediction matrix (matches x users) for Google Sheets export."""

from __future__ import annotations

import pandas as pd

from scoring import _team_code, format_pred_admin_cell, normalize_pred_outcome

MATRIX_SHEET_NAME = "prediction_matrix"
EMPTY_CELL = "—"


def _matchup_label(row) -> str:
    code_a = _team_code(row.get("team_a", ""), row.get("team_a_fifa"), None)
    code_b = _team_code(row.get("team_b", ""), row.get("team_b_fifa"), None)
    return f"{code_a} - {code_b}"


def _stage_id(row) -> int:
    try:
        return int(float(row.get("stage_id", 1)))
    except (ValueError, TypeError):
        return 1


def _adv_team_name(row, id_to_name: dict[str, str]) -> str | None:
    if _stage_id(row) <= 1 or normalize_pred_outcome(row.get("pred_outcome")) != "D":
        return None
    adv_id = row.get("pred_advanced_team_id")
    if adv_id is None or (isinstance(adv_id, float) and pd.isna(adv_id)):
        return None
    try:
        key = str(int(float(adv_id)))
    except (ValueError, TypeError):
        key = str(adv_id).strip()
    return id_to_name.get(key) or None


def build_prediction_matrix(
    matches_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    users_df: pd.DataFrame,
    teams_df: pd.DataFrame | None = None,
    name_to_fifa: dict[str, str] | None = None,
) -> pd.DataFrame:
    """
    Wide matrix: columns Trận, Cặp đấu, then one column per user (sorted by user_id).
    Cell values: A thắng / B thắng / Hòa / Hòa (PEN: XXX) / —
    """
    if matches_df.empty:
        return pd.DataFrame(columns=["Trận", "Cặp đấu"])

    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)
    users = users.sort_values("user_id")

    matches = matches_df.copy()
    matches["match_id"] = matches["match_id"].astype(str)
    matches["match_number"] = pd.to_numeric(matches["match_number"], errors="coerce")
    matches = matches.sort_values(["kickoff_vn", "match_number"])

    id_to_name: dict[str, str] = {}
    if teams_df is not None and not teams_df.empty:
        for _, t in teams_df.iterrows():
            id_to_name[str(t["id"])] = str(t["team_name"])

    preds = preds_df.copy() if not preds_df.empty else pd.DataFrame(
        columns=["user_id", "match_id", "pred_outcome", "pred_advanced_team_id"]
    )
    if not preds.empty:
        preds["user_id"] = preds["user_id"].astype(str)
        preds["match_id"] = preds["match_id"].astype(str)

    pred_by_key: dict[tuple[str, str], pd.Series] = {}
    for _, prow in preds.iterrows():
        pred_by_key[(prow["user_id"], prow["match_id"])] = prow

    rows = []
    for _, match in matches.iterrows():
        m_id = str(match["match_id"])
        row_data = {
            "Trận": int(match["match_number"]) if pd.notna(match["match_number"]) else m_id,
            "Cặp đấu": _matchup_label(match),
        }
        for _, user in users.iterrows():
            uid = str(user["user_id"])
            uname = str(user["name"])
            pred = pred_by_key.get((uid, m_id))
            if pred is None:
                row_data[uname] = EMPTY_CELL
                continue
            merged = {**match.to_dict(), **pred.to_dict()}
            adv = _adv_team_name(merged, id_to_name)
            row_data[uname] = format_pred_admin_cell(
                merged.get("pred_outcome"),
                team_a=match.get("team_a", ""),
                team_b=match.get("team_b", ""),
                adv_team_name=adv,
                is_knockout=_stage_id(match) > 1,
                name_to_fifa=name_to_fifa,
                team_a_fifa=match.get("team_a_fifa"),
                team_b_fifa=match.get("team_b_fifa"),
            )
        rows.append(row_data)

    return pd.DataFrame(rows)
