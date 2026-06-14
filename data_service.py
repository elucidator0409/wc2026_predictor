"""Shared Google Sheets connection and data helpers."""

import hashlib
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

USERS_COLUMNS = ("user_id", "name", "password", "active_from_kickoff")
PREDICTIONS_COLUMNS = ("user_id", "match_id", "pred_outcome", "pred_advanced_team_id", "timestamp")


def _col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _normalize_header_row(row: list) -> list[str]:
    return [str(h).strip() for h in row]


def _row_looks_like_prediction(row: list) -> bool:
    """Heuristic: row is data (user_id + match_id), not a header."""
    if not row or len(row) < 2:
        return False
    uid = str(row[0]).strip()
    mid = str(row[1]).strip()
    if not uid or not mid:
        return False
    if uid in PREDICTIONS_COLUMNS or uid.lower() in ("user_id", "uid"):
        return False
    if mid in PREDICTIONS_COLUMNS or mid.lower() in ("match_id", "id"):
        return False
    return True


def _predictions_header_offset(data: list[list]) -> int:
    """Return 0 if first row is data; 1 if first row is the header."""
    if not data:
        return 0
    if _normalize_header_row(data[0]) == list(PREDICTIONS_COLUMNS):
        return 1
    if _row_looks_like_prediction(data[0]):
        return 0
    if len(data) > 1 and _row_looks_like_prediction(data[1]):
        return 1
    return 1


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
    if not data or not data[0]:
        return pd.DataFrame()
    headers = [str(h).strip() for h in data[0]]
    if len(data) == 1:
        return pd.DataFrame(columns=headers)
    return pd.DataFrame(data[1:], columns=headers)


def ensure_worksheet(sh, sheet_name: str, rows: int = 120, cols: int = 20):
    """Return worksheet by name, creating it if missing."""
    try:
        return sh.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        return sh.add_worksheet(title=sheet_name, rows=rows, cols=cols)


def write_worksheet_dataframe(sh, sheet_name: str, df: pd.DataFrame) -> None:
    """Replace entire worksheet contents with dataframe (header + rows)."""
    if df.empty:
        values = [[]]
    else:
        safe_df = df.copy()
        for col in safe_df.columns:
            safe_df[col] = safe_df[col].apply(
                lambda v: "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
            )
        values = [safe_df.columns.tolist()] + safe_df.values.tolist()

    row_count = max(len(values) + 5, 50)
    col_count = max(len(values[0]) + 2 if values and values[0] else 5, 10)
    ws = ensure_worksheet(sh, sheet_name, rows=row_count, cols=col_count)
    ws.clear()
    if values and values[0]:
        ws.update(values, value_input_option="USER_ENTERED")


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


def hash_password(password: str) -> str:
    salt = st.secrets.get("password_salt", "MuoiMacDinh_@123")
    return hashlib.sha256((str(password) + salt).encode("utf-8")).hexdigest()


def _parse_active_from_kickoff(series: pd.Series) -> pd.Series:
    kickoff = pd.to_datetime(series, errors="coerce")
    if getattr(kickoff.dt, "tz", None) is None:
        return kickoff.dt.tz_localize(VN_TZ, ambiguous="NaT", nonexistent="NaT")
    return kickoff.dt.tz_convert(VN_TZ)


def normalize_users_df(users_df: pd.DataFrame) -> pd.DataFrame:
    if users_df.empty:
        return pd.DataFrame(columns=list(USERS_COLUMNS))

    df = users_df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df.replace("", pd.NA, inplace=True)

    for col in USERS_COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    if "password" not in df.columns or df["password"].isna().all():
        df["password"] = "1234"

    df["user_id"] = df["user_id"].astype(str)
    df["name"] = df["name"].astype(str)
    df["password"] = df["password"].astype(str)

    active_raw = df["active_from_kickoff"].astype(object)
    str_active = active_raw.astype(str).str.strip()
    has_active = (
        active_raw.notna()
        & ~str_active.isin(["", "nan", "NaT", "None", "<NA>"])
    )

    parsed_active = pd.Series(index=df.index, dtype=object)
    parsed_active.loc[:] = pd.NaT
    if has_active.any():
        parsed = _parse_active_from_kickoff(active_raw.loc[has_active].astype(str))
        parsed_active.loc[has_active] = parsed.to_numpy()
    df["active_from_kickoff"] = parsed_active

    return df[list(USERS_COLUMNS)]


def append_user_row(sh, row_dict: dict) -> None:
    """Append one user row to the users worksheet."""
    ws = sh.worksheet("users")
    data = ws.get_all_values()
    headers = [str(h).strip() for h in data[0]] if data and data[0] else list(USERS_COLUMNS)

    if "active_from_kickoff" not in headers:
        headers.append("active_from_kickoff")
        if data:
            end_col = _col_letter(len(headers))
            ws.update(f"A1:{end_col}1", [headers], value_input_option="USER_ENTERED")

    row = {col: "" for col in headers}
    for key, value in row_dict.items():
        if key in row and value is not None and not (isinstance(value, float) and pd.isna(value)):
            row[key] = str(value)

    ws.append_row([row.get(h, "") for h in headers], value_input_option="USER_ENTERED")


def normalize_predictions_df(preds_df: pd.DataFrame) -> pd.DataFrame:
    from scoring import normalize_pred_outcome, scores_to_outcome

    if preds_df.empty:
        return pd.DataFrame(columns=list(PREDICTIONS_COLUMNS))

    df = preds_df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    df.replace("", pd.NA, inplace=True)

    for col in PREDICTIONS_COLUMNS:
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

    invalid_uid = df["user_id"].isin(["", "nan", "None", "<NA>"]) | df["user_id"].isin(PREDICTIONS_COLUMNS)
    df = df[~invalid_uid].copy()

    return df[list(PREDICTIONS_COLUMNS)]


def read_predictions_sheet(sh) -> pd.DataFrame:
    """
    Read predictions tab with positional fallback when header is missing or wrong.
    Never writes to the sheet.
    """
    data = sh.worksheet("predictions").get_all_values()
    if not data:
        return pd.DataFrame(columns=list(PREDICTIONS_COLUMNS))

    offset = _predictions_header_offset(data)
    records = []
    for row in data[offset:]:
        padded = list(row) + [""] * len(PREDICTIONS_COLUMNS)
        padded = padded[: len(PREDICTIONS_COLUMNS)]
        if _row_looks_like_prediction(padded):
            records.append(padded)

    if not records:
        return pd.DataFrame(columns=list(PREDICTIONS_COLUMNS))

    df = pd.DataFrame(records, columns=list(PREDICTIONS_COLUMNS))
    return normalize_predictions_df(df)


def repair_predictions_sheet_header(ws) -> str:
    """
    Safely fix header row without deleting prediction data.
    Returns: 'ok' | 'created_header' | 'inserted_header' | 'fixed_header'
    """
    data = ws.get_all_values()
    expected = list(PREDICTIONS_COLUMNS)

    if not data:
        ws.update("A1:E1", [expected], value_input_option="USER_ENTERED")
        return "created_header"

    row1 = _normalize_header_row(data[0])
    if row1 == expected:
        return "ok"

    if _row_looks_like_prediction(data[0]):
        ws.insert_row(expected, index=1, value_input_option="USER_ENTERED")
        return "inserted_header"

    ws.update("A1:E1", [expected], value_input_option="USER_ENTERED")
    return "fixed_header"


def upsert_user_predictions(
    ws,
    user_id: str,
    entries: list[tuple[str, str, str, str]],
) -> tuple[int, int]:
    """
    Update or append prediction rows by (user_id, match_id).
    entries: list of (match_id, pred_outcome, pred_advanced_team_id, timestamp)
    Returns (n_updated, n_inserted).
    """
    data = ws.get_all_values()
    offset = _predictions_header_offset(data)

    existing_rows: dict[tuple[str, str], int] = {}
    for i, row in enumerate(data[offset:], start=offset + 1):
        if len(row) >= 2:
            existing_rows[(str(row[0]).strip(), str(row[1]).strip())] = i

    updates = []
    new_rows = []
    uid = str(user_id)
    for match_id, outcome, adv_id, ts in entries:
        pred_row = [uid, str(match_id), outcome or "", adv_id or "", ts or ""]
        key = (uid, str(match_id))
        if key in existing_rows:
            row_idx = existing_rows[key]
            updates.append({"range": f"A{row_idx}:E{row_idx}", "values": [pred_row]})
        else:
            new_rows.append(pred_row)

    if updates:
        ws.batch_update(updates)
    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    return len(updates), len(new_rows)


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