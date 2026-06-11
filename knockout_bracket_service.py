"""Knockout tournament bracket — two-sided layout, scores from admin."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from schedule_service import STAGE_ID_COLORS, STAGE_ID_LABELS_VN
from scoring import _clean_team_id, _parse_int

BRACKET_HALF_STAGES = (2, 3, 4, 5)
FINAL_STAGE_ID = 7
THIRD_PLACE_STAGE_ID = 6


@dataclass
class BracketTeam:
    name: str
    fifa_code: str | None
    score_display: str
    is_winner: bool


@dataclass
class BracketMatch:
    match_id: str
    match_number: int
    match_label: str
    team_a: BracketTeam
    team_b: BracketTeam
    is_finished: bool


def _is_finished(row) -> bool:
    return pd.notna(row.get("real_score_a")) and pd.notna(row.get("real_score_b"))


def _resolve_winner_side(row) -> str | None:
    if not _is_finished(row):
        return None
    ra = _parse_int(row["real_score_a"])
    rb = _parse_int(row["real_score_b"])
    if ra > rb:
        return "a"
    if rb > ra:
        return "b"
    adv = _clean_team_id(row.get("real_advanced_team_id"))
    home = _clean_team_id(row.get("home_team_id"))
    away = _clean_team_id(row.get("away_team_id"))
    if adv and home and adv == home:
        return "a"
    if adv and away and adv == away:
        return "b"
    return None


def _score_display(row, side: str, winner_side: str | None) -> str:
    if not _is_finished(row):
        return "—"
    ra = _parse_int(row["real_score_a"])
    rb = _parse_int(row["real_score_b"])
    score = ra if side == "a" else rb
    if ra == rb and winner_side:
        if winner_side == side:
            return f"{score} PEN"
        return str(score)
    return str(score)


def _row_to_bracket_match(row) -> BracketMatch:
    winner = _resolve_winner_side(row)
    team_a_name = str(row.get("team_a") or "TBD")
    team_b_name = str(row.get("team_b") or "TBD")
    m_id = str(row.get("match_id") if "match_id" in row.index else row.get("id", ""))

    return BracketMatch(
        match_id=m_id,
        match_number=int(float(row["match_number"])),
        match_label=str(row.get("match_label") or ""),
        team_a=BracketTeam(
            name=team_a_name,
            fifa_code=row.get("team_a_fifa"),
            score_display=_score_display(row, "a", winner),
            is_winner=winner == "a",
        ),
        team_b=BracketTeam(
            name=team_b_name,
            fifa_code=row.get("team_b_fifa"),
            score_display=_score_display(row, "b", winner),
            is_winner=winner == "b",
        ),
        is_finished=_is_finished(row),
    )


def _split_half(matches: list[BracketMatch]) -> tuple[list[BracketMatch], list[BracketMatch]]:
    if not matches:
        return [], []
    mid = len(matches) // 2
    return matches[:mid], matches[mid:]


def _round_dict(stage_id: int, matches: list[BracketMatch]) -> dict:
    return {
        "stage_id": stage_id,
        "label": STAGE_ID_LABELS_VN.get(stage_id, f"Vòng {stage_id}"),
        "color": STAGE_ID_COLORS.get(stage_id, "#64748b"),
        "matches": matches,
    }


def build_knockout_bracket(matches_df: pd.DataFrame) -> dict:
    """Two-sided bracket: left half + center final + right half (mirrored)."""
    ko = matches_df[matches_df["stage_id"].apply(lambda x: int(float(x)) > 1 if pd.notna(x) else False)].copy()
    if ko.empty:
        return {
            "left_rounds": [],
            "right_rounds": [],
            "final": None,
            "third_place": None,
            "has_data": False,
        }

    ko["stage_id"] = ko["stage_id"].apply(lambda x: int(float(x)))
    ko["match_number"] = pd.to_numeric(ko["match_number"], errors="coerce")

    left_rounds = []
    right_rounds = []

    for stage_id in BRACKET_HALF_STAGES:
        stage_matches = ko[ko["stage_id"] == stage_id].sort_values("match_number")
        if stage_matches.empty:
            continue
        all_matches = [_row_to_bracket_match(row) for _, row in stage_matches.iterrows()]
        left, right = _split_half(all_matches)
        if left:
            left_rounds.append(_round_dict(stage_id, left))
        if right:
            right_rounds.append(_round_dict(stage_id, right))

    final = None
    final_rows = ko[ko["stage_id"] == FINAL_STAGE_ID].sort_values("match_number")
    if not final_rows.empty:
        final = _row_to_bracket_match(final_rows.iloc[0])

    third_place = None
    tp_rows = ko[ko["stage_id"] == THIRD_PLACE_STAGE_ID].sort_values("match_number")
    if not tp_rows.empty:
        third_place = _row_to_bracket_match(tp_rows.iloc[0])

    has_data = bool(left_rounds or right_rounds or final)

    return {
        "left_rounds": left_rounds,
        "right_rounds": right_rounds,
        "final": final,
        "third_place": third_place,
        "has_data": has_data,
    }
