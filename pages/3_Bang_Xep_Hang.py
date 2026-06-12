import pandas as pd
import plotly.express as px
import streamlit as st

from data_service import init_connection, normalize_predictions_df, prep_matches, read_sheet
from leaderboard_service import build_leaderboard, latest_match_insight, podium_entries, top_rank_tie_count
from team_flags import build_name_to_fifa, flag_emoji
from scoring import _parse_stage, calculate_fines, calculate_points, format_pred_display, format_real_display, normalize_pred_outcome, outcome_to_analytics_key
from ui_components import (
    _html,
    apply_global_styles,
    custom_loader,
    render_leaderboard_insight,
    render_leaderboard_podium,
    render_leaderboard_table,
    render_page_header,
    render_sidebar,
    render_stat_cards,
    sync_auth_session,
)

_LB_CHART_COLORS = [
    "#60a5fa", "#fbbf24", "#34d399", "#f472b6", "#a78bfa",
    "#fb923c", "#22d3ee", "#a3e635", "#e879f9", "#f87171",
    "#38bdf8", "#fde047", "#4ade80", "#c084fc",
]

st.set_page_config(page_title="Bảng Xếp Hạng & Phân Tích", page_icon="🏆", layout="wide")
apply_global_styles()
sync_auth_session()
render_sidebar()
render_page_header("🏆 Bảng vinh danh", "Xếp hạng điểm số, quỹ phạt & phong cách dự đoán", variant="rank", eyebrow="Leaderboard")


@st.cache_data(ttl=300, show_spinner=False)
def load_data_for_ranking():
    sh = init_connection()
    users_df, preds_df = read_sheet(sh, "users"), read_sheet(sh, "predictions")
    matches_raw, teams_df = read_sheet(sh, "matches"), read_sheet(sh, "teams")
    users_df.replace("", pd.NA, inplace=True)
    preds_df = normalize_predictions_df(preds_df)
    teams_df.replace("", pd.NA, inplace=True)
    matches_df = prep_matches(matches_raw, teams_df)
    return users_df, preds_df, matches_df, teams_df


with custom_loader("Đang thống kê điểm số và quỹ phạt..."):
    users_df, preds_df, matches_df, teams_df = load_data_for_ranking()

users_df["user_id"] = users_df["user_id"].astype(str)
preds_df["user_id"] = preds_df["user_id"].astype(str)
teams_df["id"] = teams_df["id"].astype(str)
id_to_name = {str(row["id"]): row["team_name"] for _, row in teams_df.iterrows()}
name_to_fifa = build_name_to_fifa(teams_df)
current_user_id = st.session_state.get("authenticated_user_id")

if "real_score_a" not in matches_df.columns or "real_score_b" not in matches_df.columns:
    st.info("Chưa có kết quả trận đấu. Bảng xếp hạng sẽ hiện khi có kết quả đầu tiên!")
    st.stop()

id_col = "id" if "id" in matches_df.columns else "match_id"
finished_matches = matches_df[matches_df["real_score_a"].notna() & matches_df["real_score_b"].notna()].copy()
preds_df["match_id"] = preds_df["match_id"].astype(str)
finished_matches[id_col] = finished_matches[id_col].astype(str)

if finished_matches.empty:
    st.info("Chưa có dữ liệu dự đoán cho các trận đã đá.")
    st.stop()

merged_df = pd.merge(preds_df, finished_matches, left_on="match_id", right_on=id_col, how="inner")
if not merged_df.empty:
    merged_df["points"] = merged_df.apply(calculate_points, axis=1)
    merged_df["fines"] = merged_df.apply(calculate_fines, axis=1)
    merged_df["points"] = pd.to_numeric(merged_df["points"], errors="coerce").fillna(0).astype(int)
    merged_df["fines"] = pd.to_numeric(merged_df["fines"], errors="coerce").fillna(0).astype(int)
    merged_df["user_id"] = merged_df["user_id"].astype(str)

preds_df["outcome"] = preds_df["pred_outcome"].apply(
    lambda x: outcome_to_analytics_key(x) if normalize_pred_outcome(x) else "Unknown"
)
consensus = preds_df.groupby(["match_id", "outcome"]).size().reset_index(name="picks")
total_picks = preds_df.groupby("match_id").size().reset_index(name="total")
consensus = pd.merge(consensus, total_picks, on="match_id")
consensus["pick_ratio"] = consensus["picks"] / consensus["total"]
consensus["is_maverick"] = consensus["pick_ratio"] <= 0.3
preds_analytics = pd.merge(
    preds_df, consensus[["match_id", "outcome", "is_maverick"]], on=["match_id", "outcome"], how="left"
)

maverick_stats = (
    preds_analytics.groupby("user_id", as_index=False)["is_maverick"].sum().rename(columns={"is_maverick": "Maverick Picks"})
    if not preds_analytics.empty
    else pd.DataFrame(columns=["user_id", "Maverick Picks"])
)
if not merged_df.empty:
    correct_outcome_stats = merged_df[merged_df["points"] >= 3].groupby("user_id", as_index=False).size().rename(
        columns={"size": "Correct Outcomes"}
    )
    total_played_stats = merged_df.groupby("user_id", as_index=False).size().rename(columns={"size": "Total Played"})
else:
    correct_outcome_stats = pd.DataFrame(columns=["user_id", "Correct Outcomes"])
    total_played_stats = pd.DataFrame(columns=["user_id", "Total Played"])

tab1, tab2 = st.tabs(["🥇 Bảng điểm & quỹ phạt", "🧠 Phân tích phong cách"])

with tab1:
    _html('<div class="lb-page-marker" aria-hidden="true"></div>')
    leaderboard = build_leaderboard(users_df, preds_df, finished_matches)
    insight = latest_match_insight(finished_matches, preds_df, users_df)
    if insight:
        insight["top_tie_count"] = top_rank_tie_count(leaderboard)
        render_leaderboard_insight(insight)

    entries = podium_entries(leaderboard, limit=3)
    if entries and top_rank_tie_count(leaderboard) <= 3:
        render_leaderboard_podium(entries)

    total_pts = int(leaderboard["points"].sum())
    total_fines = int(leaderboard["fines"].sum())
    avg_hit = (
        round(leaderboard.loc[leaderboard["played"] > 0, "hit_rate"].mean(), 1)
        if leaderboard["played"].sum() > 0
        else 0
    )
    render_stat_cards(
        [
            (str(len(leaderboard)), "Người chơi", "👥"),
            (str(total_pts), "Tổng điểm", "⭐"),
            (f"{total_fines}k", "Tổng quỹ phạt", "💸"),
            (str(len(finished_matches)), "Trận đã đá", "⚽"),
            (f"{avg_hit}%", "TB tỉ lệ đúng", "🎯"),
        ],
        row_class="stats-row--lb",
    )

    table_rows = leaderboard.to_dict("records")
    chart_df = leaderboard[["name", "points"]].rename(columns={"name": "Người chơi", "points": "Tổng điểm"})

    col_table, col_chart = st.columns([1.25, 1])
    with col_table:
        render_leaderboard_table(table_rows, highlight_user_id=current_user_id)
    with col_chart:
        if not chart_df.empty and chart_df["Tổng điểm"].sum() > 0:
            fig = px.bar(
                chart_df.sort_values("Tổng điểm", ascending=True),
                y="Người chơi",
                x="Tổng điểm",
                orientation="h",
                text="Tổng điểm",
                color="Người chơi",
                color_discrete_sequence=_LB_CHART_COLORS,
            )
            fig.update_traces(textposition="outside")
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#cbd5e1", family="Inter", size=13),
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)", title="Điểm", dtick=1),
                yaxis=dict(title=""),
                margin=dict(l=0, r=16, t=8, b=0),
                height=min(360, max(220, len(chart_df) * 24)),
                showlegend=False,
            )
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("Chưa có dữ liệu biểu đồ.")

    with st.expander("🔍 Chi tiết chấm điểm & tiền phạt từng trận"):
            if merged_df.empty:
                st.info("Chưa có dự đoán nào cho các trận đã đá.")
            else:
                detail_df = merged_df.copy()
                detail_df["user_id"] = detail_df["user_id"].astype(str)
                detail_df["home_team_id"] = detail_df["home_team_id"].astype(str)
                detail_df["away_team_id"] = detail_df["away_team_id"].astype(str)
                detail_df = pd.merge(detail_df, users_df[["user_id", "name"]], on="user_id", how="left")
                detail_df = pd.merge(
                    detail_df,
                    teams_df[["id", "team_name", "fifa_code"]],
                    left_on="home_team_id",
                    right_on="id",
                    how="left",
                ).rename(columns={"team_name": "Team A", "fifa_code": "Team A FIFA"})
                detail_df = pd.merge(
                    detail_df,
                    teams_df[["id", "team_name", "fifa_code"]],
                    left_on="away_team_id",
                    right_on="id",
                    how="left",
                ).rename(columns={"team_name": "Team B", "fifa_code": "Team B FIFA"})

                def format_pred_row(row):
                    stage = _parse_stage(row)
                    adv_name = (
                        id_to_name.get(str(row.get("pred_advanced_team_id")), "")
                        if stage > 1
                        and normalize_pred_outcome(row.get("pred_outcome")) == "D"
                        and pd.notna(row.get("pred_advanced_team_id"))
                        else None
                    )
                    return format_pred_display(
                        row.get("pred_outcome"),
                        team_a=row.get("Team A", ""),
                        team_b=row.get("Team B", ""),
                        adv_team_name=adv_name,
                        is_knockout=stage > 1,
                        name_to_fifa=name_to_fifa,
                        team_a_fifa=row.get("Team A FIFA"),
                        team_b_fifa=row.get("Team B FIFA"),
                    )

                def format_real_row(row):
                    stage = _parse_stage(row)
                    adv_name = (
                        id_to_name.get(str(row.get("real_advanced_team_id")), "")
                        if stage > 1 and pd.notna(row.get("real_advanced_team_id"))
                        else None
                    )
                    return format_real_display(
                        row.get("real_score_a"), row.get("real_score_b"), adv_name=adv_name, stage=stage
                    )

                detail_df["Kết quả"] = detail_df.apply(format_real_row, axis=1)
                detail_df["Dự đoán"] = detail_df.apply(format_pred_row, axis=1)
                detail_df["Trận"] = detail_df.apply(
                    lambda r: (
                        f"T{r['match_number']}: "
                        f"{flag_emoji(r.get('Team A FIFA'), r.get('Team A'), name_to_fifa)} {r['Team A']} vs "
                        f"{r['Team B']} {flag_emoji(r.get('Team B FIFA'), r.get('Team B'), name_to_fifa)}"
                    ),
                    axis=1,
                )
                final_detail = detail_df[["name", "Trận", "Dự đoán", "Kết quả", "points", "fines"]]
                final_detail.columns = ["Người chơi", "Trận đấu", "Dự đoán", "Kết quả", "Điểm", "Phạt (k)"]
                st.dataframe(final_detail.sort_values(by=["Trận đấu", "Người chơi"]), width="stretch", hide_index=True)

with tab2:
        st.markdown('<div class="content-card-title">🧬 Hồ sơ dữ liệu người chơi</div>', unsafe_allow_html=True)
        analytics_df = (
            pd.merge(pd.merge(users_df, total_played_stats, on="user_id", how="left").fillna(0), correct_outcome_stats, on="user_id", how="left")
            .fillna(0)
        )
        analytics_df = pd.merge(analytics_df, maverick_stats, on="user_id", how="left").fillna(0)
        analytics_df["Hit Rate (%)"] = analytics_df.apply(
            lambda r: (r["Correct Outcomes"] / r["Total Played"] * 100) if r["Total Played"] > 0 else 0,
            axis=1,
        ).round(1)

        col_chart1, col_chart2 = st.columns(2)
        chart_layout = dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#cbd5e1", family="Inter", size=13),
        )

        with col_chart1:
            st.markdown("**🎯 Tỉ lệ đúng kết quả (A / Hòa / B)**")
            if analytics_df["Total Played"].sum() > 0:
                fig1 = px.scatter(
                    analytics_df[analytics_df["Total Played"] > 0],
                    x="Hit Rate (%)",
                    y="name",
                    size="Correct Outcomes",
                    color="Hit Rate (%)",
                    color_continuous_scale=[[0, "#064e3b"], [0.5, "#10b981"], [1, "#fbbf24"]],
                )
                fig1.update_layout(**chart_layout, yaxis_title="", xaxis_title="Tỉ lệ đúng kết quả (%)")
                st.plotly_chart(fig1, width="stretch")
            else:
                st.info("Chưa đủ dữ liệu.")

        with col_chart2:
            st.markdown("**🐺 Top Maverick (đi ngược đám đông)**")
            if analytics_df["Maverick Picks"].sum() > 0:
                fig2 = px.bar(
                    analytics_df.sort_values("Maverick Picks", ascending=True),
                    x="Maverick Picks",
                    y="name",
                    text="Maverick Picks",
                    orientation="h",
                    color="Maverick Picks",
                    color_continuous_scale=[[0, "#7c2d12"], [0.5, "#ea580c"], [1, "#fbbf24"]],
                )
                fig2.update_traces(textposition="outside")
                fig2.update_layout(**chart_layout, yaxis_title="", xaxis_title="Số lần bẻ lái")
                st.plotly_chart(fig2, width="stretch")
            else:
                st.info("Chưa đủ dữ liệu.")
