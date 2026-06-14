"""HP bar math and Google Sheets achievement rule evaluation."""

from __future__ import annotations

import hashlib
import operator as op
from typing import Callable

import pandas as pd

MAX_HP = 104  # 1.040.000 VNĐ budget — 1 HP = 10.000 VNĐ
FINE_UNIT_HP = 10  # fines column stores 10 per 10k VNĐ penalty (10 → 1 HP)

OPERATORS: dict[str, Callable[[float, float], bool]] = {
    ">": op.gt,
    ">=": op.ge,
    "==": op.eq,
    "<": op.lt,
    "<=": op.le,
}

ALLOWED_METRICS = frozenset(
    {
        "total_penalties",
        "points",
        "hit_rate",
        "correct",
        "missed",
        "played",
        "remaining_hp",
        "win_streak",
        "lose_streak",
    }
)

METRIC_LABELS_VN: dict[str, str] = {
    "total_penalties": "Tổng phạt (đơn vị 10k)",
    "points": "Điểm",
    "hit_rate": "Tỉ lệ trúng (%)",
    "correct": "Số trận đúng",
    "missed": "Số trận bỏ lỡ",
    "played": "Số trận đã dự đoán",
    "remaining_hp": "Sinh lực còn lại",
    "win_streak": "Chuỗi thắng gần nhất",
    "lose_streak": "Chuỗi thua/hòa gần nhất",
}

THRESHOLD_HINTS_VN: dict[str, str] = {
    "total_penalties": (
        "Ngưỡng theo cột fines (không phải VNĐ): mỗi 10 = 10.000 VNĐ. "
        "Ví dụ phạt 50k → nhập 50; phạt 125k → nhập 125. "
        "Các rule total_penalties chỉ trao **một** badge tier cao nhất (>=) hoặc thấp nhất (<=)."
    ),
    "remaining_hp": "Ngưỡng theo HP còn lại (0–140), không phải tiền VNĐ.",
    "win_streak": "Số trận thắng liên tiếp tính từ trận mới nhất ngược lại (chuỗi 2 = 2 trận gần nhất đều thắng).",
    "lose_streak": "Số trận thua/hòa/bỏ lỡ liên tiếp từ trận mới nhất ngược lại.",
}


# Penalty tiers: at most one >= rule and one <= rule per user (highest / lowest matching band).
TIER_EXCLUSIVE_METRICS = frozenset({"total_penalties"})
TIER_HIGH_OPERATORS = frozenset({">", ">="})
TIER_LOW_OPERATORS = frozenset({"<", "<="})

BADGE_RARITIES = ("Common", "Rare", "Legend")
DEFAULT_BADGE_RARITY = "Common"

RARITY_LABELS_VN: dict[str, str] = {
    "Common": "Thường",
    "Rare": "Hiếm",
    "Legend": "Huyền thoại",
}


def normalize_badge_rarity(raw) -> str:
    """Normalize rarity to Common / Rare / Legend."""
    text = str(raw or "").strip().lower()
    if text in ("rare", "hiếm", "hiem"):
        return "Rare"
    if text in ("legend", "legendary", "huyền thoại", "huyen thoai", "huyenthoai"):
        return "Legend"
    return DEFAULT_BADGE_RARITY


def badge_rarity_slug(rarity: str) -> str:
    return normalize_badge_rarity(rarity).lower()


def build_badge_rarity_map(rules_df: pd.DataFrame) -> dict[str, str]:
    """Map badge_name → rarity (first occurrence in sheet order wins)."""
    out: dict[str, str] = {}
    if rules_df.empty:
        return out
    for _, rule in rules_df.iterrows():
        badge = str(rule.get("badge_name", "")).strip()
        if not badge or badge in out:
            continue
        out[badge] = normalize_badge_rarity(rule.get("rarity", DEFAULT_BADGE_RARITY))
    return out


def badge_catalog_meta_from_rules(rules_df: pd.DataFrame) -> list[dict[str, str]]:
    """Unique badges with rarity metadata in sheet order."""
    catalog: list[dict[str, str]] = []
    seen: set[str] = set()
    if rules_df.empty:
        return catalog
    for _, rule in rules_df.iterrows():
        badge = str(rule.get("badge_name", "")).strip()
        if not badge or badge in seen:
            continue
        seen.add(badge)
        catalog.append(
            {
                "name": badge,
                "metric": str(rule.get("metric", "")).strip(),
                "rarity": normalize_badge_rarity(rule.get("rarity", DEFAULT_BADGE_RARITY)),
                "description": str(rule.get("description", "")).strip(),
            }
        )
    return catalog


def count_badges_by_rarity(catalog_meta: list[dict[str, str]]) -> dict[str, int]:
    counts = {r: 0 for r in BADGE_RARITIES}
    for item in catalog_meta:
        rarity = normalize_badge_rarity(item.get("rarity"))
        counts[rarity] = counts.get(rarity, 0) + 1
    return counts


def compute_hp_fields(fines_k: int) -> dict[str, int | float]:
    """Convert fines (10 = 10k VNĐ) into remaining HP — each 10k costs 1 HP."""
    hp_lost = int(fines_k) // FINE_UNIT_HP
    remaining = max(0, MAX_HP - hp_lost)
    return {
        "remaining_hp": remaining,
        "remaining_hp_pct": round(remaining / MAX_HP * 100, 1),
    }


def _streak_for_user(streaks: dict | None, key: str, user_id: str) -> int:
    if not streaks:
        return 0
    record = streaks.get(key)
    if not record or str(record.get("user_id")) != str(user_id):
        return 0
    return int(record.get("streak", 0))


def _trailing_streak_count(codes: list[str], target: set[str]) -> int:
    """Count consecutive matches at the end of timeline matching target codes."""
    count = 0
    for code in reversed(codes):
        if code in target:
            count += 1
        else:
            break
    return count


def build_per_user_streak_recent(timeline_df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Trailing win/lose streak per user from most recent finished matches."""
    if timeline_df.empty:
        return {}
    out: dict[str, dict[str, int]] = {}
    for uid, group in timeline_df.groupby("user_id"):
        codes = group.sort_values("global_order")["form_code"].tolist()
        out[str(uid)] = {
            "win_streak": _trailing_streak_count(codes, {"W"}),
            "lose_streak": _trailing_streak_count(codes, {"L", "D"}),
        }
    return out


def build_per_user_streak_max(timeline_df: pd.DataFrame) -> dict[str, dict[str, int]]:
    """Deprecated alias — achievements use trailing streak only."""
    return build_per_user_streak_recent(timeline_df)


def build_user_stats_dict(
    lb_row: dict,
    streaks: dict | None = None,
    per_user_streaks: dict[str, dict[str, int]] | None = None,
) -> dict[str, float]:
    """Flatten leaderboard row + streak stats into evaluable metrics."""
    fines = int(lb_row.get("fines", 0) or 0)
    hp = compute_hp_fields(fines)
    uid = str(lb_row.get("user_id", ""))
    played = int(lb_row.get("played", 0) or 0)
    correct = int(lb_row.get("correct", 0) or 0)
    hit_rate = float(lb_row.get("hit_rate", 0) or 0)
    if played > 0 and hit_rate == 0 and correct > 0:
        hit_rate = round(correct / played * 100, 1)

    user_streaks = (per_user_streaks or {}).get(uid, {})
    win_streak = int(user_streaks.get("win_streak", 0))
    lose_streak = int(user_streaks.get("lose_streak", 0))
    if not per_user_streaks and streaks:
        win_streak = _streak_for_user(streaks, "win_streak", uid)
        lose_streak = _streak_for_user(streaks, "lose_streak", uid)

    return {
        "total_penalties": float(fines),
        "points": float(lb_row.get("points", 0) or 0),
        "hit_rate": hit_rate,
        "correct": float(correct),
        "missed": float(lb_row.get("missed", 0) or 0),
        "played": float(played),
        "remaining_hp": float(hp["remaining_hp"]),
        "win_streak": float(win_streak),
        "lose_streak": float(lose_streak),
    }


def _coerce_threshold(value) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def badge_chip_style(badge_name: str) -> str:
    """Deterministic per-badge HSL theme (same name → same colors)."""
    key = str(badge_name).strip()
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    hue = int(digest[0:8], 16) % 360
    sat = 52 + (int(digest[8:12], 16) % 28)
    border_l = 46 + (int(digest[12:16], 16) % 14)
    bg_l = 14 + (int(digest[16:20], 16) % 10)
    text_l = 72 + (int(digest[20:24], 16) % 16)
    return (
        f"border-color:hsl({hue},{sat}%,{border_l}%);"
        f"background:hsl({hue},{sat}%,{bg_l}%);"
        f"color:hsl({hue},{sat}%,{text_l}%);"
        f"box-shadow:0 0 0 1px hsl({hue},{sat}%,{border_l}%);"
    )


def parse_badge_list(badges) -> list[str]:
    """Normalize badges column value to a list of badge names."""
    if badges is None or (isinstance(badges, float) and pd.isna(badges)):
        return []
    if isinstance(badges, list):
        return [str(b).strip() for b in badges if str(b).strip()]
    text = str(badges).strip()
    if not text:
        return []
    if "\x1f" in text:
        return [part.strip() for part in text.split("\x1f") if part.strip()]
    return [text]


def evaluate_user_achievements(user_stats: dict, rules_df: pd.DataFrame) -> list[str]:
    """Return badge names earned by a user (preserves sheet order).

    For ``total_penalties``, only the highest ``>=`` tier and lowest ``<=`` tier
    are kept so users do not stack every penalty badge at once.
    """
    if rules_df.empty:
        return []

    matches: list[tuple[int, str, str, str, float]] = []
    for pos, (_, rule) in enumerate(rules_df.iterrows()):
        metric = str(rule.get("metric", "")).strip()
        operator_key = str(rule.get("operator", "")).strip()
        badge = str(rule.get("badge_name", "")).strip()
        threshold = _coerce_threshold(rule.get("threshold_value"))

        if not badge or metric not in ALLOWED_METRICS:
            continue
        if operator_key not in OPERATORS or threshold is None:
            continue
        if metric not in user_stats:
            continue

        try:
            actual = float(user_stats[metric])
        except (TypeError, ValueError):
            continue

        if OPERATORS[operator_key](actual, threshold):
            matches.append((pos, badge, metric, operator_key, threshold))

    tier_high_best: dict[str, tuple[int, str, float]] = {}
    tier_low_best: dict[str, tuple[int, str, float]] = {}
    for pos, badge, metric, operator_key, threshold in matches:
        if metric not in TIER_EXCLUSIVE_METRICS:
            continue
        if operator_key in TIER_HIGH_OPERATORS:
            cur = tier_high_best.get(metric)
            if cur is None or threshold > cur[2]:
                tier_high_best[metric] = (pos, badge, threshold)
        elif operator_key in TIER_LOW_OPERATORS:
            cur = tier_low_best.get(metric)
            if cur is None or threshold < cur[2]:
                tier_low_best[metric] = (pos, badge, threshold)

    earned: list[str] = []
    for pos, badge, metric, operator_key, _threshold in matches:
        if metric in TIER_EXCLUSIVE_METRICS:
            if operator_key in TIER_HIGH_OPERATORS:
                winner = tier_high_best.get(metric)
                if winner is None or (pos, badge) != (winner[0], winner[1]):
                    continue
            elif operator_key in TIER_LOW_OPERATORS:
                winner = tier_low_best.get(metric)
                if winner is None or (pos, badge) != (winner[0], winner[1]):
                    continue
        earned.append(badge)

    return earned


def badge_catalog_from_rules(rules_df: pd.DataFrame) -> list[str]:
    """Unique badge names in sheet order."""
    return [item["name"] for item in badge_catalog_meta_from_rules(rules_df)]


def build_per_user_badge_history(
    long_df: pd.DataFrame,
    rules_df: pd.DataFrame,
) -> dict[str, set[str]]:
    """Union of all badges ever triggered by replaying stats after each finished match."""
    if long_df.empty or rules_df.empty:
        return {}

    history: dict[str, set[str]] = {}
    for uid, group in long_df.groupby("user_id"):
        earned: set[str] = set()
        codes: list[str] = []
        played = 0
        correct = 0
        missed = 0
        for _, row in group.sort_values("global_order").iterrows():
            pts = int(row.get("match_pts", 0) or 0)
            fine = int(row.get("match_fines", 0) or 0)
            has_pred = bool(row.get("has_pred", False))
            cum_pts = int(row.get("cum_pts", 0) or 0)
            cum_fines = int(row.get("cum_fines", 0) or 0)
            codes.append(str(row.get("form_code", "D")))
            if has_pred:
                played += 1
                if pts >= 3:
                    correct += 1
            else:
                missed += 1
            hp = compute_hp_fields(cum_fines)
            hit_rate = round(correct / played * 100, 1) if played > 0 else 0.0
            stats = {
                "total_penalties": float(cum_fines),
                "points": float(cum_pts),
                "hit_rate": hit_rate,
                "correct": float(correct),
                "missed": float(missed),
                "played": float(played),
                "remaining_hp": float(hp["remaining_hp"]),
                "win_streak": float(_trailing_streak_count(codes, {"W"})),
                "lose_streak": float(_trailing_streak_count(codes, {"L", "D"})),
            }
            earned.update(evaluate_user_achievements(stats, rules_df))
        history[str(uid)] = earned
    return history


def build_badge_collection_bundle(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
    rules_df: pd.DataFrame,
    leaderboard_df: pd.DataFrame | None = None,
) -> dict:
    """Data for the badge collection UI: catalog + per-player ever/current badges."""
    from leaderboard_service import _score_all_user_matches

    catalog_meta = badge_catalog_meta_from_rules(rules_df)
    catalog = [item["name"] for item in catalog_meta]
    rarity_map = {item["name"]: item["rarity"] for item in catalog_meta}
    description_map = {item["name"]: item.get("description", "") for item in catalog_meta}
    metric_map = {item["name"]: item.get("metric", "") for item in catalog_meta}
    long_df = _score_all_user_matches(users_df, preds_df, finished_matches_df)
    history = build_per_user_badge_history(long_df, rules_df)

    rank_by_user: dict[str, int] = {}
    name_by_user: dict[str, str] = {}
    current_by_user: dict[str, set[str]] = {}
    if leaderboard_df is not None and not leaderboard_df.empty:
        for _, row in leaderboard_df.iterrows():
            uid = str(row["user_id"])
            rank_by_user[uid] = int(row.get("rank", 0) or 0)
            name_by_user[uid] = str(row.get("name", ""))
            current_by_user[uid] = set(parse_badge_list(row.get("badges", [])))

    players: list[dict] = []
    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)
    for _, user in users.iterrows():
        uid = str(user["user_id"])
        ever_set = history.get(uid, set())
        current_set = current_by_user.get(uid, set())
        ever_ordered = [b for b in catalog if b in ever_set]
        players.append(
            {
                "user_id": uid,
                "name": name_by_user.get(uid) or str(user.get("name", "")),
                "rank": rank_by_user.get(uid, 0),
                "ever_badges": ever_ordered,
                "current_badges": sorted(current_set, key=lambda b: catalog.index(b) if b in catalog else 999),
                "unlocked_count": len(ever_ordered),
            }
        )

    players.sort(key=lambda p: (p["rank"] if p["rank"] > 0 else 9999, -p["unlocked_count"], p["name"]))

    total_unlocked = sum(p["unlocked_count"] for p in players)
    total_slots = len(catalog) * max(len(players), 1)

    return {
        "catalog": catalog,
        "catalog_meta": catalog_meta,
        "rarity_map": rarity_map,
        "description_map": description_map,
        "metric_map": metric_map,
        "rarity_totals": count_badges_by_rarity(catalog_meta),
        "players": players,
        "total_badges": len(catalog),
        "total_unlocked": total_unlocked,
        "total_slots": total_slots,
    }


def apply_achievements_to_leaderboard(
    leaderboard: pd.DataFrame,
    rules_df: pd.DataFrame,
    streaks: dict | None = None,
    per_user_streaks: dict[str, dict[str, int]] | None = None,
) -> pd.DataFrame:
    """Add badges column to leaderboard."""
    if leaderboard.empty:
        return leaderboard

    lb = leaderboard.copy()
    lb["badges"] = lb.apply(
        lambda row: evaluate_user_achievements(
            build_user_stats_dict(
                row.to_dict(),
                streaks=streaks,
                per_user_streaks=per_user_streaks,
            ),
            rules_df,
        ),
        axis=1,
    )
    return lb


def enrich_leaderboard_hp(leaderboard: pd.DataFrame) -> pd.DataFrame:
    """Attach remaining_hp and remaining_hp_pct to each leaderboard row."""
    if leaderboard.empty:
        return leaderboard

    lb = leaderboard.copy()
    hp_cols = lb["fines"].apply(lambda f: pd.Series(compute_hp_fields(int(f))))
    lb["remaining_hp"] = hp_cols["remaining_hp"].astype(int)
    lb["remaining_hp_pct"] = hp_cols["remaining_hp_pct"].astype(float)
    return lb
