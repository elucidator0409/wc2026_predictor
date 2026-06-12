"""Player squad data — load, join teams, filter."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from data_service import read_sheet

PLAYERS_SHEET_NAME = "wc2026_full_players_1200"
PLAYERS_CSV_PATH = Path(__file__).parent / "data" / "wc2026_full_players_1200.csv"

POSITION_ORDER = ("GK", "DF", "MF", "FW")
POSITION_LABELS = {
    "GK": "Thủ môn",
    "DF": "Hậu vệ",
    "MF": "Tiền vệ",
    "FW": "Tiền đạo",
}

TEAM_CODE_ALIASES = {"CUW": "CUR"}

# Player CSV team name -> teams sheet fifa_code (when names differ)
TEAM_NAME_TO_FIFA = {
    "Czechia": "CZE",
    "Korea Republic": "KOR",
    "Türkiye": "TUR",
    "Côte D'Ivoire": "CIV",
    "Congo DR": "COD",
}


def normalize_team_code(code) -> str:
    if code is None or (isinstance(code, float) and pd.isna(code)):
        return ""
    text = str(code).strip().upper()
    return TEAM_CODE_ALIASES.get(text, text)


def _clean_text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def load_players_df(sh=None) -> pd.DataFrame:
    """Load players from Google Sheet or local CSV fallback."""
    if sh is not None:
        try:
            raw = read_sheet(sh, PLAYERS_SHEET_NAME)
            if not raw.empty:
                return _normalize_players_raw(raw)
        except Exception:
            pass
    if PLAYERS_CSV_PATH.exists():
        return _normalize_players_raw(pd.read_csv(PLAYERS_CSV_PATH))
    return pd.DataFrame(
        columns=[
            "team",
            "team_code",
            "position",
            "player_name",
            "player_name_raw",
            "dob",
            "club",
            "height_cm",
            "caps",
            "goals",
        ]
    )


def _normalize_players_raw(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.replace("", pd.NA, inplace=True)
    for col in ("team", "team_code", "position", "player_name", "club", "dob"):
        if col in out.columns:
            out[col] = out[col].apply(_clean_text)
    out["team_code"] = out["team_code"].apply(normalize_team_code)
    out["position"] = out["position"].str.upper()
    out["height_cm"] = pd.to_numeric(out.get("height_cm"), errors="coerce").fillna(0).astype(int)
    out["caps"] = pd.to_numeric(out.get("caps"), errors="coerce").fillna(0).astype(int)
    out["goals"] = pd.to_numeric(out.get("goals"), errors="coerce").fillna(0).astype(int)
    return out


def prep_players(players_df: pd.DataFrame, teams_df: pd.DataFrame) -> pd.DataFrame:
    """Join player rows with teams sheet metadata (fifa_code, group, team_id)."""
    if players_df.empty:
        return players_df

    players = players_df.copy()
    teams = teams_df.copy()
    teams.replace("", pd.NA, inplace=True)
    teams["fifa_code"] = teams["fifa_code"].astype(str).str.strip().str.upper()

    fifa_to_team: dict[str, dict] = {}
    name_to_fifa: dict[str, str] = {}
    for _, row in teams.iterrows():
        code = str(row.get("fifa_code", "")).strip().upper()
        if code:
            fifa_to_team[code] = row.to_dict()
        name = str(row.get("team_name", "")).strip()
        if name and code:
            name_to_fifa[name] = code

    for csv_name, code in TEAM_NAME_TO_FIFA.items():
        name_to_fifa[csv_name] = code

    def resolve_fifa(row) -> str:
        code = normalize_team_code(row.get("team_code"))
        if code and code in fifa_to_team:
            return code
        team_name = str(row.get("team", "")).strip()
        return name_to_fifa.get(team_name, code)

    players["fifa_code"] = players.apply(resolve_fifa, axis=1)

    def sheet_meta(code: str, field: str, fallback: str = "") -> str:
        meta = fifa_to_team.get(code, {})
        val = meta.get(field)
        return str(val).strip() if val is not None and not (isinstance(val, float) and pd.isna(val)) else fallback

    players["team_id"] = players["fifa_code"].map(lambda c: sheet_meta(c, "id"))
    players["team_name_sheet"] = players.apply(
        lambda r: sheet_meta(r["fifa_code"], "team_name", str(r.get("team", ""))),
        axis=1,
    )
    players["group_letter"] = players["fifa_code"].map(
        lambda c: str(fifa_to_team.get(c, {}).get("group_letter", "")).strip().upper()
    )
    return players


def filter_squad(
    df: pd.DataFrame,
    fifa_code: str,
    position: str | None = None,
    search: str = "",
) -> pd.DataFrame:
    """Filter squad for one team; optional position and name/club search."""
    if df.empty:
        return df

    code = normalize_team_code(fifa_code)
    squad = df[df["fifa_code"] == code].copy()
    if position and position.upper() != "ALL":
        squad = squad[squad["position"] == position.upper()]

    query = _clean_text(search).lower()
    if query:
        mask = squad["player_name"].str.lower().str.contains(query, na=False) | squad["club"].str.lower().str.contains(
            query, na=False
        )
        squad = squad[mask]

    squad["_pos_order"] = squad["position"].map({p: i for i, p in enumerate(POSITION_ORDER)}).fillna(99)
    squad = squad.sort_values(["_pos_order", "goals", "caps", "player_name"], ascending=[True, False, False, True])
    return squad.drop(columns=["_pos_order"], errors="ignore")


def squad_summary(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"count": 0, "total_caps": 0, "total_goals": 0, "avg_height": 0}
    heights = df["height_cm"].replace(0, pd.NA)
    avg_h = round(float(heights.mean()), 1) if heights.notna().any() else 0
    return {
        "count": len(df),
        "total_caps": int(df["caps"].sum()),
        "total_goals": int(df["goals"].sum()),
        "avg_height": avg_h,
    }


def top_players(df: pd.DataFrame, fifa_code: str, limit: int = 3) -> pd.DataFrame:
    """Top scorers for mini squad panel (goals desc, caps desc)."""
    squad = filter_squad(df, fifa_code)
    if squad.empty:
        return squad
    return squad.sort_values(["goals", "caps", "player_name"], ascending=[False, False, True]).head(limit)


def team_options(teams_df: pd.DataFrame) -> list[dict]:
    """Sorted team picker entries for UI."""
    teams = teams_df.copy()
    teams.replace("", pd.NA, inplace=True)
    teams = teams.sort_values(["group_letter", "team_name"])
    options = []
    for _, row in teams.iterrows():
        code = str(row.get("fifa_code", "")).strip().upper()
        if not code:
            continue
        group = str(row.get("group_letter", "")).strip().upper()
        label = f"{code} · {row['team_name']}" + (f" (Bảng {group})" if group else "")
        options.append(
            {
                "fifa_code": code,
                "team_name": str(row["team_name"]),
                "group_letter": group,
                "label": label,
            }
        )
    return options


def squad_by_position(df: pd.DataFrame) -> dict[str, list[dict]]:
    """Group filtered squad rows by position for HTML table render."""
    grouped: dict[str, list[dict]] = {p: [] for p in POSITION_ORDER}
    for _, row in df.iterrows():
        pos = str(row.get("position", ""))
        if pos in grouped:
            grouped[pos].append(row.to_dict())
    return {k: v for k, v in grouped.items() if v}
