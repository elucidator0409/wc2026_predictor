"""Analytics aggregations for prediction-style dashboard (pure pandas)."""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np



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


def calculate_fund_forecast(leaderboard_df: pd.DataFrame, finished_matches_count: int) -> dict:
    """
    Tính dự phóng quỹ phạt (Expected Value) dựa trên Hit Rate cá nhân của từng user.
    """
    TOTAL_MATCHES = 104
    PENALTY_FEE = 10000  # 10k VNĐ mỗi trận sai/miss
    
    if leaderboard_df.empty:
        return {"current_fund": 0, "projected_fund": 0, "finished_matches": 0, "total_matches": TOTAL_MATCHES}

    current_total_fund = 0
    projected_total_fund = 0
    remaining_matches = max(0, TOTAL_MATCHES - finished_matches_count)

    # Tính dự phóng cho TỪNG USER
    for _, row in leaderboard_df.iterrows():
        # 1. Quỹ hiện tại của user này (1 đơn vị fines = 1000 VNĐ)
        user_current_fine = int(row.get("fines", 0)) * 1000
        current_total_fund += user_current_fine

        # 2. Lấy tỉ lệ trúng (Hit Rate) hiện tại
        # Ví dụ hit_rate = 40.5 (%) -> Xác suất đoán đúng là 0.405
        hit_rate_pct = float(row.get("hit_rate", 0.0))
        prob_correct = hit_rate_pct / 100.0

        # Nếu user chưa chơi trận nào (hoặc data lỗi), để mặc định xác suất sai là 50%
        if float(row.get("played", 0)) == 0:
            prob_correct = 0.5

        # 3. Xác suất bị phạt (Đoán sai hoặc Bỏ lỡ)
        prob_penalty = 1.0 - prob_correct

        # 4. Kỳ vọng tiền phạt trong các trận còn lại
        expected_future_fines = prob_penalty * remaining_matches * PENALTY_FEE

        # 5. Cộng dồn vào quỹ dự phóng tổng
        projected_total_fund += (user_current_fine + expected_future_fines)

    # Tính thêm một baseline ngây thơ (Naive) để so sánh vui
    naive_projected = 0
    if finished_matches_count > 0:
        naive_projected = int((current_total_fund / finished_matches_count) * TOTAL_MATCHES)

    return {
        "current_fund": int(current_total_fund),
        "projected_fund": int(projected_total_fund),
        "naive_fund": int(naive_projected), # Dùng để soi xem model AI tính lệch model cơ bản bao nhiêu
        "finished_matches": finished_matches_count,
        "total_matches": TOTAL_MATCHES
    }


def calculate_advanced_forecast(leaderboard_df, finished_matches_count, target=11000000):
    """
    Tính dự phóng quỹ với biên độ an toàn (Confidence Interval).
    """
    TOTAL_MATCHES = 104
    PENALTY_FEE = 10000
    remaining_matches = max(0, TOTAL_MATCHES - finished_matches_count)
    
    # --- 1. TÍNH BASE_PROJ (Dựa trên logic EV chúng ta đã chốt) ---
    current_total = 0
    projected_total = 0
    
    for _, row in leaderboard_df.iterrows():
        user_current = int(row.get("fines", 0)) * 1000
        current_total += user_current
        
        # Lấy hit_rate an toàn
        hit_rate = float(row.get("hit_rate", 50.0))
        prob_penalty = 1.0 - (max(0, min(100, hit_rate)) / 100.0)
        
        # Dự phóng phần còn lại
        expected_future = prob_penalty * remaining_matches * PENALTY_FEE
        projected_total += (user_current + expected_future)
    
    base_proj = projected_total
    
    # --- 2. TÍNH MARGIN (Biên độ dao động) ---
    # Tính độ lệch chuẩn của số tiền phạt mỗi user để làm margin
    # Nếu nhóm dự đoán bất ổn (std cao), margin sẽ rộng ra
    std_dev = leaderboard_df["fines"].std() * 1000 if "fines" in leaderboard_df.columns else 0
    # Giả định margin là 15% hoặc 1.5 lần độ lệch chuẩn, lấy cái nào lớn hơn
    margin = max(base_proj * 0.15, std_dev * 1.5)
    
    return {
        "lower": max(0, base_proj - margin),
        "mid": base_proj,
        "upper": base_proj + margin,
        "target": target,
        'current_fund': current_total,
    }





def generate_financial_insights(leaderboard_df: pd.DataFrame, merged_df: pd.DataFrame, projected_fund: int, target_fund: int = 11000000) -> list[dict]:
    insights = []
    if leaderboard_df.empty:
        return insights
        
    TOTAL_MATCHES = 104
    PENALTY_FEE = 10000
    
    # 1. Tự động dò tìm tên cột
    col_map = {str(c).lower(): c for c in leaderboard_df.columns}
    fines_col = col_map.get("fines") or col_map.get("tiền phạt") or col_map.get("phạt") or col_map.get("fines_k")
    name_col = col_map.get("name") or col_map.get("tên") or col_map.get("người chơi") or col_map.get("user") or col_map.get("user_id")
    hr_col = col_map.get("hit_rate") or col_map.get("accuracy") or col_map.get("tỉ lệ") or col_map.get("tỉ lệ đúng")
    played_col = col_map.get("played") or col_map.get("số trận") or col_map.get("đã chơi")

    if not name_col and len(leaderboard_df.columns) > 0:
        name_col = leaderboard_df.columns[0]
        
    df_safe = leaderboard_df.copy()
    num_players = len(df_safe)
    if num_players == 0:
        return insights
    
    # 2. Xác định số trận đã đá và còn lại
    if played_col and not df_safe.empty:
        finished_matches = int(pd.to_numeric(df_safe[played_col], errors='coerce').max())
    else:
        match_col = "match_number" if "match_number" in merged_df.columns else ("match_id" if "match_id" in merged_df.columns else None)
        finished_matches = merged_df[match_col].nunique() if match_col and match_col in merged_df.columns else 0
        
    remaining_matches = max(0, TOTAL_MATCHES - finished_matches)

    # 3. Tính Quỹ hiện tại và Khoảng cách thực tế
    current_fund = 0
    if fines_col:
        df_safe[fines_col] = pd.to_numeric(df_safe[fines_col], errors='coerce').fillna(0)
        current_fund = df_safe[fines_col].sum()
        if df_safe[fines_col].max() < 10000 and current_fund > 0:
            current_fund *= 1000
    current_fund = int(current_fund)
    real_gap = target_fund - current_fund

    # =========================================================================
    # BỘ 3 INSIGHT CŨ (ĐÃ CHỐT)
    # =========================================================================

    # --- INSIGHT 1: ĐỘI HÌNH "GÁNH QUỸ" ---
    top_drivers = pd.DataFrame()
    if hr_col and name_col and remaining_matches > 0:
        df_safe[hr_col] = pd.to_numeric(df_safe[hr_col], errors='coerce').fillna(50.0)
        df_safe['expected_contribution'] = (1 - df_safe[hr_col] / 100.0) * remaining_matches * PENALTY_FEE
        top_drivers = df_safe.sort_values(by='expected_contribution', ascending=False).head(2)
        
        if len(top_drivers) >= 2:
            name_1, expected_1 = str(top_drivers.iloc[0][name_col]), float(top_drivers.iloc[0]['expected_contribution'])
            name_2, expected_2 = str(top_drivers.iloc[1][name_col]), float(top_drivers.iloc[1]['expected_contribution'])
            content_1 = f"Dựa trên phong độ, **{name_1}** (dự kiến cúng thêm {expected_1:,.0f} đ) và **{name_2}** (dự kiến {expected_2:,.0f} đ) sẽ là 2 'đầu kéo' chính đưa quỹ về đích. Hãy chăm sóc kỹ 2 nguồn thu này!"
        else:
            name_1, expected_1 = str(top_drivers.iloc[0][name_col]), float(top_drivers.iloc[0]['expected_contribution'])
            content_1 = f"Dựa trên phong độ, **{name_1}** dự kiến sẽ là 'đầu kéo' chính với mức cúng thêm {expected_1:,.0f} đ."
            
        insights.append({"type": "profiling", "title": "🚜 Đội hình 'Gánh Quỹ'", "content": content_1})

    # --- INSIGHT 2: KỊCH BẢN "GIẢI CỨU QUỸ" ---
    if real_gap > 0:
        misses_per_person = (real_gap / PENALTY_FEE) / num_players
        content_2 = f"Quỹ thực tế mới đang có **{current_fund:,.0f} đ**. Để cán đích 11M, mỗi anh em cần 'tự nguyện' đoán sai trung bình **{misses_per_person:.1f} trận** nữa. Áp lực đang rất lớn!"
        insights.append({"type": "what_if", "title": "🚑 Kịch Bản 'Giải Cứu Quỹ'", "content": content_2})
    else:
        surplus = current_fund - target_fund
        insights.append({"type": "profiling", "title": "🎉 Mục Tiêu Hoàn Thành", "content": f"Quỹ đã vượt mục tiêu **{surplus:,.0f} đ**. Anh em chuẩn bị liên hoan thôi!"})

    # --- INSIGHT 3: CHỈ SỐ TIẾN ĐỘ ---
    match_completion_pct = (finished_matches / TOTAL_MATCHES) * 100 if TOTAL_MATCHES > 0 else 0
    fund_completion_pct = (current_fund / target_fund) * 100 if target_fund > 0 else 0

    if fund_completion_pct < match_completion_pct:
        diff = match_completion_pct - fund_completion_pct
        content_3 = f"Giải đấu đã trôi qua **{match_completion_pct:.1f}%**, nhưng quỹ mới gom được **{fund_completion_pct:.1f}%**. Tốc độ nộp phạt đang chậm hơn tiến độ giải ({diff:.1f}%)."
        insights.append({"type": "burn_rate", "title": "⏱️ Chỉ số Tiến Độ (Pacing)", "content": content_3})
    else:
        diff = fund_completion_pct - match_completion_pct
        content_3 = f"Mới trôi qua **{match_completion_pct:.1f}%** chặng đường mà quỹ đã hoàn thành **{fund_completion_pct:.1f}%** (Vượt tiến độ {diff:.1f}%). Tốc độ 'báo' đang cực kỳ xuất sắc!"
        insights.append({"type": "profiling", "title": "⏱️ Chỉ số Tiến Độ (Pacing)", "content": content_3})


    # =========================================================================
    # BỘ 3 INSIGHT MỚI (SENIOR FORECASTING)
    # =========================================================================

    # --- INSIGHT 4: RỦI RO "CÁ MẬP" (Whale Dependency) ---
    if not top_drivers.empty and remaining_matches > 0:
        total_expected = df_safe['expected_contribution'].sum()
        top_2_expected = top_drivers['expected_contribution'].sum()
        
        if total_expected > 0:
            dependency_pct = (top_2_expected / total_expected) * 100
            content_4 = f"Top 2 'Báo thủ' đang nắm giữ tới **{dependency_pct:.1f}%** dòng tiền dự phóng tương lai của quỹ. \n\n⚠️ **Cảnh báo:** Nếu 2 anh này đột nhiên 'vào form' và đoán trúng liên tục, quỹ dự phóng sẽ sụp đổ. Các anh em khác cần chia lửa gấp, không thể ỷ lại!"
            
            insights.append({
                "type": "what_if",  # Render màu Đỏ
                "title": "🐳 Rủi ro 'Cá Mập' (Whale Dependency)",
                "content": content_4
            })

    # --- INSIGHT 5: NGƯỠNG SINH TỬ (Goal-Seek Hit Rate) ---
    if real_gap > 0 and remaining_matches > 0:
        total_remaining_picks = remaining_matches * num_players
        misses_needed = real_gap / PENALTY_FEE
        
        if misses_needed > total_remaining_picks:
            content_5 = f"Dù TẤT CẢ {num_players} anh em đều đoán sai {remaining_matches} trận còn lại, quỹ vẫn KHÔNG THỂ chạm mốc 11 Triệu. Target đã vỡ!"
            i5_type = "what_if"
        else:
            required_miss_rate = misses_needed / total_remaining_picks
            required_hit_rate = (1 - required_miss_rate) * 100
            current_group_hr = df_safe[hr_col].mean() if hr_col else 50.0
            
            if current_group_hr > required_hit_rate:
                status = f"Hiện tại nhóm đang đoán quá mượt ({current_group_hr:.1f}%). Cần 'tâm linh' hơn nữa!"
                i5_type = "what_if"
            else:
                status = f"Phong độ hiện tại ({current_group_hr:.1f}%) đang rất lý tưởng để bào tiền. Cứ thế phát huy!"
                i5_type = "profiling"
                
            content_5 = f"Để cán đích 11M, Hit Rate trung bình của cả nhóm trong các trận còn lại **PHẢI THẤP HƠN {required_hit_rate:.1f}%**. \n\n{status}"
            
        insights.append({
            "type": i5_type, # Tự đổi màu dựa theo việc có vượt ngưỡng hay không
            "title": "🎯 Ngưỡng Sinh Tử (Survival Hit Rate)",
            "content": content_5
        })

    # --- INSIGHT 6: THỜI ĐIỂM ĐẠT TARGET (The ETA Deadline) ---
    if finished_matches > 0 and real_gap > 0:
        avg_fine_per_match = current_fund / finished_matches
        
        if avg_fine_per_match > 0:
            matches_needed = real_gap / avg_fine_per_match
            projected_match_to_hit = finished_matches + matches_needed
            
            if projected_match_to_hit <= TOTAL_MATCHES:
                content_6 = f"Với tốc độ 'đóng họ' hiện tại ({avg_fine_per_match:,.0f} đ/trận), quỹ dự kiến sẽ cán mốc 11 Triệu vào khoảng **trận đấu thứ {projected_match_to_hit:.0f}**. Có thể bắt đầu booking nhà hàng trước thềm chung kết!"
                i6_type = "profiling" # Render Xanh
            else:
                content_6 = f"Với tốc độ nộp phạt hẻo lánh hiện tại ({avg_fine_per_match:,.0f} đ/trận), phải đến... **trận thứ {projected_match_to_hit:.0f}** chúng ta mới đủ 11 Triệu (mà giải chỉ có {TOTAL_MATCHES} trận). Mission Impossible nếu không lật kèo!"
                i6_type = "burn_rate" # Render Vàng cảnh báo
        else:
             content_6 = "Chưa có ai nộp phạt, không thể tính toán ETA."
             i6_type = "burn_rate"
             
        insights.append({
            "type": i6_type,
            "title": "🗓️ Dự Báo Deadline (ETA)",
            "content": content_6
        })

    return insights

def generate_weekly_trend_data(merged_df: pd.DataFrame, penalty_fee: int = 10000) -> dict:
    if merged_df.empty:
        return {"df": pd.DataFrame(), "insight": ""}
        
    df = merged_df.copy()
    df["points"] = pd.to_numeric(df.get("points", 0), errors="coerce").fillna(0)
    
    group_col = "period"
    df[group_col] = "N/A"
    
    time_col = None
    if "date_time" in df.columns:
        time_col = "date_time"
    elif "timestamp" in df.columns:
        time_col = "timestamp"
    else:
        for c in df.columns:
            if "date" in str(c).lower() or "time" in str(c).lower():
                time_col = c
                break

    has_time = False
    if time_col:
        df["datetime"] = pd.to_datetime(df[time_col], format="mixed", errors="coerce")
        df_valid_time = df.dropna(subset=["datetime"]).copy()
        
        if not df_valid_time.empty:
            df = df_valid_time.sort_values("datetime")
            
            # --- FIX CHUẨN LỊCH THỰC TẾ (Thứ 2 đến Chủ Nhật) ---
            # Lấy số thứ tự tuần chuẩn theo Lịch quốc tế ISO (Bắt đầu T2, Kết thúc CN)
            df["iso_week"] = df["datetime"].dt.isocalendar().week
            
            # Đánh số Tuần 1, Tuần 2... dựa trên tuần bắt đầu của giải đấu
            min_iso_week = df["iso_week"].min()
            df["week_num"] = df["iso_week"] - min_iso_week + 1
            
            # Tạo nhãn hiển thị: lấy ngày đá sớm nhất và trễ nhất TRONG TUẦN ĐÓ
            week_groups = df.groupby("week_num")["datetime"]
            week_labels = {}
            for w, dates in week_groups:
                start_str = dates.min().strftime("%d/%m")
                end_str = dates.max().strftime("%d/%m")
                if start_str == end_str:
                    week_labels[w] = f"Tuần {w} ({start_str})"
                else:
                    week_labels[w] = f"Tuần {w} ({start_str}-{end_str})"
            
            df[group_col] = df["week_num"].map(week_labels)
            has_time = True
            df["sort_order"] = df["week_num"]
            
    if not has_time:
        match_col = "match_number" if "match_number" in df.columns else ("match_id" if "match_id" in df.columns else None)
        if match_col:
            df[match_col] = pd.to_numeric(df[match_col], errors="coerce").fillna(0)
            start_match = ((df[match_col] - 1) // 10 * 10 + 1).astype(int)
            end_match = start_match + 9
            df[group_col] = "Trận " + start_match.astype(str) + "-" + end_match.astype(str)
            df["sort_order"] = start_match
        else:
            return {"df": pd.DataFrame(), "insight": ""}

    df = df[df[group_col] != "N/A"]
    if df.empty:
        return {"df": pd.DataFrame(), "insight": ""}

    trend_df = df.groupby([group_col, "sort_order"]).agg(
        total_predictions=("points", "count"),
        correct_predictions=("points", lambda x: (x > 0).sum())
    ).reset_index()
    
    trend_df = trend_df[trend_df["total_predictions"] > 0]
    trend_df["missed_predictions"] = trend_df["total_predictions"] - trend_df["correct_predictions"]
    trend_df["fines"] = trend_df["missed_predictions"] * penalty_fee
    trend_df["hit_rate"] = (trend_df["correct_predictions"] / trend_df["total_predictions"]) * 100
    
    trend_df = trend_df.sort_values("sort_order")
    
    insight_text = ""
    if len(trend_df) >= 2:
        last_week = trend_df.iloc[-1]
        prev_week = trend_df.iloc[-2]
        
        hr_diff = last_week["hit_rate"] - prev_week["hit_rate"]
        fines_diff = last_week["fines"] - prev_week["fines"]
        last_week_name = str(last_week[group_col]).split('(')[0].strip().lower()
        
        if hr_diff < -3:
            insight_text = f"📉 **Khủng hoảng tâm lý:** Ở {last_week_name}, Hit Rate giảm mạnh ({hr_diff:.1f}%), anh em bắt đầu rơi vào chuỗi hoảng loạn. Dòng tiền đổ về quỹ tăng thêm **{fines_diff:,.0f} đ** so với kỳ trước!"
        elif hr_diff > 3:
            insight_text = f"⚠️ **Cảnh báo học hỏi:** Anh em đã 'bắt bài' được nhà cái! Tỉ lệ đoán trúng {last_week_name} tăng vọt ({hr_diff:+.1f}%), quỹ bị hụt đi **{abs(fines_diff):,.0f} đ**. Tốc độ gom tiền đang chững lại!"
        else:
            insight_text = f"⚖️ **Giữ vững phong độ:** Hit Rate {last_week_name} dao động nhẹ ({hr_diff:+.1f}%), anh em duy trì mức cống hiến ổn định. Quỹ thu về **{last_week['fines']:,.0f} đ** trong đợt này."
    else:
        insight_text = "⏳ Giai đoạn đầu giải, hệ thống đang thu thập thêm dữ liệu để đánh giá xem phong độ anh em đang đi lên hay cắm đầu."
        
    return {"df": trend_df, "insight": insight_text}


