"""Scoring and display helpers for A/D/B outcome predictions.

Canonical codes stored in pred_outcome:
  A — Team A (home / first listed) wins
  D — Draw
  B — Team B (away / second listed) wins

Legacy W/D/L is accepted on read (W→A, L→B) for existing sheet rows.
"""

from __future__ import annotations

import pandas as pd

OUTCOMES = ("A", "D", "B")

LEGACY_OUTCOME_MAP = {"W": "A", "D": "D", "L": "B"}

OUTCOME_LABELS = {
    "A": "Đội A thắng",
    "D": "Hòa",
    "B": "Đội B thắng",
}


def scores_to_outcome(score_a: int, score_b: int) -> str:
    if score_a > score_b:
        return "A"
    if score_a < score_b:
        return "B"
    return "D"


def normalize_pred_outcome(value) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().upper()
    if text in OUTCOMES:
        return text
    return LEGACY_OUTCOME_MAP.get(text)


def _parse_int(value, default: int = 0) -> int:
    try:
        if pd.isna(value) or str(value).strip() == "":
            return default
        return int(float(value))
    except (ValueError, TypeError):
        return default


def _parse_stage(row) -> int:
    try:
        return int(float(row.get("stage_id", 1)))
    except (ValueError, TypeError):
        return 1


def _clean_team_id(val) -> str:
    if pd.isna(val) or str(val).strip() == "":
        return ""
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return str(val).strip()


def calculate_points(row) -> int:
    try:
        real_a, real_b = _parse_int(row["real_score_a"]), _parse_int(row["real_score_b"])
        pred_outcome = normalize_pred_outcome(row.get("pred_outcome"))
        if pred_outcome is None:
            return 0
    except (KeyError, TypeError):
        return 0

    real_outcome = scores_to_outcome(real_a, real_b)
    points = 3 if pred_outcome == real_outcome else 0
    stage = _parse_stage(row)

    if stage > 1 and real_outcome == "D" and pred_outcome == "D":
        pred_adv, real_adv = row.get("pred_advanced_team_id"), row.get("real_advanced_team_id")
        if _clean_team_id(pred_adv) and _clean_team_id(real_adv) and _clean_team_id(pred_adv) == _clean_team_id(real_adv):
            points += 1
    return points


def calculate_fines(row) -> int:
    try:
        real_a, real_b = _parse_int(row["real_score_a"]), _parse_int(row["real_score_b"])
        pred_outcome = normalize_pred_outcome(row.get("pred_outcome"))
        if pred_outcome is None:
            return 10
    except (KeyError, TypeError):
        return 10

    return 0 if pred_outcome == scores_to_outcome(real_a, real_b) else 10


def outcome_to_analytics_key(outcome: str) -> str:
    normalized = normalize_pred_outcome(outcome)
    return {"A": "Win_A", "D": "Draw", "B": "Win_B"}.get(normalized or "", "Unknown")


def _matchup_line(flag_a: str, team_a: str, flag_b: str, team_b: str) -> str:
    return f"{flag_a} {team_a} - {flag_b} {team_b}"


def _pred_result_line(matchup: str, result: str) -> str:
    return f"{matchup} → {result}"


def format_pred_display(
    outcome,
    team_a: str = "",
    team_b: str = "",
    adv_team_name: str | None = None,
    is_knockout: bool = False,
    name_to_fifa: dict | None = None,
    team_a_fifa: str | None = None,
    team_b_fifa: str | None = None,
) -> str:
    from team_flags import flag_emoji

    outcome = normalize_pred_outcome(outcome)
    if outcome is None:
        return "—"

    if outcome == "A" and team_a:
        flag_a = flag_emoji(team_a_fifa, team_a, name_to_fifa)
        flag_b = flag_emoji(team_b_fifa, team_b, name_to_fifa)
        matchup = _matchup_line(flag_a, team_a, flag_b, team_b)
        base = _pred_result_line(matchup, f"{flag_a} {team_a} thắng")
    elif outcome == "B" and team_b:
        flag_a = flag_emoji(team_a_fifa, team_a, name_to_fifa)
        flag_b = flag_emoji(team_b_fifa, team_b, name_to_fifa)
        matchup = _matchup_line(flag_a, team_a, flag_b, team_b)
        base = _pred_result_line(matchup, f"{flag_b} {team_b} thắng")
    elif outcome == "D":
        if team_a and team_b:
            flag_a = flag_emoji(team_a_fifa, team_a, name_to_fifa)
            flag_b = flag_emoji(team_b_fifa, team_b, name_to_fifa)
            matchup = _matchup_line(flag_a, team_a, flag_b, team_b)
            base = _pred_result_line(matchup, "🤝 Hòa")
        else:
            base = "🤝 Hòa"
    else:
        base = OUTCOME_LABELS.get(outcome, outcome)

    if is_knockout and outcome == "D" and adv_team_name:
        base += f" · PEN: {flag_emoji(team_name=adv_team_name, name_to_fifa=name_to_fifa)} {adv_team_name}"
    return base


def format_real_display(score_a, score_b, adv_name: str | None = None, stage: int = 1) -> str:
    sa, sb = _parse_int(score_a), _parse_int(score_b)
    base = f"{sa} - {sb}"
    if stage > 1 and sa == sb and adv_name:
        base += f" (PEN: {adv_name})"
    return base


def outcome_label_for_team(outcome: str, team_a: str, team_b: str) -> str:
    outcome = normalize_pred_outcome(outcome)
    if outcome == "A":
        return _pred_result_line(f"{team_a} - {team_b}", f"{team_a} thắng")
    if outcome == "B":
        return _pred_result_line(f"{team_a} - {team_b}", f"{team_b} thắng")
    return "Hòa"


def _team_code(team_name: str, fifa_code: str | None, name_to_fifa: dict | None) -> str:
    if fifa_code and str(fifa_code).strip():
        return str(fifa_code).strip().upper()
    if name_to_fifa and team_name in name_to_fifa:
        return str(name_to_fifa[team_name]).strip().upper()
    return team_name[:3].upper() if team_name else "???"


def is_match_finished(row) -> bool:
    try:
        return pd.notna(row["real_score_a"]) and pd.notna(row["real_score_b"])
    except (KeyError, TypeError):
        return False


def format_matchup_display(
    team_a: str = "",
    team_b: str = "",
    name_to_fifa: dict | None = None,
    team_a_fifa: str | None = None,
    team_b_fifa: str | None = None,
    compact: bool = True,
) -> str:
    from team_flags import flag_emoji

    if not team_a or not team_b:
        return "—"
    flag_a = flag_emoji(team_a_fifa, team_a, name_to_fifa)
    flag_b = flag_emoji(team_b_fifa, team_b, name_to_fifa)
    if compact:
        code_a = _team_code(team_a, team_a_fifa, name_to_fifa)
        code_b = _team_code(team_b, team_b_fifa, name_to_fifa)
        return f"{flag_a} {code_a} - {flag_b} {code_b}"
    return _matchup_line(flag_a, team_a, flag_b, team_b)


def format_pred_pick(
    outcome,
    team_a: str = "",
    team_b: str = "",
    adv_team_name: str | None = None,
    is_knockout: bool = False,
    name_to_fifa: dict | None = None,
    team_a_fifa: str | None = None,
    team_b_fifa: str | None = None,
) -> str:
    from team_flags import flag_emoji

    outcome = normalize_pred_outcome(outcome)
    if outcome is None:
        return "—"
    if outcome == "A" and team_a:
        flag_a = flag_emoji(team_a_fifa, team_a, name_to_fifa)
        return f"{flag_a} thắng"
    if outcome == "B" and team_b:
        flag_b = flag_emoji(team_b_fifa, team_b, name_to_fifa)
        return f"{flag_b} thắng"
    if outcome == "D":
        base = "🤝 Hòa"
        if is_knockout and adv_team_name:
            pen_flag = flag_emoji(team_name=adv_team_name, name_to_fifa=name_to_fifa)
            base += f" · PEN: {pen_flag} {_team_code(adv_team_name, None, name_to_fifa)}"
        return base
    return OUTCOME_LABELS.get(outcome, outcome)


def format_history_verdict(row) -> str:
    if not is_match_finished(row):
        return "⏳ Chưa đá"
    points = calculate_points(row)
    if points > 0:
        return f"✅ +{points}"
    fines = calculate_fines(row)
    if fines > 0:
        return f"❌ phạt {fines}k"
    return "✅ +0"


def format_history_timestamp(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        return pd.to_datetime(value).strftime("%d/%m · %H:%M")
    except (ValueError, TypeError):
        text = str(value).strip()
        if len(text) >= 16:
            return text[8:10] + "/" + text[5:7] + " · " + text[11:16]
        return text
