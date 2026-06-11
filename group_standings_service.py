"""Group stage standings for World Cup 2026 (groups A–L)."""

from __future__ import annotations

import pandas as pd

from schedule_service import GROUP_COLORS, group_letter, is_group_stage
from scoring import _parse_int


def _init_team_stats(team_id: str, team_name: str, group: str) -> dict:
    return {
        "team_id": team_id,
        "team_name": team_name,
        "group": group,
        "played": 0,
        "won": 0,
        "drawn": 0,
        "lost": 0,
        "gf": 0,
        "ga": 0,
        "gd": 0,
        "points": 0,
    }


def compute_group_standings(matches_df: pd.DataFrame, teams_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Return standings per group letter A–L from finished group-stage matches."""
    teams_df = teams_df.copy()
    teams_df["id"] = teams_df["id"].astype(str)
    id_to_team = {str(row["id"]): row for _, row in teams_df.iterrows()}

    groups: dict[str, dict[str, dict]] = {}
    for _, team in teams_df.iterrows():
        letter = str(team.get("group_letter", "")).strip().upper()
        if not letter:
            continue
        tid = str(team["id"])
        groups.setdefault(letter, {})[tid] = _init_team_stats(tid, team["team_name"], letter)

    finished = matches_df[
        matches_df["real_score_a"].notna() & matches_df["real_score_b"].notna()
    ].copy()

    for _, row in finished.iterrows():
        if not is_group_stage(row.get("group_round"), row.get("stage_id")):
            continue

        letter = group_letter(row.get("group_round"))
        if not letter or letter not in groups:
            continue

        home_id = str(int(float(row["home_team_id"]))) if pd.notna(row.get("home_team_id")) else ""
        away_id = str(int(float(row["away_team_id"]))) if pd.notna(row.get("away_team_id")) else ""
        if not home_id or not away_id:
            continue

        sa = _parse_int(row["real_score_a"])
        sb = _parse_int(row["real_score_b"])

        for tid, gf, ga, pts, w, d, l in (
            (home_id, sa, sb, 3 if sa > sb else 1 if sa == sb else 0, sa > sb, sa == sb, sa < sb),
            (away_id, sb, sa, 3 if sb > sa else 1 if sa == sb else 0, sb > sa, sa == sb, sb < sa),
        ):
            if tid not in groups[letter]:
                name = id_to_team.get(tid, {}).get("team_name", tid) if tid in id_to_team else tid
                groups[letter][tid] = _init_team_stats(tid, name, letter)
            rec = groups[letter][tid]
            rec["played"] += 1
            rec["gf"] += gf
            rec["ga"] += ga
            rec["gd"] = rec["gf"] - rec["ga"]
            rec["points"] += pts
            rec["won"] += int(w)
            rec["drawn"] += int(d)
            rec["lost"] += int(l)

    result: dict[str, pd.DataFrame] = {}
    for letter in sorted(groups.keys()):
        rows = list(groups[letter].values())
        if not rows:
            continue
        df = pd.DataFrame(rows)
        df = df.sort_values(
            by=["points", "gd", "gf", "team_name"],
            ascending=[False, False, False, True],
        ).reset_index(drop=True)
        df["rank"] = df.index + 1
        df["color"] = GROUP_COLORS.get(letter, "#64748b")
        result[letter] = df

    return result
