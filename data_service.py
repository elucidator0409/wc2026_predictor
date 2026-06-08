"""Shared Google Sheets connection and data helpers."""

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

    for col in ("real_score_a", "real_score_b", "real_advanced_team_id"):
        if col not in matches_raw.columns:
            matches_raw[col] = None

    if "is_locked" not in matches_raw.columns:
        matches_raw["is_locked"] = False
    else:
        matches_raw["is_locked"] = (
            matches_raw["is_locked"].astype(str).str.strip().str.upper() == "TRUE"
        )

    matches_raw["home_team_id"] = (
        pd.to_numeric(matches_raw["home_team_id"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )
    matches_raw["away_team_id"] = (
        pd.to_numeric(matches_raw["away_team_id"], errors="coerce")
        .fillna(0)
        .astype(int)
        .astype(str)
    )
    teams_df = teams_df.copy()
    teams_df["id"] = (
        pd.to_numeric(teams_df["id"], errors="coerce").fillna(0).astype(int).astype(str)
    )

    matches_df = pd.merge(
        matches_raw,
        teams_df[["id", "team_name"]],
        left_on="home_team_id",
        right_on="id",
        how="left",
    )
    matches_df.rename(columns={"team_name": "team_a"}, inplace=True)
    matches_df.drop("id_y", axis=1, inplace=True, errors="ignore")

    matches_df = pd.merge(
        matches_df,
        teams_df[["id", "team_name"]],
        left_on="away_team_id",
        right_on="id",
        how="left",
    )
    matches_df.rename(columns={"team_name": "team_b"}, inplace=True)
    matches_df.drop("id", axis=1, inplace=True, errors="ignore")

    matches_df.rename(columns={"id_x": "match_id"}, inplace=True, errors="ignore")
    matches_df["match_id"] = matches_df["match_id"].astype(str)
    matches_df["team_a"] = matches_df["team_a"].fillna("TBD")
    matches_df["team_b"] = matches_df["team_b"].fillna("TBD")
    matches_df["stage_id"] = (
        pd.to_numeric(matches_df["stage_id"], errors="coerce").fillna(1).astype(int)
    )
    return matches_df
