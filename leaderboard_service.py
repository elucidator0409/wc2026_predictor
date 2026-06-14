"""Leaderboard aggregation: points, fines, ranks, and match insights."""

from __future__ import annotations

import pandas as pd

from scoring import calculate_fines, calculate_points, normalize_pred_outcome
from user_service import _to_vn_timestamp, eligible_finished_matches, is_match_eligible, user_active_from

FINE_MISSED_MATCH = 10

_FORM_EMOJI = {"W": "✅", "L": "❌", "D": "➖"}


def _match_id_col(matches_df: pd.DataFrame) -> str:
    return "id" if "id" in matches_df.columns else "match_id"


def _pred_lookup(preds_df: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    lookup: dict[tuple[str, str], pd.Series] = {}
    if preds_df.empty:
        return lookup
    for _, row in preds_df.iterrows():
        lookup[(str(row["user_id"]), str(row["match_id"]))] = row
    return lookup


def _form_code(has_pred: bool, pts: int) -> str:
    if not has_pred:
        return "D"
    return "W" if pts >= 3 else "L"


def fines_to_vnd(fines_k: int) -> int:
    """Convert fines stored in thousands (10 = 10k) to VND."""
    return int(fines_k) * 1000


def format_fines_vnd(fines_k: int) -> str:
    """Format fines as Vietnamese currency string."""
    vnd = fines_to_vnd(fines_k)
    return f"{vnd:,.0f}".replace(",", ".") + " VNĐ"


def score_finished_match(pred_row: pd.Series | None, match_row: pd.Series) -> tuple[int, int, bool]:
    """Return (points, fines, has_prediction)."""
    if pred_row is None or normalize_pred_outcome(pred_row.get("pred_outcome")) is None:
        return 0, FINE_MISSED_MATCH, False
    merged = {**match_row.to_dict(), **pred_row.to_dict()}
    return calculate_points(merged), calculate_fines(merged), True


def _build_global_finished_order(finished_df: pd.DataFrame) -> pd.DataFrame:
    """Sort finished matches and attach global_order + match_date_vn."""
    finished = finished_df.copy()
    sort_cols = [c for c in ("kickoff_vn", "match_number") if c in finished.columns]
    if sort_cols:
        finished = finished.sort_values(sort_cols).reset_index(drop=True)
    else:
        finished = finished.reset_index(drop=True)

    finished["global_order"] = range(1, len(finished) + 1)
    if "kickoff_vn" in finished.columns:
        kickoffs = finished["kickoff_vn"].apply(_to_vn_timestamp)
        finished["match_date_vn"] = kickoffs.apply(
            lambda ts: ts.date() if ts is not None else pd.NaT
        )
    else:
        finished["match_date_vn"] = pd.NaT
    return finished


def _score_all_user_matches(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
) -> pd.DataFrame:
    """Long DataFrame: one row per eligible user×finished match."""
    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)

    finished = _build_global_finished_order(finished_matches_df)
    id_col = _match_id_col(finished)
    finished[id_col] = finished[id_col].astype(str)

    preds = preds_df.copy()
    if not preds.empty:
        preds["user_id"] = preds["user_id"].astype(str)
        preds["match_id"] = preds["match_id"].astype(str)
    pred_by_key = _pred_lookup(preds)

    rows: list[dict] = []
    for _, user in users.iterrows():
        uid = str(user["user_id"])
        user_finished = eligible_finished_matches(finished, user)
        for _, match in user_finished.iterrows():
            m_id = str(match[id_col])
            pred = pred_by_key.get((uid, m_id))
            pts, fine, has_pred = score_finished_match(pred, match)
            rows.append(
                {
                    "user_id": uid,
                    "name": user["name"],
                    "global_order": int(match["global_order"]),
                    "match_date_vn": match["match_date_vn"],
                    "match_pts": pts,
                    "match_fines": fine,
                    "has_pred": has_pred,
                    "form_code": _form_code(has_pred, pts),
                }
            )

    long_df = pd.DataFrame(rows)
    if long_df.empty:
        return long_df

    long_df = long_df.sort_values(["user_id", "global_order"]).reset_index(drop=True)
    long_df["cum_pts"] = long_df.groupby("user_id")["match_pts"].cumsum()
    long_df["cum_fines"] = long_df.groupby("user_id")["match_fines"].cumsum()
    return long_df


def _aggregate_leaderboard(long_df: pd.DataFrame, users_df: pd.DataFrame) -> pd.DataFrame:
    """Build one row per user from the long match timeline."""
    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)

    if long_df.empty:
        rows = [
            {
                "user_id": str(u["user_id"]),
                "name": u["name"],
                "points": 0,
                "fines": 0,
                "played": 0,
                "correct": 0,
                "missed": 0,
                "total_finished": 0,
            }
            for _, u in users.iterrows()
        ]
        lb = pd.DataFrame(rows)
    else:
        agg = long_df.groupby("user_id", as_index=False).agg(
            points=("match_pts", "sum"),
            fines=("match_fines", "sum"),
            played=("has_pred", "sum"),
            total_finished=("global_order", "count"),
        )
        agg["played"] = agg["played"].astype(int)
        agg["total_finished"] = agg["total_finished"].astype(int)

        correct = (
            long_df[long_df["match_pts"] >= 3]
            .groupby("user_id")
            .size()
            .rename("correct")
        )
        missed = (
            long_df[~long_df["has_pred"]]
            .groupby("user_id")
            .size()
            .rename("missed")
        )
        agg = agg.merge(correct, on="user_id", how="left")
        agg = agg.merge(missed, on="user_id", how="left")
        agg["correct"] = agg["correct"].fillna(0).astype(int)
        agg["missed"] = agg["missed"].fillna(0).astype(int)

        names = users[["user_id", "name"]]
        lb = users[["user_id"]].merge(agg, on="user_id", how="left")
        lb = lb.merge(names, on="user_id", how="left")
        lb["points"] = lb["points"].fillna(0).astype(int)
        lb["fines"] = lb["fines"].fillna(0).astype(int)
        lb["played"] = lb["played"].fillna(0).astype(int)
        lb["correct"] = lb["correct"].fillna(0).astype(int)
        lb["missed"] = lb["missed"].fillna(0).astype(int)
        lb["total_finished"] = lb["total_finished"].fillna(0).astype(int)

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


def build_leaderboard(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    One row per user with totals across all finished matches.
    Users who skipped a finished match receive FINE_MISSED_MATCH for that match.
    """
    long_df = _score_all_user_matches(users_df, preds_df, finished_matches_df)
    return _aggregate_leaderboard(long_df, users_df)


def build_day_end_snapshots(long_df: pd.DataFrame, users_df: pd.DataFrame) -> pd.DataFrame:
    """Per-user cumulative standings at end of each calendar match day."""
    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)

    if long_df.empty:
        return pd.DataFrame(columns=["user_id", "match_date_vn", "cum_pts", "cum_fines", "rank"])

    dates = sorted(long_df["match_date_vn"].dropna().unique())
    if not dates:
        return pd.DataFrame(columns=["user_id", "match_date_vn", "cum_pts", "cum_fines", "rank"])

    snapshots: list[pd.DataFrame] = []
    for match_date in dates:
        subset = long_df[long_df["match_date_vn"] <= match_date]
        day_end = (
            subset.sort_values("global_order")
            .groupby("user_id", as_index=False)
            .last()[["user_id", "cum_pts", "cum_fines"]]
        )
        all_users = users[["user_id"]].copy()
        day_end = all_users.merge(day_end, on="user_id", how="left")
        day_end["cum_pts"] = day_end["cum_pts"].fillna(0).astype(int)
        day_end["cum_fines"] = day_end["cum_fines"].fillna(0).astype(int)
        day_end["match_date_vn"] = match_date
        day_end = day_end.sort_values(
            by=["cum_pts", "cum_fines", "user_id"],
            ascending=[False, True, True],
        ).reset_index(drop=True)
        day_end["rank"] = _competition_rank(day_end, ["cum_pts", "cum_fines"])
        snapshots.append(day_end)

    return pd.concat(snapshots, ignore_index=True)


def _format_rank_movement(delta: int) -> str:
    if delta > 0:
        return f"▲ {delta}"
    if delta < 0:
        return f"▼ {abs(delta)}"
    return "➖"


def _form_to_emoji(codes: list[str]) -> str:
    return "".join(_FORM_EMOJI.get(c, "") for c in codes if c)


def enrich_leaderboard_dynamics(
    lb: pd.DataFrame,
    long_df: pd.DataFrame,
    snapshots: pd.DataFrame,
) -> pd.DataFrame:
    """Attach rank movement, recent form, and points history to leaderboard rows."""
    if lb.empty:
        return lb

    enriched = lb.copy()

    # Rank movement from last two calendar-day snapshots
    movement: dict[str, str] = {}
    movement_delta: dict[str, int] = {}
    if not snapshots.empty:
        dates = sorted(snapshots["match_date_vn"].dropna().unique())
        if len(dates) >= 2:
            prev_date, curr_date = dates[-2], dates[-1]
            prev_ranks = snapshots[snapshots["match_date_vn"] == prev_date].set_index("user_id")["rank"]
            curr_ranks = snapshots[snapshots["match_date_vn"] == curr_date].set_index("user_id")["rank"]
            for uid in enriched["user_id"].astype(str):
                if uid in prev_ranks.index and uid in curr_ranks.index:
                    delta = int(prev_ranks[uid]) - int(curr_ranks[uid])
                    movement_delta[uid] = delta
                    movement[uid] = _format_rank_movement(delta)
                else:
                    movement_delta[uid] = 0
                    movement[uid] = "➖"
        else:
            movement = {uid: "➖" for uid in enriched["user_id"].astype(str)}
            movement_delta = {uid: 0 for uid in enriched["user_id"].astype(str)}
    else:
        movement = {uid: "➖" for uid in enriched["user_id"].astype(str)}
        movement_delta = {uid: 0 for uid in enriched["user_id"].astype(str)}

    enriched["rank_movement_delta"] = (
        enriched["user_id"].astype(str).map(movement_delta).fillna(0).astype(int)
    )
    enriched["rank_movement"] = enriched["user_id"].astype(str).map(movement).fillna("➖")
    enriched["rank_display"] = enriched.apply(
        lambda r: f"{r['rank_label']} {r['rank_movement']}".strip(),
        axis=1,
    )

    # Recent form: last 5 matches per user
    recent_form: dict[str, list[str]] = {}
    recent_display: dict[str, str] = {}
    if not long_df.empty:
        for uid, group in long_df.groupby("user_id"):
            codes = group.sort_values("global_order")["form_code"].tolist()
            last5 = codes[-5:] if len(codes) >= 5 else codes
            recent_form[str(uid)] = last5
            recent_display[str(uid)] = _form_to_emoji(last5)

    enriched["recent_form"] = enriched["user_id"].astype(str).map(recent_form)
    enriched["recent_form"] = enriched["recent_form"].apply(
        lambda v: v if isinstance(v, list) else []
    )
    enriched["recent_form_display"] = (
        enriched["user_id"].astype(str).map(recent_display).fillna("")
    )

    enriched["phat_vnd"] = enriched["fines"].apply(format_fines_vnd)

    return enriched


def build_leaderboard_with_dynamics(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
) -> pd.DataFrame:
    """Full leaderboard with rank movement and recent form."""
    long_df = _score_all_user_matches(users_df, preds_df, finished_matches_df)
    lb = _aggregate_leaderboard(long_df, users_df)
    snapshots = build_day_end_snapshots(long_df, users_df)
    return enrich_leaderboard_dynamics(lb, long_df, snapshots)


def _competition_rank(df: pd.DataFrame, key_cols: list[str]) -> pd.Series:
    ranks = []
    current = 1
    prev_key = None
    for _, row in df.iterrows():
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
