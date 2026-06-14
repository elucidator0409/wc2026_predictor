import pandas as pd

from achievement_service import (
    MAX_HP,
    apply_achievements_to_leaderboard,
    badge_chip_style,
    build_badge_collection_bundle,
    build_badge_rarity_map,
    build_per_user_badge_history,
    build_per_user_streak_recent,
    build_user_stats_dict,
    compute_hp_fields,
    evaluate_user_achievements,
    normalize_badge_rarity,
    parse_badge_list,
)


from data_service import _normalize_operator_from_sheet, _serialize_operator_for_sheet


def test_operator_sheet_eq_alias():
    assert _serialize_operator_for_sheet("==") == "eq"
    assert _serialize_operator_for_sheet(">=") == ">="
    assert _normalize_operator_from_sheet("eq") == "=="
    assert _normalize_operator_from_sheet("=") == "=="


def test_evaluate_user_achievements_eq_operator_from_sheet():
    rules = pd.DataFrame(
        [
            {
                "id": "A010",
                "badge_name": "🎯 Chuẩn",
                "metric": "correct",
                "operator": "eq",
                "threshold_value": "5",
            }
        ]
    )
    rules["operator"] = rules["operator"].apply(_normalize_operator_from_sheet)
    stats = build_user_stats_dict(
        {"user_id": "U01", "fines": 0, "points": 15, "hit_rate": 62.5, "played": 8, "correct": 5, "missed": 0}
    )
    assert evaluate_user_achievements(stats, rules) == ["🎯 Chuẩn"]


def test_compute_hp_fields_full_and_clamped():
    full = compute_hp_fields(0)
    assert full["remaining_hp"] == MAX_HP
    assert full["remaining_hp_pct"] == 100.0

    # 30 fines = 30k VNĐ = 3 HP lost
    three_wrong = compute_hp_fields(30)
    assert three_wrong["remaining_hp"] == 137
    assert three_wrong["remaining_hp_pct"] == round(137 / MAX_HP * 100, 1)

    empty = compute_hp_fields(1400)
    assert empty["remaining_hp"] == 0
    assert empty["remaining_hp_pct"] == 0.0

    mid = compute_hp_fields(700)
    assert mid["remaining_hp"] == 70
    assert mid["remaining_hp_pct"] == 50.0


def test_build_per_user_streak_recent_trailing_only():
    timeline = pd.DataFrame(
        [
            {"user_id": "U01", "global_order": 1, "form_code": "W"},
            {"user_id": "U01", "global_order": 2, "form_code": "W"},
            {"user_id": "U01", "global_order": 3, "form_code": "W"},
            {"user_id": "U01", "global_order": 4, "form_code": "L"},
            {"user_id": "U01", "global_order": 5, "form_code": "W"},
            {"user_id": "U01", "global_order": 6, "form_code": "W"},
            {"user_id": "U02", "global_order": 1, "form_code": "W"},
            {"user_id": "U02", "global_order": 2, "form_code": "L"},
            {"user_id": "U02", "global_order": 3, "form_code": "D"},
            {"user_id": "U02", "global_order": 4, "form_code": "L"},
        ]
    )
    streaks = build_per_user_streak_recent(timeline)
    assert streaks["U01"]["win_streak"] == 2
    assert streaks["U01"]["lose_streak"] == 0
    assert streaks["U02"]["win_streak"] == 0
    assert streaks["U02"]["lose_streak"] == 3


def test_evaluate_user_achievements_total_penalties():
    rules = pd.DataFrame(
        [
            {
                "id": "A001",
                "badge_name": "🔮 Pháp Sư Mù",
                "metric": "total_penalties",
                "operator": ">=",
                "threshold_value": "50",
            }
        ]
    )
    stats = build_user_stats_dict({"user_id": "U01", "fines": 60, "points": 10, "hit_rate": 50, "played": 8, "correct": 4, "missed": 1})
    assert evaluate_user_achievements(stats, rules) == ["🔮 Pháp Sư Mù"]

    stats_low = build_user_stats_dict({"user_id": "U01", "fines": 10, "points": 10, "hit_rate": 50, "played": 8, "correct": 4, "missed": 0})
    assert evaluate_user_achievements(stats_low, rules) == []


def test_evaluate_user_achievements_win_streak_per_user():
    rules = pd.DataFrame(
        [
            {
                "id": "A002",
                "badge_name": "🔥 Chuỗi Vàng",
                "metric": "win_streak",
                "operator": ">=",
                "threshold_value": "3",
            }
        ]
    )
    per_user = {"U01": {"win_streak": 4, "lose_streak": 0}}
    stats = build_user_stats_dict(
        {"user_id": "U01", "fines": 0, "points": 20, "hit_rate": 80, "played": 5, "correct": 4, "missed": 0},
        per_user_streaks=per_user,
    )
    assert evaluate_user_achievements(stats, rules) == ["🔥 Chuỗi Vàng"]


def test_evaluate_skips_invalid_rules():
    rules = pd.DataFrame(
        [
            {"id": "X1", "badge_name": "Bad", "metric": "unknown_metric", "operator": ">=", "threshold_value": "1"},
            {"id": "X2", "badge_name": "Also Bad", "metric": "points", "operator": "eval", "threshold_value": "1"},
            {"id": "X3", "badge_name": "OK", "metric": "points", "operator": ">=", "threshold_value": "10"},
        ]
    )
    stats = build_user_stats_dict({"user_id": "U01", "fines": 0, "points": 15, "hit_rate": 0, "played": 0, "correct": 0, "missed": 0})
    assert evaluate_user_achievements(stats, rules) == ["OK"]


def test_apply_achievements_to_leaderboard():
    lb = pd.DataFrame(
        [
            {
                "user_id": "U01",
                "name": "Alice",
                "fines": 0,
                "points": 30,
                "hit_rate": 75.0,
                "played": 4,
                "correct": 3,
                "missed": 0,
            }
        ]
    )
    rules = pd.DataFrame(
        [
            {
                "id": "A003",
                "badge_name": "👑 Vua",
                "metric": "points",
                "operator": ">=",
                "threshold_value": "20",
            }
        ]
    )
    out = apply_achievements_to_leaderboard(lb, rules)
    assert out.iloc[0]["badges"] == ["👑 Vua"]


def test_total_penalties_exclusive_high_tier_only():
    rules = pd.DataFrame(
        [
            {"id": "A1", "badge_name": "Nuôi Heo", "metric": "total_penalties", "operator": ">=", "threshold_value": "12"},
            {"id": "A2", "badge_name": "Kim Cương", "metric": "total_penalties", "operator": ">=", "threshold_value": "125"},
            {"id": "A3", "badge_name": "Phú ông", "metric": "total_penalties", "operator": ">=", "threshold_value": "250"},
        ]
    )
    stats_high = build_user_stats_dict({"user_id": "U01", "fines": 350, "points": 0, "hit_rate": 0, "played": 0, "correct": 0, "missed": 0})
    assert evaluate_user_achievements(stats_high, rules) == ["Phú ông"]

    stats_mid = build_user_stats_dict({"user_id": "U01", "fines": 70, "points": 0, "hit_rate": 0, "played": 0, "correct": 0, "missed": 0})
    assert evaluate_user_achievements(stats_mid, rules) == ["Nuôi Heo"]

    stats_low = build_user_stats_dict({"user_id": "U01", "fines": 5, "points": 0, "hit_rate": 0, "played": 0, "correct": 0, "missed": 0})
    assert evaluate_user_achievements(stats_low, rules) == []


def test_total_penalties_exclusive_low_tier_only():
    rules = pd.DataFrame(
        [
            {"id": "B1", "badge_name": "Tiền lẻ", "metric": "total_penalties", "operator": "<=", "threshold_value": "124"},
            {"id": "B2", "badge_name": "Siêu tiết kiệm", "metric": "total_penalties", "operator": "<=", "threshold_value": "40"},
        ]
    )
    stats = build_user_stats_dict({"user_id": "U01", "fines": 30, "points": 0, "hit_rate": 0, "played": 0, "correct": 0, "missed": 0})
    assert evaluate_user_achievements(stats, rules) == ["Siêu tiết kiệm"]


def test_badge_chip_style_is_deterministic_and_unique():
    a = badge_chip_style("Nhập môn bet thủ")
    b = badge_chip_style("Nhập môn bet thủ")
    c = badge_chip_style("Bet thủ lành nghề")
    assert a == b
    assert a != c
    assert "border-color:hsl(" in a


def test_parse_badge_list_supports_list_and_legacy_string():
    assert parse_badge_list(["A", "B"]) == ["A", "B"]
    assert parse_badge_list("solo") == ["solo"]
    assert parse_badge_list("A\x1fB") == ["A", "B"]
    assert parse_badge_list([]) == []


def test_build_per_user_badge_history_replays_past_streak():
    long_df = pd.DataFrame(
        [
            {"user_id": "U01", "global_order": 1, "match_pts": 3, "match_fines": 0, "has_pred": True, "form_code": "W", "cum_pts": 3, "cum_fines": 0},
            {"user_id": "U01", "global_order": 2, "match_pts": 3, "match_fines": 0, "has_pred": True, "form_code": "W", "cum_pts": 6, "cum_fines": 0},
            {"user_id": "U01", "global_order": 3, "match_pts": 3, "match_fines": 0, "has_pred": True, "form_code": "W", "cum_pts": 9, "cum_fines": 0},
            {"user_id": "U01", "global_order": 4, "match_pts": 0, "match_fines": 0, "has_pred": True, "form_code": "L", "cum_pts": 9, "cum_fines": 0},
        ]
    )
    rules = pd.DataFrame(
        [
            {"id": "S1", "badge_name": "🔥 Chuỗi Vàng", "metric": "win_streak", "operator": ">=", "threshold_value": "3"},
        ]
    )
    history = build_per_user_badge_history(long_df, rules)
    assert "🔥 Chuỗi Vàng" in history["U01"]


def test_build_badge_collection_bundle_orders_catalog():
    users_df = pd.DataFrame([{"user_id": "U01", "name": "Alice"}])
    preds_df = pd.DataFrame(
        [
            {"user_id": "U01", "match_id": "M1", "pred_outcome": "home_win"},
            {"user_id": "U01", "match_id": "M2", "pred_outcome": "home_win"},
            {"user_id": "U01", "match_id": "M3", "pred_outcome": "home_win"},
        ]
    )
    finished = pd.DataFrame(
        [
            {"id": "M1", "match_number": 1, "real_outcome": "home_win", "kickoff_vn": "2026-06-01 20:00"},
            {"id": "M2", "match_number": 2, "real_outcome": "home_win", "kickoff_vn": "2026-06-02 20:00"},
            {"id": "M3", "match_number": 3, "real_outcome": "away_win", "kickoff_vn": "2026-06-03 20:00"},
        ]
    )
    rules = pd.DataFrame(
        [
            {"id": "A1", "badge_name": "🔥 Chuỗi", "metric": "win_streak", "operator": ">=", "threshold_value": "3"},
            {"id": "A2", "badge_name": "👑 Vua", "metric": "points", "operator": ">=", "threshold_value": "5"},
        ]
    )
    lb = pd.DataFrame(
        [
            {
                "user_id": "U01",
                "name": "Alice",
                "rank": 1,
                "fines": 0,
                "points": 9,
                "hit_rate": 66.7,
                "played": 3,
                "correct": 2,
                "missed": 0,
                "badges": ["👑 Vua"],
            }
        ]
    )
    bundle = build_badge_collection_bundle(users_df, preds_df, finished, rules, lb)
    assert bundle["catalog"] == ["🔥 Chuỗi", "👑 Vua"]
    player = bundle["players"][0]
    assert "🔥 Chuỗi" in player["ever_badges"]
    assert "👑 Vua" in player["ever_badges"]
    assert player["current_badges"] == ["👑 Vua"]


def test_normalize_badge_rarity_aliases():
    assert normalize_badge_rarity("Common") == "Common"
    assert normalize_badge_rarity("rare") == "Rare"
    assert normalize_badge_rarity("Legendary") == "Legend"
    assert normalize_badge_rarity("") == "Common"
    assert normalize_badge_rarity("huyền thoại") == "Legend"


def test_build_badge_rarity_map_uses_first_occurrence():
    rules = pd.DataFrame(
        [
            {"badge_name": "A", "rarity": "Rare"},
            {"badge_name": "A", "rarity": "Legend"},
            {"badge_name": "B", "rarity": ""},
        ]
    )
    out = build_badge_rarity_map(rules)
    assert out == {"A": "Rare", "B": "Common"}


def test_build_badge_collection_bundle_includes_rarity_meta():
    users_df = pd.DataFrame([{"user_id": "U01", "name": "Alice"}])
    rules = pd.DataFrame(
        [
            {"id": "A1", "badge_name": "Common One", "metric": "points", "operator": ">=", "threshold_value": "1", "rarity": "Common"},
            {"id": "A2", "badge_name": "Rare One", "metric": "points", "operator": ">=", "threshold_value": "5", "rarity": "Rare"},
        ]
    )
    bundle = build_badge_collection_bundle(users_df, pd.DataFrame(), pd.DataFrame(), rules)
    assert bundle["rarity_totals"] == {"Common": 1, "Rare": 1, "Legend": 0}
    assert bundle["catalog_meta"][1]["rarity"] == "Rare"


def test_build_badge_collection_bundle_includes_description_map():
    rules = pd.DataFrame(
        [
            {
                "id": "A1",
                "badge_name": "🎯 Sniper",
                "metric": "points",
                "operator": ">=",
                "threshold_value": "10",
                "rarity": "Rare",
                "description": "Đạt 10 điểm trở lên",
            }
        ]
    )
    bundle = build_badge_collection_bundle(
        pd.DataFrame([{"user_id": "U01", "name": "Alice"}]),
        pd.DataFrame(),
        pd.DataFrame(),
        rules,
    )
    assert bundle["description_map"]["🎯 Sniper"] == "Đạt 10 điểm trở lên"
    assert bundle["catalog_meta"][0]["description"] == "Đạt 10 điểm trở lên"


def test_filter_catalog_by_metric_preserves_order():
    catalog = ["B1", "B2", "B3"]
    catalog_meta = [
        {"name": "B1", "metric": "points"},
        {"name": "B2", "metric": "win_streak"},
        {"name": "B3", "metric": "points"},
    ]
    from ui_components import _filter_catalog_by_metric

    assert _filter_catalog_by_metric(catalog, catalog_meta, "all") == catalog
    assert _filter_catalog_by_metric(catalog, catalog_meta, "points") == ["B1", "B3"]
    assert _filter_catalog_by_metric(catalog, catalog_meta, "win_streak") == ["B2"]


def test_format_gallery_metric_fallback():
    from ui_components import format_gallery_metric

    assert format_gallery_metric("all") == "🌟 Tất cả"
    assert format_gallery_metric("win_streak") == "🔥 Chuỗi Thắng"
    assert format_gallery_metric("custom_metric") == "Custom metric"
