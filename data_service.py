"""Shared Google Sheets connection and data helpers."""

from datetime import datetime, timedelta, timezone

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials


@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes,
    )
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["spreadsheet_id"])


def read_sheet(sh, sheet_name: str) -> pd.DataFrame:
    data = sh.worksheet(sheet_name).get_all_values()
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data[1:], columns=data[0])


def prep_matches(matches_raw: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    matches_raw = matches_raw.copy()
    matches_raw.replace("", pd.NA, inplace=True)

    # Đổi tên cột id thành match_id ngay từ đầu để bảo vệ primary key
    if "id" in matches_raw.columns and "match_id" not in matches_raw.columns:
        matches_raw.rename(columns={"id": "match_id"}, inplace=True)

    for col in ("real_score_a", "real_score_b", "real_advanced_team_id"):
        if col not in matches_raw.columns:
            matches_raw[col] = pd.NA

    if "is_locked" not in matches_raw.columns:
        matches_raw["is_locked"] = False
    else:
        matches_raw["is_locked"] = (
            matches_raw["is_locked"].astype(str).str.strip().str.upper() == "TRUE"
        )

    # Ép kiểu Int64 an toàn cho dữ liệu có thể chứa NaN
    matches_raw["home_team_id"] = pd.to_numeric(matches_raw["home_team_id"], errors="coerce").astype(pd.Int64Dtype()).astype(str)
    matches_raw["away_team_id"] = pd.to_numeric(matches_raw["away_team_id"], errors="coerce").astype(pd.Int64Dtype()).astype(str)
    
    teams_df = teams_df.copy()
    teams_df["id"] = pd.to_numeric(teams_df["id"], errors="coerce").astype(pd.Int64Dtype()).astype(str)
    if "fifa_code" not in teams_df.columns:
        teams_df["fifa_code"] = pd.NA
    team_cols = ["id", "team_name", "fifa_code"]

    # Merge Team A
    matches_df = pd.merge(
        matches_raw,
        teams_df[team_cols],
        left_on="home_team_id",
        right_on="id",
        how="left",
    )
    matches_df.rename(columns={"team_name": "team_a", "fifa_code": "team_a_fifa"}, inplace=True)
    if "id" in matches_df.columns:
        matches_df.drop(columns=["id"], inplace=True) # Xóa id của bảng team đi
    
    # Merge Team B
    matches_df = pd.merge(
        matches_df,
        teams_df[team_cols],
        left_on="away_team_id",
        right_on="id",
        how="left",
    )
    matches_df.rename(columns={"team_name": "team_b", "fifa_code": "team_b_fifa"}, inplace=True)
    if "id" in matches_df.columns:
        matches_df.drop(columns=["id"], inplace=True) # Xóa id của bảng team đi

    matches_df["match_id"] = matches_df["match_id"].astype(str)
    matches_df["team_a"] = matches_df["team_a"].fillna("TBD")
    matches_df["team_b"] = matches_df["team_b"].fillna("TBD")
    matches_df["team_a_fifa"] = matches_df["team_a_fifa"].fillna("")
    matches_df["team_b_fifa"] = matches_df["team_b_fifa"].fillna("")
    matches_df["stage_id"] = pd.to_numeric(matches_df["stage_id"], errors="coerce").fillna(1).astype(int)

    from schedule_service import enrich_matches_with_schedule

    return enrich_matches_with_schedule(matches_df)


def vietnam_timestamp() -> str:
    vn_tz = timezone(timedelta(hours=7))
    return datetime.now(vn_tz).strftime("%Y-%m-%d %H:%M:%S")


def normalize_predictions_df(preds_df: pd.DataFrame) -> pd.DataFrame:
    from scoring import normalize_pred_outcome, scores_to_outcome

    if preds_df.empty:
        return pd.DataFrame(
            columns=["user_id", "match_id", "pred_outcome", "pred_advanced_team_id", "timestamp"]
        )

    df = preds_df.copy()
    df.replace("", pd.NA, inplace=True)

    for col in ("pred_outcome", "pred_advanced_team_id"):
        if col not in df.columns:
            df[col] = pd.NA

    if "pred_score_a" in df.columns and "pred_score_b" in df.columns:
        def _legacy_outcome(row):
            current = normalize_pred_outcome(row.get("pred_outcome"))
            if current:
                return current
            try:
                sa, sb = int(float(row["pred_score_a"])), int(float(row["pred_score_b"]))
                return scores_to_outcome(sa, sb)
            except (ValueError, TypeError):
                return None
        df["pred_outcome"] = df.apply(_legacy_outcome, axis=1)
    else:
        df["pred_outcome"] = df["pred_outcome"].apply(normalize_pred_outcome)

    df["user_id"] = df["user_id"].astype(str)
    df["match_id"] = df["match_id"].astype(str)

    keep_cols = ["user_id", "match_id", "pred_outcome", "pred_advanced_team_id", "timestamp"]
    for col in keep_cols:
        if col not in df.columns:
            df[col] = pd.NA

    return df[keep_cols]


def build_prediction_row(
    user_id: str,
    match_id: str,
    pred_outcome: str,
    pred_advanced_team_id=None,
    timestamp: str | None = None,
) -> dict:
    from scoring import normalize_pred_outcome
    return {
        "user_id": str(user_id),
        "match_id": str(match_id),
        "pred_outcome": normalize_pred_outcome(pred_outcome) or "",
        "pred_advanced_team_id": pred_advanced_team_id if pred_advanced_team_id is not None else "",
        "timestamp": timestamp or "",
    }