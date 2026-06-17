"""Desktop sidebar: activity feed and streak milestones for the leaderboard."""

from __future__ import annotations

import html
from zoneinfo import ZoneInfo

import pandas as pd

from analytics_service import (
    _parse_prediction_timestamp,
    build_scored_predictions,
    calculate_crowd_consensus,
    derive_actual_outcome,
)
from leaderboard_service import (
    _build_global_finished_order,
    _form_code,
    _match_id_col,
    _pred_lookup,
    format_fines_vnd,
    score_finished_match,
)
from schedule_service import group_letter, match_round_label_vn
from scoring import format_matchup_html, format_pred_pick_html, normalize_pred_outcome
from user_service import eligible_finished_matches, is_match_eligible, user_active_from

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_ACTIVITY_LIMIT = 25


def _now_vn() -> pd.Timestamp:
    return pd.Timestamp.now(tz=VN_TZ)


def _player_label(user_id: str, name: str) -> str:
    uid = str(user_id).strip()
    nm = str(name).strip()
    return f"{uid} {nm}" if nm else uid


def _relative_vn(ts: pd.Timestamp | None, *, now: pd.Timestamp | None = None) -> str:
    if ts is None or pd.isna(ts):
        return "Vừa xong"
    now = now or _now_vn()
    if getattr(ts, "tzinfo", None) is None:
        ts = ts.tz_localize(VN_TZ)
    else:
        ts = ts.tz_convert(VN_TZ)
    delta = now - ts
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "Vừa xong"
    if seconds < 120:
        return "Vừa xong"
    minutes = seconds // 60
    if minutes < 60:
        return f"Cách đây {minutes} phút"
    hours = minutes // 60
    if hours < 24:
        return f"Cách đây {hours} giờ"
    days = hours // 24
    if days == 1:
        return "Hôm qua"
    return f"Cách đây {days} ngày"


def _match_label(row: pd.Series) -> str:
    grp = match_round_label_vn(
        group_round=row.get("group_round"),
        match_label=row.get("match_label"),
        stage_id=row.get("stage_id"),
    )
    if grp and grp != "TBD":
        return grp
    a = row.get("team_a_fifa") or str(row.get("team_a", ""))[:3].upper()
    b = row.get("team_b_fifa") or str(row.get("team_b", ""))[:3].upper()
    return f"{a} vs {b}"


def _trailing_streak_window(rows: list[dict], target: set[str]) -> tuple[int, list[dict]]:
    """Trailing consecutive matches at the end of timeline matching target codes."""
    if not rows:
        return 0, []
    window: list[dict] = []
    for row in reversed(rows):
        if row["form_code"] in target:
            window.insert(0, row)
        else:
            break
    return len(window), window


def _max_streak_window(rows: list[dict], target: set[str]) -> tuple[int, list[dict]]:
    best_count = 0
    best_window: list[dict] = []
    cur: list[dict] = []
    for row in rows:
        if row["form_code"] in target:
            cur.append(row)
        else:
            if len(cur) > best_count:
                best_count = len(cur)
                best_window = cur.copy()
            cur = []
    if len(cur) > best_count:
        best_count = len(cur)
        best_window = cur
    return best_count, best_window


def _streak_stage_id(row: dict) -> int:
    try:
        return int(float(row.get("stage_id") or 1))
    except (TypeError, ValueError):
        return 1


def _streak_adv_name(row: dict, id_to_name: dict[str, str] | None) -> str | None:
    if _streak_stage_id(row) <= 1 or normalize_pred_outcome(row.get("pred_outcome")) != "D":
        return None
    adv_id = row.get("pred_advanced_team_id")
    if adv_id is None or pd.isna(adv_id) or not str(adv_id).strip():
        return None
    try:
        return (id_to_name or {}).get(str(int(float(adv_id))), "")
    except (TypeError, ValueError):
        return None


def _streak_draw_pick_html(
    row: dict,
    *,
    name_to_fifa: dict | None,
    id_to_name: dict[str, str] | None,
) -> str:
    """Draw pick for streak cards — show both teams, not just 🤝 Hòa."""
    team_a = str(row.get("team_a") or "")
    team_b = str(row.get("team_b") or "")
    matchup = format_matchup_html(
        team_a=team_a,
        team_b=team_b,
        name_to_fifa=name_to_fifa,
        team_a_fifa=row.get("team_a_fifa"),
        team_b_fifa=row.get("team_b_fifa"),
        compact=True,
    )
    pen_html = ""
    if _streak_stage_id(row) > 1:
        adv = _streak_adv_name(row, id_to_name)
        if adv:
            from team_flags import flag_img_html
            from scoring import _team_code

            pen_flag = flag_img_html(team_name=adv, name_to_fifa=name_to_fifa, size="sm")
            pen_code = html.escape(_team_code(adv, None, name_to_fifa))
            pen_html = f'<span class="pred-hist-pen"> · PEN: {pen_flag} {pen_code}</span>'
    return (
        f'<span class="pred-hist-pick-line lb-streak-pick-draw">'
        f"{matchup}"
        f'<span class="lb-streak-draw-label">🤝 Hòa</span>'
        f"{pen_html}"
        f"</span>"
    )


def _streak_pick_html(
    row: dict,
    *,
    name_to_fifa: dict | None,
    id_to_name: dict[str, str] | None,
) -> str:
    if row.get("form_code") == "D" and not row.get("has_pred"):
        return '<span class="lb-streak-pick lb-streak-pick--miss">Bỏ lỡ</span>'
    outcome = normalize_pred_outcome(row.get("pred_outcome"))
    team_a = str(row.get("team_a") or "")
    team_b = str(row.get("team_b") or "")
    if outcome == "D" and team_a and team_b:
        return _streak_draw_pick_html(
            row,
            name_to_fifa=name_to_fifa,
            id_to_name=id_to_name,
        )
    stage_id = _streak_stage_id(row)
    return format_pred_pick_html(
        row.get("pred_outcome"),
        team_a=team_a,
        team_b=team_b,
        adv_team_name=_streak_adv_name(row, id_to_name),
        is_knockout=stage_id > 1,
        name_to_fifa=name_to_fifa,
        team_a_fifa=row.get("team_a_fifa"),
        team_b_fifa=row.get("team_b_fifa"),
    )


def _format_streak_history_html(
    window: list[dict],
    *,
    name_to_fifa: dict | None,
    id_to_name: dict[str, str] | None,
    layout: str = "inline",
) -> str:
    if not window:
        return ""
    picks = [
        _streak_pick_html(row, name_to_fifa=name_to_fifa, id_to_name=id_to_name)
        for row in window
    ]
    if layout == "stack":
        steps = "".join(f'<div class="lb-streak-history-step">{pick}</div>' for pick in picks)
        return f'<div class="lb-streak-card-history lb-streak-card-history--stack">{steps}</div>'
    return '<span class="lb-streak-arrow">→</span>'.join(picks)


def _build_streak_timeline(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
) -> pd.DataFrame:
    """Per-user chronological match rows with metadata for streak history."""
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
        for _, match in eligible_finished_matches(finished, user).iterrows():
            m_id = str(match[id_col])
            pred = pred_by_key.get((uid, m_id))
            pts, _fine, has_pred = score_finished_match(pred, match)
            pred_outcome = pred.get("pred_outcome") if pred is not None else None
            pred_adv = pred.get("pred_advanced_team_id") if pred is not None else None
            rows.append(
                {
                    "user_id": uid,
                    "name": user["name"],
                    "global_order": int(match["global_order"]),
                    "form_code": _form_code(has_pred, pts),
                    "has_pred": has_pred,
                    "pred_outcome": pred_outcome,
                    "pred_advanced_team_id": pred_adv,
                    "team_a": match.get("team_a"),
                    "team_b": match.get("team_b"),
                    "team_a_fifa": match.get("team_a_fifa"),
                    "team_b_fifa": match.get("team_b_fifa"),
                    "stage_id": match.get("stage_id"),
                }
            )

    timeline = pd.DataFrame(rows)
    if timeline.empty:
        return timeline
    return timeline.sort_values(["user_id", "global_order"]).reset_index(drop=True)


def _streak_record(
    timeline_df: pd.DataFrame,
    target: set[str],
    *,
    name_to_fifa: dict | None = None,
    id_to_name: dict[str, str] | None = None,
) -> dict | None:
    if timeline_df.empty:
        return None
    best: dict | None = None
    for uid, group in timeline_df.groupby("user_id"):
        ordered = group.sort_values("global_order")
        rows = ordered.to_dict("records")
        streak, window = _trailing_streak_window(rows, target)
        if streak <= 0:
            continue
        name = str(ordered["name"].iloc[0])
        end_order = int(rows[-1]["global_order"]) if rows else 0
        candidate = {
            "user_id": str(uid),
            "name": name,
            "streak": streak,
            "history_html": _format_streak_history_html(
                window,
                name_to_fifa=name_to_fifa,
                id_to_name=id_to_name,
                layout="inline",
            ),
            "history_stack_html": _format_streak_history_html(
                window,
                name_to_fifa=name_to_fifa,
                id_to_name=id_to_name,
                layout="stack",
            ),
            "_end_order": end_order,
        }
        if best is None or streak > best["streak"]:
            best = candidate
        elif streak == best["streak"] and end_order > best["_end_order"]:
            best = candidate
    if best is not None:
        best = {k: v for k, v in best.items() if k != "_end_order"}
    return best


def _fine_reason(has_pred: bool, pts: int, match_row: pd.Series) -> str:
    if not has_pred:
        return "bỏ lỡ trận đấu"
    team_b = str(match_row.get("team_b", "đối thủ"))
    return f"trượt kèo {team_b}"


def _pred_lookup(preds_df: pd.DataFrame) -> dict[tuple[str, str], pd.Series]:
    lookup: dict[tuple[str, str], pd.Series] = {}
    if preds_df.empty:
        return lookup
    for _, row in preds_df.iterrows():
        lookup[(str(row["user_id"]), str(row["match_id"]))] = row
    return lookup


def _activity_event(
    *,
    event_at: pd.Timestamp,
    tone: str,
    icon: str,
    text: str,
    kind: str,
) -> dict:
    return {
        "event_at": event_at,
        "tone": tone,
        "icon": icon,
        "text": text,
        "kind": kind,
    }


def build_activity_feed(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
    leaderboard_df: pd.DataFrame,
) -> list[dict]:
    """Build sorted activity events for the desktop sidebar feed."""
    events: list[dict] = []
    now = _now_vn()

    users = users_df.copy()
    users["user_id"] = users["user_id"].astype(str)
    name_map = {str(r["user_id"]): str(r["name"]) for _, r in users.iterrows()}

    id_col = _match_id_col(matches_df) if not matches_df.empty else "match_id"
    matches = matches_df.copy()
    if not matches.empty:
        matches[id_col] = matches[id_col].astype(str)

    preds = preds_df.copy()
    if not preds.empty:
        preds["user_id"] = preds["user_id"].astype(str)
        preds["match_id"] = preds["match_id"].astype(str)

    # --- Recent predictions (timestamp) ---
    if not preds.empty and "timestamp" in preds.columns:
        merged_preds = pd.merge(
            preds,
            matches[[id_col, "group_round", "match_label", "stage_id", "kickoff_vn"]],
            left_on="match_id",
            right_on=id_col,
            how="left",
        )
        ts = _parse_prediction_timestamp(merged_preds["timestamp"])
        merged_preds["event_at"] = ts
        valid = merged_preds["event_at"].notna()
        recent = merged_preds.loc[valid].sort_values("event_at", ascending=False).head(20)
        for _, row in recent.iterrows():
            label = _player_label(row["user_id"], name_map.get(str(row["user_id"]), ""))
            grp = match_round_label_vn(
                group_round=row.get("group_round"),
                match_label=row.get("match_label"),
                stage_id=row.get("stage_id"),
            )
            rel = _relative_vn(row["event_at"], now=now)
            events.append(
                _activity_event(
                    event_at=row["event_at"],
                    tone="good",
                    icon="🟢",
                    text=f"{rel}: {label} vừa chốt kèo {grp}.",
                    kind="pred_recent",
                )
            )

    # --- Group sweep: all pending group matches predicted ---
    if (
        not matches.empty
        and "real_score_a" in matches.columns
        and "real_score_b" in matches.columns
        and not preds.empty
    ):
        pending = matches[matches["real_score_a"].isna() | matches["real_score_b"].isna()].copy()
        pending["group_ltr"] = pending["group_round"].apply(group_letter)
        pending = pending[pending["group_ltr"].notna()]
        pred_by_key = _pred_lookup(preds)

        for grp, grp_matches in pending.groupby("group_ltr"):
            match_ids = grp_matches[id_col].astype(str).tolist()
            if not match_ids:
                continue
            for _, user in users.iterrows():
                uid = str(user["user_id"])
                active = user_active_from(user)
                eligible_ids = [
                    str(m[id_col])
                    for _, m in grp_matches.iterrows()
                    if is_match_eligible(m, active)
                ]
                if not eligible_ids:
                    continue
                if not all((uid, m_id) in pred_by_key for m_id in eligible_ids):
                    continue
                timestamps = []
                for m_id in eligible_ids:
                    pred = pred_by_key[(uid, m_id)]
                    ts_val = pred.get("timestamp")
                    parsed = _parse_prediction_timestamp(pd.Series([ts_val])).iloc[0]
                    if pd.notna(parsed):
                        timestamps.append(parsed)
                event_at = max(timestamps) if timestamps else now
                label = _player_label(uid, user["name"])
                rel = _relative_vn(event_at, now=now)
                events.append(
                    _activity_event(
                        event_at=event_at,
                        tone="good",
                        icon="🟢",
                        text=f"{rel}: {label} vừa chốt xong toàn bộ kèo bảng {grp}.",
                        kind="group_sweep",
                    )
                )

    # --- Fine events from finished matches ---
    if not finished_matches_df.empty:
        finished = finished_matches_df.copy()
        finished[id_col] = finished[id_col].astype(str)
        pred_by_key = _pred_lookup(preds)

        for _, user in users.iterrows():
            uid = str(user["user_id"])
            for _, match in eligible_finished_matches(finished, user).iterrows():
                m_id = str(match[id_col])
                pred = pred_by_key.get((uid, m_id))
                pts, fine, has_pred = score_finished_match(pred, match)
                if fine <= 0:
                    continue
                kickoff = match.get("kickoff_vn")
                event_at = pd.to_datetime(kickoff, errors="coerce")
                if pd.isna(event_at):
                    event_at = now
                elif getattr(event_at, "tzinfo", None) is None:
                    event_at = event_at.tz_localize(VN_TZ)
                else:
                    event_at = event_at.tz_convert(VN_TZ)
                label = _player_label(uid, user["name"])
                vnd = format_fines_vnd(fine)
                reason = _fine_reason(has_pred, pts, match)
                events.append(
                    _activity_event(
                        event_at=event_at,
                        tone="bad",
                        icon="🔴",
                        text=f"Vừa xong: {label} chính thức nộp thêm {vnd} vào quỹ phạt vì {reason}.",
                        kind="fine_hit",
                    )
                )

    # --- Title race drama ---
    if not leaderboard_df.empty and len(leaderboard_df) >= 2:
        lb = leaderboard_df.sort_values(["rank", "points"], ascending=[True, False])
        leader = lb.iloc[0]
        challenger = lb.iloc[1]
        gap = int(leader["points"]) - int(challenger["points"])
        if gap <= 3:
            events.append(
                _activity_event(
                    event_at=now,
                    tone="warn",
                    icon="⚡",
                    text=(
                        f"Cảnh báo: Chỉ cần {_player_label(leader['user_id'], leader['name'])} "
                        f"tạch trận tới, {_player_label(challenger['user_id'], challenger['name'])} "
                        f"sẽ đoạt lấy Ngôi Vương!"
                    ),
                    kind="title_race",
                )
            )

    if not events:
        return []

    df = pd.DataFrame(events)
    df = df.sort_values("event_at", ascending=False).head(_ACTIVITY_LIMIT)
    return df.to_dict("records")


def compute_streak_milestones(
    timeline_df: pd.DataFrame,
    scored_df: pd.DataFrame,
    consensus_df: pd.DataFrame,
    users_df: pd.DataFrame,
    *,
    name_to_fifa: dict | None = None,
    id_to_name: dict[str, str] | None = None,
) -> dict:
    """Trailing win/lose streak leaders and sole upset predictor (Vua Bịp)."""
    win = _streak_record(
        timeline_df,
        {"W"},
        name_to_fifa=name_to_fifa,
        id_to_name=id_to_name,
    )
    lose = _streak_record(
        timeline_df,
        {"L", "D"},
        name_to_fifa=name_to_fifa,
        id_to_name=id_to_name,
    )

    upset_hero = None
    if not scored_df.empty and not consensus_df.empty:
        scored = scored_df.copy()
        scored["user_id"] = scored["user_id"].astype(str)
        scored["match_id"] = scored["match_id"].astype(str)
        scored["pred_outcome"] = scored["pred_outcome"].apply(normalize_pred_outcome)
        if "actual_outcome" not in scored.columns or scored["actual_outcome"].isna().all():
            scored["actual_outcome"] = derive_actual_outcome(scored)

        consensus = consensus_df.copy()
        consensus["match_id"] = consensus["match_id"].astype(str)

        merged = pd.merge(
            scored,
            consensus[["match_id", "favorite_pick", "consensus_votes", "total_votes"]],
            on="match_id",
            how="inner",
        )
        merged = merged[merged["actual_outcome"].notna() & merged["pred_outcome"].notna()]
        upsets = merged[merged["actual_outcome"] != merged["favorite_pick"]].copy()

        sort_cols = [c for c in ("kickoff_vn", "match_number") if c in upsets.columns]
        if sort_cols:
            upsets = upsets.sort_values(sort_cols, ascending=False)

        match_order = upsets["match_id"].drop_duplicates()
        for match_id in match_order:
            group = upsets[upsets["match_id"] == match_id]
            correct = group[group["pred_outcome"] == group["actual_outcome"]]
            if len(correct) != 1:
                continue
            row = correct.iloc[0]
            pct = 0.0
            if int(row.get("total_votes", 0)) > 0:
                pct = round(int(row["consensus_votes"]) / int(row["total_votes"]) * 100, 0)
            upset_hero = {
                "user_id": str(row["user_id"]),
                "name": str(row.get("name", "")),
                "match_label": _match_label(row),
                "detail": f"Đoán đúng kèo động đất — đám đông {pct:.0f}% chọn ngược lại",
            }
            break

    return {
        "win_streak": win,
        "lose_streak": lose,
        "upset_hero": upset_hero,
    }


def build_lb_desktop_sidebar_bundle(
    users_df: pd.DataFrame,
    preds_df: pd.DataFrame,
    matches_df: pd.DataFrame,
    finished_matches_df: pd.DataFrame,
    leaderboard_df: pd.DataFrame,
    *,
    name_to_fifa: dict | None = None,
    id_to_name: dict[str, str] | None = None,
) -> dict:
    """Activity feed + streak milestones for desktop sidebar."""
    timeline_df = _build_streak_timeline(users_df, preds_df, finished_matches_df)
    scored_df = build_scored_predictions(preds_df, finished_matches_df, users_df)
    consensus_df = calculate_crowd_consensus(preds_df)

    return {
        "activity": build_activity_feed(
            users_df,
            preds_df,
            matches_df,
            finished_matches_df,
            leaderboard_df,
        ),
        "streaks": compute_streak_milestones(
            timeline_df,
            scored_df,
            consensus_df,
            users_df,
            name_to_fifa=name_to_fifa,
            id_to_name=id_to_name,
        ),
    }


    
