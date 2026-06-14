"""Leaderboard aggregation: points, fines, ranks, and match insights."""

from __future__ import annotations

import pandas as pd

from scoring import calculate_fines, calculate_points, normalize_pred_outcome
from user_service import eligible_finished_matches, is_match_eligible, user_active_from

FINE_MISSED_MATCH = 10


def _match_id_col(matches_df: pd.DataFrame) -> str:
    return "id" if "id" in matches_df.columns else "match_id"


def _pred_lookup(preds_df: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    lookup: dict[tuple[str, str], pd.Series] = {}
    if preds_df.empty:
        return lookup
    for _, row in preds_df.iterrows():
        lookup[(str(row["user_id"]), str(row["match_id"]))] = row
    return lookup


def score_finished_match(pred_row: pd.Series | None, match_row: pd.Series) -> tuple[int, int, bool]:
    """Return (points, fines, has_prediction)."""
    if pred_row is None or normalize_pred_outcome(pred_row.get("pred_outcome")) is None:
        return 0, FINE_MISSED_MATCH, False
    merged = {**match_row.to_dict(), **pred_row.to_dict()}
    return calculate_points(merged), calculate_fines(merged), True


def build_leaderboard(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    One row per user with totals across all finished matches.
    Users who skipped a finished match receive FINE_MISSED_MATCH for that match.
    """
    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)

    id_col = _match_id_col(finished_matches_df)
    finished = finished_matches_df.copy()
    finished[id_col] = finished[id_col].astype(str)

    preds = preds_df.copy()
    if not preds.empty:
        preds["user_id"] = preds["user_id"].astype(str)
        preds["match_id"] = preds["match_id"].astype(str)
    pred_by_key = _pred_lookup(preds)

    rows = []
    for _, user in users.iterrows():
        uid = str(user["user_id"])
        points = fines = correct = played = missed = 0
        user_finished = eligible_finished_matches(finished, user)
        for _, match in user_finished.iterrows():
            m_id = str(match[id_col])
            pred = pred_by_key.get((uid, m_id))
            pts, fine, has_pred = score_finished_match(pred, match)
            points += pts
            fines += fine
            if has_pred:
                played += 1
                if pts >= 3:
                    correct += 1
            else:
                missed += 1
        rows.append(
            {
                "user_id": uid,
                "name": user["name"],
                "points": points,
                "fines": fines,
                "played": played,
                "correct": correct,
                "missed": missed,
                "total_finished": len(user_finished),
            }
        )

    lb = pd.DataFrame(rows)
    if lb.empty:
        return lb

    lb["hit_rate"] = lb.apply(
        lambda r: round(r["correct"] / r["played"] * 100, 1) if r["played"] > 0 else 0.0,
        axis=1,
    )
    lb = lb.sort_values(by=["points", "fines", "name"], ascending=[False, True, True]).reset_index(drop=True)
    lb["rank"] = _competition_rank(lb, ["points", "fines"])
    lb["rank_label"] = lb["rank"].apply(_rank_label)
    return lb


def _competition_rank(df: pd.DataFrame, key_cols: list[str]) -> pd.Series:
    ranks = []
    current = 1
    prev_key = None
    for i, row in df.iterrows():
        key = tuple(row[c] for c in key_cols)
        if prev_key is not None and key != prev_key:
            current = len(ranks) + 1
        ranks.append(current)
        prev_key = key
    return pd.Series(ranks, index=df.index)


def _rank_label(rank: int) -> str:
    if rank == 1:
        return "🥇"
    if rank == 2:
        return "🥈"
    if rank == 3:
        return "🥉"
    return str(rank)


def podium_entries(lb: pd.DataFrame, limit: int = 3) -> list[dict]:
    """Top distinct ranks for podium; may be fewer than 3 if heavy ties at top."""
    if lb.empty:
        return []
    entries = []
    seen_ranks = set()
    for _, row in lb.iterrows():
        r = int(row["rank"])
        if r in seen_ranks:
            continue
        seen_ranks.add(r)
        tie_count = int((lb["rank"] == r).sum())
        entries.append(
            {
                "rank": r,
                "name": row["name"],
                "points": int(row["points"]),
                "fines": int(row["fines"]),
                "tie_count": tie_count,
            }
        )
        if len(entries) >= limit:
            break
    return entries


def top_rank_tie_count(lb: pd.DataFrame) -> int:
    if lb.empty:
        return 0
    return int((lb["rank"] == 1).sum())


def latest_match_insight(
    finished_matches_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    users_df: pd.DataFrame,
) -> dict | None:
    """Summary for the most recently finished match."""
    if finished_matches_df.empty:
        return None

    id_col = _match_id_col(finished_matches_df)
    finished = finished_matches_df.copy()
    finished["match_number"] = pd.to_numeric(finished["match_number"], errors="coerce")
    if "kickoff_vn" in finished.columns:
        latest = finished.sort_values(["kickoff_vn", "match_number"]).iloc[-1]
    else:
        latest = finished.sort_values("match_number").iloc[-1]

    m_id = str(latest[id_col])
    preds = preds_df.copy()
    if not preds.empty:
        preds["match_id"] = preds["match_id"].astype(str)
        preds["user_id"] = preds["user_id"].astype(str)

    pred_by_key = _pred_lookup(preds)
    total_users = 0
    correct = wrong = missed = 0

    for _, user in users_df.iterrows():
        if not is_match_eligible(latest, user_active_from(user)):
            continue
        total_users += 1
        uid = str(user["user_id"])
        pred = pred_by_key.get((uid, m_id))
        pts, _, has_pred = score_finished_match(pred, latest)
        if not has_pred:
            missed += 1
        elif pts >= 3:
            correct += 1
        else:
            wrong += 1

    code_a = latest.get("team_a_fifa") or (str(latest.get("team_a", ""))[:3].upper())
    code_b = latest.get("team_b_fifa") or (str(latest.get("team_b", ""))[:3].upper())
    score_a = latest.get("real_score_a")
    score_b = latest.get("real_score_b")

    return {
        "match_number": int(latest["match_number"]) if pd.notna(latest.get("match_number")) else m_id,
        "matchup": f"{code_a} {score_a}–{score_b} {code_b}",
        "correct": correct,
        "wrong": wrong,
        "missed": missed,
        "total_users": total_users,
    }
