"""Analytics aggregations for prediction-style dashboard (pure pandas)."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd

from scoring import calculate_points, normalize_pred_outcome
from user_service import is_match_eligible, user_active_from

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

OUTCOME_ORDER = ("A", "D", "B")

OUTCOME_LABELS = {
    "A": "Đội A thắng",
    "D": "Hòa",
    "B": "Đội B thắng",
}

RISK_PICK_LABELS = {
    "Safe": "Cửa trên (theo đám đông)",
    "Risky": "Cửa dưới (ngược số đông)",
}

RISK_CHART_COLORS = {
    "Safe": "#60a5fa",
    "Risky": "#fb923c",
}

_OUTCOME_RANK = {code: idx for idx, code in enumerate(OUTCOME_ORDER)}


def _match_id_col(matches_df: pd.DataFrame) -> str:
    return "id" if "id" in matches_df.columns else "match_id"


def derive_actual_outcome(df: pd.DataFrame) -> pd.Series:
    score_a = pd.to_numeric(df["real_score_a"], errors="coerce")
    score_b = pd.to_numeric(df["real_score_b"], errors="coerce")
    outcome = pd.Series(pd.NA, index=df.index, dtype="object")
    valid = score_a.notna() & score_b.notna()
    outcome.loc[valid & (score_a > score_b)] = "A"
    outcome.loc[valid & (score_a < score_b)] = "B"
    outcome.loc[valid & (score_a == score_b)] = "D"
    return outcome


def _normalize_kickoff(series: pd.Series) -> pd.Series:
    kickoff = pd.to_datetime(series, errors="coerce")
    if getattr(kickoff.dt, "tz", None) is None:
        return kickoff.dt.tz_localize(VN_TZ, ambiguous="NaT", nonexistent="NaT")
    return kickoff.dt.tz_convert(VN_TZ)


def _parse_prediction_timestamp(series: pd.Series) -> pd.Series:
    ts = pd.to_datetime(series, errors="coerce")
    if getattr(ts.dt, "tz", None) is None:
        return ts.dt.tz_localize(VN_TZ, ambiguous="NaT", nonexistent="NaT")
    return ts.dt.tz_convert(VN_TZ)


def _filter_merged_by_user_eligibility(
    merged: pd.DataFrame,
    users_df: pd.DataFrame,
) -> pd.DataFrame:
    if merged.empty or "kickoff_vn" not in merged.columns:
        return merged

    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)
    active_map = {
        str(row["user_id"]): user_active_from(row)
        for _, row in users.iterrows()
    }

    mask = merged.apply(
        lambda row: is_match_eligible(row, active_map.get(str(row["user_id"]))),
        axis=1,
    )
    return merged[mask].copy()


def build_scored_predictions(
    preds_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
    users_df: pd.DataFrame,
) -> pd.DataFrame:
    """Inner-merge predictions with finished matches, score once, derive outcomes."""
    if preds_df.empty or finished_matches_df.empty:
        return pd.DataFrame()

    preds = preds_df.copy()
    finished = finished_matches_df.copy()
    id_col = _match_id_col(finished)

    preds["user_id"] = preds["user_id"].astype(str)
    preds["match_id"] = preds["match_id"].astype(str)
    finished[id_col] = finished[id_col].astype(str)

    merged = pd.merge(preds, finished, left_on="match_id", right_on=id_col, how="inner")
    if merged.empty:
        return merged

    merged["points"] = merged.apply(calculate_points, axis=1)
    merged["points"] = pd.to_numeric(merged["points"], errors="coerce").fillna(0).astype(int)
    merged["actual_outcome"] = derive_actual_outcome(merged)
    merged["pred_outcome"] = merged["pred_outcome"].apply(normalize_pred_outcome)

    sort_cols = [c for c in ("kickoff_vn", "match_number") if c in merged.columns]
    if sort_cols:
        merged = merged.sort_values(sort_cols).reset_index(drop=True)

    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)
    merged = pd.merge(merged, users[["user_id", "name"]], on="user_id", how="left")
    return _filter_merged_by_user_eligibility(merged, users_df)


def get_cumulative_scores(scored_df: pd.DataFrame) -> pd.DataFrame:
    """Per-user cumulative points in global kickoff order."""
    cols = ["user_id", "name", "kickoff_vn", "match_number", "points", "cumulative_points"]
    if scored_df.empty:
        return pd.DataFrame(columns=cols)

    sort_cols = [c for c in ("kickoff_vn", "match_number") if c in scored_df.columns]
    df = scored_df.sort_values(sort_cols or ["user_id"]).copy()
    df["cumulative_points"] = df.groupby("user_id")["points"].cumsum()
    return df[cols]


def get_confusion_matrix(scored_df: pd.DataFrame, user_id: str) -> pd.DataFrame:
    """3×3 crosstab of actual vs predicted outcome for one user."""
    empty = pd.DataFrame(0, index=list(OUTCOME_ORDER), columns=list(OUTCOME_ORDER))
    if scored_df.empty or "user_id" not in scored_df.columns:
        return empty

    user_df = scored_df[scored_df["user_id"] == str(user_id)]
    if user_df.empty:
        return empty

    valid = user_df["actual_outcome"].notna() & user_df["pred_outcome"].notna()
    user_df = user_df.loc[valid]
    if user_df.empty:
        return empty

    matrix = pd.crosstab(user_df["actual_outcome"], user_df["pred_outcome"])
    return matrix.reindex(index=list(OUTCOME_ORDER), columns=list(OUTCOME_ORDER), fill_value=0)


def get_prediction_lead_time(
    preds_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    users_df: pd.DataFrame,
) -> pd.DataFrame:
    """All predictions with hours before kickoff; NaN lead_hours when timestamp/kickoff missing."""
    cols = ["user_id", "name", "match_id", "kickoff_vn", "timestamp", "lead_hours", "is_late"]
    if preds_df.empty or matches_df.empty:
        return pd.DataFrame(columns=cols)

    preds = preds_df.copy()
    matches = matches_df.copy()
    id_col = _match_id_col(matches)

    preds["user_id"] = preds["user_id"].astype(str)
    preds["match_id"] = preds["match_id"].astype(str)
    matches[id_col] = matches[id_col].astype(str)

    kickoff_cols = [id_col]
    if "kickoff_vn" in matches.columns:
        kickoff_cols.append("kickoff_vn")
    if "match_number" in matches.columns:
        kickoff_cols.append("match_number")

    merged = pd.merge(
        preds,
        matches[kickoff_cols],
        left_on="match_id",
        right_on=id_col,
        how="left",
    )

    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)
    merged = pd.merge(merged, users[["user_id", "name"]], on="user_id", how="left")

    ts = _parse_prediction_timestamp(merged["timestamp"]) if "timestamp" in merged.columns else pd.Series(pd.NaT, index=merged.index)
    kickoff = _normalize_kickoff(merged["kickoff_vn"]) if "kickoff_vn" in merged.columns else pd.Series(pd.NaT, index=merged.index)

    delta = kickoff - ts
    merged["lead_hours"] = delta.dt.total_seconds() / 3600
    merged["is_late"] = merged["lead_hours"] < 0

    merged = _filter_merged_by_user_eligibility(merged, users_df)
    return merged[cols]


def lead_time_stats(preds_df: pd.DataFrame, lead_df: pd.DataFrame) -> dict:
    """Coverage summary for prediction timestamps vs total predictions."""
    total = len(preds_df)
    if lead_df.empty or total == 0:
        return {
            "total_predictions": total,
            "with_timestamp": 0,
            "coverage_pct": 0.0,
            "late_count": 0,
        }

    with_timestamp = int(lead_df["lead_hours"].notna().sum())
    late_count = int((lead_df["lead_hours"].notna() & lead_df["is_late"]).sum())
    coverage_pct = round(with_timestamp / total * 100, 1) if total else 0.0

    return {
        "total_predictions": total,
        "with_timestamp": with_timestamp,
        "coverage_pct": coverage_pct,
        "late_count": late_count,
    }


def _latest_per_user(cumulative_df: pd.DataFrame) -> pd.DataFrame:
    sort_cols = [c for c in ("kickoff_vn", "match_number") if c in cumulative_df.columns]
    ordered = cumulative_df.sort_values(sort_cols or ["user_id"])
    return ordered.groupby("user_id", as_index=False).tail(1)


def summarize_momentum(cumulative_df: pd.DataFrame, n_finished_matches: int) -> dict:
    """Plain-language highlights for the cumulative score race."""
    if cumulative_df.empty:
        return {}

    latest = _latest_per_user(cumulative_df)
    leader_row = latest.loc[latest["cumulative_points"].idxmax()]
    leader_points = int(leader_row["cumulative_points"])
    leader_name = str(leader_row["name"])

    sort_cols = [c for c in ("kickoff_vn", "match_number") if c in cumulative_df.columns]
    last_kickoff = cumulative_df.sort_values(sort_cols)["kickoff_vn"].iloc[-1]
    last_match = cumulative_df[cumulative_df["kickoff_vn"] == last_kickoff].copy()
    last_match["prev_cum"] = (
        last_match.groupby("user_id")["cumulative_points"].shift(1).fillna(0).astype(int)
    )
    last_match["match_gain"] = last_match["cumulative_points"] - last_match["prev_cum"]
    top_last = last_match.loc[last_match["match_gain"].idxmax()]

    return {
        "n_finished_matches": n_finished_matches,
        "n_players": int(latest["user_id"].nunique()),
        "leader_name": leader_name,
        "leader_points": leader_points,
        "last_match_winner": str(top_last["name"]),
        "last_match_gain": int(top_last["match_gain"]),
        "last_match_number": int(top_last["match_number"]) if "match_number" in top_last else None,
    }


def top_momentum_players(
    cumulative_df: pd.DataFrame,
    *,
    limit: int = 6,
    highlight_user_id: str | None = None,
) -> list[str]:
    """User IDs to plot: top N by cumulative points + optional highlighted user."""
    if cumulative_df.empty:
        return []

    latest = _latest_per_user(cumulative_df)
    top_ids = (
        latest.sort_values("cumulative_points", ascending=False)
        .head(limit)["user_id"]
        .astype(str)
        .tolist()
    )
    if highlight_user_id and str(highlight_user_id) not in top_ids:
        top_ids.append(str(highlight_user_id))
    return top_ids


def summarize_accuracy(matrix: pd.DataFrame, user_name: str) -> dict:
    """Interpret a 3×3 confusion matrix in everyday language."""
    total = int(matrix.values.sum())
    if total == 0:
        return {"user_name": user_name, "total": 0}

    hits = int(sum(matrix.loc[o, o] for o in OUTCOME_ORDER if o in matrix.index and o in matrix.columns))
    accuracy_pct = round(hits / total * 100, 1)

    pred_totals = matrix.sum(axis=0)
    favorite_code = pred_totals.idxmax() if not pred_totals.empty else OUTCOME_ORDER[0]
    favorite_count = int(pred_totals.max()) if not pred_totals.empty else 0

    off_diag = matrix.copy()
    for o in OUTCOME_ORDER:
        if o in off_diag.index and o in off_diag.columns:
            off_diag.loc[o, o] = 0
    weak_actual = weak_pred = None
    weak_count = 0
    if off_diag.values.sum() > 0:
        flat_idx = off_diag.stack().idxmax()
        weak_actual, weak_pred = flat_idx
        weak_count = int(off_diag.loc[weak_actual, weak_pred])

    return {
        "user_name": user_name,
        "total": total,
        "hits": hits,
        "misses": total - hits,
        "accuracy_pct": accuracy_pct,
        "favorite_code": favorite_code,
        "favorite_label": OUTCOME_LABELS.get(favorite_code, favorite_code),
        "favorite_count": favorite_count,
        "weak_actual": weak_actual,
        "weak_pred": weak_pred,
        "weak_count": weak_count,
        "weak_actual_label": OUTCOME_LABELS.get(weak_actual, "") if weak_actual else "",
        "weak_pred_label": OUTCOME_LABELS.get(weak_pred, "") if weak_pred else "",
    }


def lead_time_medians(lead_df: pd.DataFrame) -> pd.DataFrame:
    """Per-user median lead hours (valid timestamps only)."""
    cols = ["user_id", "name", "median_hours", "n_predictions"]
    if lead_df.empty:
        return pd.DataFrame(columns=cols)

    valid = lead_df[lead_df["lead_hours"].notna()].copy()
    if valid.empty:
        return pd.DataFrame(columns=cols)

    grouped = (
        valid.groupby(["user_id", "name"], as_index=False)
        .agg(median_hours=("lead_hours", "median"), n_predictions=("lead_hours", "count"))
        .sort_values("median_hours", ascending=False)
    )
    grouped["median_hours"] = grouped["median_hours"].round(1)
    return grouped[cols]


def summarize_lead_time(lead_df: pd.DataFrame, lead_stats: dict) -> dict:
    """Plain-language highlights for prediction timing."""
    medians = lead_time_medians(lead_df)
    if medians.empty:
        return {
            "coverage_pct": lead_stats.get("coverage_pct", 0.0),
            "late_count": lead_stats.get("late_count", 0),
            "with_timestamp": lead_stats.get("with_timestamp", 0),
            "total_predictions": lead_stats.get("total_predictions", 0),
        }

    early = medians.iloc[0]
    late = medians.iloc[-1]
    overall_median = round(float(lead_df["lead_hours"].dropna().median()), 1)

    return {
        "coverage_pct": lead_stats.get("coverage_pct", 0.0),
        "late_count": lead_stats.get("late_count", 0),
        "with_timestamp": lead_stats.get("with_timestamp", 0),
        "total_predictions": lead_stats.get("total_predictions", 0),
        "overall_median_hours": overall_median,
        "early_bird_name": str(early["name"]),
        "early_bird_hours": float(early["median_hours"]),
        "last_minute_name": str(late["name"]),
        "last_minute_hours": float(late["median_hours"]),
        "n_players": int(medians["user_id"].nunique()),
    }


def format_momentum_takeaway(summary: dict) -> str:
    if not summary:
        return ""
    leader = summary["leader_name"]
    pts = summary["leader_points"]
    last_w = summary["last_match_winner"]
    gain = summary["last_match_gain"]
    if gain > 0:
        return (
            f"{leader} đang dẫn đầu cuộc đua với {pts} điểm. "
            f"Trận gần nhất, {last_w} ghi thêm {gain} điểm — nhiều nhất trong trận đó."
        )
    return f"{leader} đang dẫn đầu cuộc đua với {pts} điểm."


def format_accuracy_takeaway(summary: dict) -> str:
    if not summary or summary.get("total", 0) == 0:
        return ""
    name = summary["user_name"]
    hits = summary["hits"]
    total = summary["total"]
    acc = summary["accuracy_pct"]
    fav = summary["favorite_label"]
    fav_n = summary["favorite_count"]
    parts = [f"{name}: {hits}/{total} đúng ({acc}%). Thường chọn {fav} ({fav_n} lần)."]
    if summary.get("weak_count", 0) > 0:
        parts.append(
            f"Lỗi hay gặp: dự {summary['weak_pred_label']} nhưng thực tế {summary['weak_actual_label']} "
            f"({summary['weak_count']} lần)."
        )
    return " ".join(parts)


def format_lead_time_takeaway(summary: dict) -> str:
    if not summary.get("overall_median_hours"):
        return ""
    early = summary["early_bird_name"]
    early_h = summary["early_bird_hours"]
    late = summary["last_minute_name"]
    late_h = summary["last_minute_hours"]
    med = summary["overall_median_hours"]
    text = (
        f"Cả nhóm dự đoán trung bình {med} giờ trước giờ đá. "
        f"Sớm nhất: {early} (~{early_h}h). Gần giờ đá nhất: {late} (~{late_h}h)."
    )
    if summary.get("late_count", 0) > 0:
        text += f" Có {summary['late_count']} lần dự đoán sau giờ đá."
    return text


def calculate_crowd_consensus(preds_df: pd.DataFrame) -> pd.DataFrame:
    """
    Per-match majority pick (Wisdom of the Crowd).
    Tie-break when vote counts equal: OUTCOME_ORDER (A, D, B).
    """
    cols = ["match_id", "favorite_pick", "consensus_votes", "total_votes"]
    if preds_df.empty or "match_id" not in preds_df.columns or "pred_outcome" not in preds_df.columns:
        return pd.DataFrame(columns=cols)

    preds = preds_df.copy()
    preds["match_id"] = preds["match_id"].astype(str)
    preds["pred_outcome"] = preds["pred_outcome"].apply(normalize_pred_outcome)
    valid = preds["pred_outcome"].notna()
    preds = preds.loc[valid, ["match_id", "pred_outcome"]]
    if preds.empty:
        return pd.DataFrame(columns=cols)

    counts = (
        preds.groupby(["match_id", "pred_outcome"], as_index=False)
        .size()
        .rename(columns={"size": "consensus_votes"})
    )
    totals = counts.groupby("match_id")["consensus_votes"].transform("sum")
    counts["total_votes"] = totals.astype(int)
    counts["_rank"] = counts["pred_outcome"].map(_OUTCOME_RANK).fillna(99).astype(int)
    counts = counts.sort_values(
        ["match_id", "consensus_votes", "_rank"],
        ascending=[True, False, True],
    )
    consensus = (
        counts.groupby("match_id", as_index=False)
        .first()
        .rename(columns={"pred_outcome": "favorite_pick"})
    )
    return consensus[cols]


def get_user_risk_profile(
    preds_df: pd.DataFrame,
    consensus_df: pd.DataFrame,
    users_df: pd.DataFrame,
) -> pd.DataFrame:
    """Safe vs Risky pick proportions per user (aligned with crowd favorite)."""
    cols = ["user_id", "name", "pick_type", "n_picks", "pct"]
    if preds_df.empty or consensus_df.empty:
        return pd.DataFrame(columns=cols)

    preds = preds_df.copy()
    preds["user_id"] = preds["user_id"].astype(str)
    preds["match_id"] = preds["match_id"].astype(str)
    preds["pred_outcome"] = preds["pred_outcome"].apply(normalize_pred_outcome)
    preds = preds[preds["pred_outcome"].notna()]

    merged = pd.merge(
        preds,
        consensus_df[["match_id", "favorite_pick"]],
        on="match_id",
        how="inner",
    )
    if merged.empty:
        return pd.DataFrame(columns=cols)

    merged["pick_type"] = merged["pred_outcome"].eq(merged["favorite_pick"]).map(
        {True: "Safe", False: "Risky"}
    )

    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)
    merged = pd.merge(merged, users[["user_id", "name"]], on="user_id", how="left")

    grouped = (
        merged.groupby(["user_id", "name", "pick_type"], as_index=False)
        .size()
        .rename(columns={"size": "n_picks"})
    )
    grouped["pct"] = (
        grouped["n_picks"] / grouped.groupby("user_id")["n_picks"].transform("sum") * 100
    ).round(1)
    return grouped.sort_values(["name", "pick_type"])[cols]


def summarize_risk_bias(profile_df: pd.DataFrame, consensus_df: pd.DataFrame) -> dict:
    """Highlights for Risk Bias tab."""
    if profile_df.empty:
        return {"n_matches_with_consensus": int(len(consensus_df))}

    safe = profile_df[profile_df["pick_type"] == "Safe"].copy()
    risky = profile_df[profile_df["pick_type"] == "Risky"].copy()

    safe_top = safe.loc[safe["pct"].idxmax()] if not safe.empty else None
    risky_top = risky.loc[risky["pct"].idxmax()] if not risky.empty else None

    return {
        "n_matches_with_consensus": int(len(consensus_df)),
        "n_players": int(profile_df["user_id"].nunique()),
        "safest_name": str(safe_top["name"]) if safe_top is not None else "",
        "safest_pct": float(safe_top["pct"]) if safe_top is not None else 0.0,
        "riskiest_name": str(risky_top["name"]) if risky_top is not None else "",
        "riskiest_pct": float(risky_top["pct"]) if risky_top is not None else 0.0,
    }


def format_risk_bias_takeaway(summary: dict) -> str:
    if not summary.get("n_matches_with_consensus"):
        return ""
    n = summary["n_matches_with_consensus"]
    parts = [f"Phân tích {n} trận có dự đoán — Cửa trên = pick đa số nhóm (Wisdom of the Crowd)."]
    if summary.get("safest_name"):
        parts.append(
            f"{summary['safest_name']} hay đi theo đám đông nhất ({summary['safest_pct']:.0f}% Safe)."
        )
    if summary.get("riskiest_name") and summary.get("riskiest_pct", 0) > 0:
        parts.append(
            f"{summary['riskiest_name']} hay chọn ngược số đông nhất ({summary['riskiest_pct']:.0f}% Risky)."
        )
    return " ".join(parts)
