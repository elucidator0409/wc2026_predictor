import pandas as pd
import plotly.express as px
import streamlit as st

from data_service import init_connection, read_sheet
from ui_components import (
    apply_global_styles,
    custom_loader,
    render_page_header,
    render_podium,
    render_sidebar,
    render_stat_cards,
    sync_auth_session,
)

st.set_page_config(page_title="Bảng Xếp Hạng & Phân Tích", page_icon="🏆", layout="wide")

apply_global_styles()
sync_auth_session()
render_sidebar()

render_page_header(
    "🏆 Bảng vàng",
    "Xếp hạng điểm số, quỹ phạt và phân tích phong cách dự đoán",
    variant="rank",
    eyebrow="Leaderboard",
)


@st.cache_data(ttl=300, show_spinner=False)
def load_data_for_ranking():
    sh = init_connection()
    users_df = read_sheet(sh, "users")
    preds_df = read_sheet(sh, "predictions")
    matches_df = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")

    for df in (users_df, preds_df, matches_df):
        df.replace("", pd.NA, inplace=True)

    if "pred_advanced_team_id" not in preds_df.columns:
        preds_df["pred_advanced_team_id"] = None
    if "real_advanced_team_id" not in matches_df.columns:
        matches_df["real_advanced_team_id"] = None

    return users_df, preds_df, matches_df, teams_df


with custom_loader("Đang thống kê điểm số và quỹ phạt..."):
    users_df, preds_df, matches_df, teams_df = load_data_for_ranking()

users_df["user_id"] = users_df["user_id"].astype(str)
preds_df["user_id"] = preds_df["user_id"].astype(str)
teams_df["id"] = teams_df["id"].astype(str)

id_to_name = {str(row["id"]): row["team_name"] for _, row in teams_df.iterrows()}

if "real_score_a" not in matches_df.columns or "real_score_b" not in matches_df.columns:
    st.info("Chưa có kết quả trận đấu. Bảng xếp hạng sẽ hiện khi có kết quả đầu tiên!")
    st.stop()

id_col = "id" if "id" in matches_df.columns else "match_id"
finished_matches = matches_df[matches_df["real_score_a"].notna() & matches_df["real_score_b"].notna()].copy()

preds_df["match_id"] = preds_df["match_id"].astype(str)
finished_matches[id_col] = finished_matches[id_col].astype(str)

merged_df = pd.merge(preds_df, finished_matches, left_on="match_id", right_on=id_col, how="inner")


def calculate_points(row):
    try:
        pred_a, pred_b = int(float(row["pred_score_a"])), int(float(row["pred_score_b"]))
        real_a, real_b = int(float(row["real_score_a"])), int(float(row["real_score_b"]))
    except (ValueError, TypeError):
        return 0

    points = 0
    if pred_a == real_a and pred_b == real_b:
        points += 3
    else:
        pred_diff, real_diff = pred_a - pred_b, real_a - real_b
        if (pred_diff > 0 and real_diff > 0) or (pred_diff < 0 and real_diff < 0) or (pred_diff == 0 and real_diff == 0):
            points += 1

    try:
        stage = int(float(row.get("stage_id", 1)))
    except (ValueError, TypeError):
        stage = 1

    if stage > 1 and real_a == real_b and pred_a == pred_b:
        pred_adv = row.get("pred_advanced_team_id")
        real_adv = row.get("real_advanced_team_id")
        try:
            if pd.notna(pred_adv) and pd.notna(real_adv) and str(int(float(pred_adv))) == str(int(float(real_adv))):
                points += 1
        except (ValueError, TypeError):
            pass
    return points


def calculate_fines(row):
    try:
        pred_a, pred_b = int(float(row["pred_score_a"])), int(float(row["pred_score_b"]))
        real_a, real_b = int(float(row["real_score_a"])), int(float(row["real_score_b"]))
        try:
            stage = int(float(row.get("stage_id", 1)))
        except (ValueError, TypeError):
            stage = 1
    except (ValueError, TypeError):
        return 10

    def clean_id(val):
        if pd.isna(val) or str(val).strip() == "":
            return ""
        try:
            return str(int(float(val)))
        except (ValueError, TypeError):
            return str(val).strip()

    home_id = clean_id(row.get("home_team_id"))
    away_id = clean_id(row.get("away_team_id"))

    if real_a > real_b:
        real_winner = home_id
    elif real_a < real_b:
        real_winner = away_id
    else:
        real_winner = clean_id(row.get("real_advanced_team_id")) if stage > 1 else "DRAW"

    if pred_a > pred_b:
        pred_winner = home_id
    elif pred_a < pred_b:
        pred_winner = away_id
    else:
        pred_winner = clean_id(row.get("pred_advanced_team_id")) if stage > 1 else "DRAW"

    if pred_winner == real_winner and real_winner != "":
        return 0
    return 10


if not merged_df.empty:
    merged_df["points"] = merged_df.apply(calculate_points, axis=1)
    merged_df["fines"] = merged_df.apply(calculate_fines, axis=1)
    merged_df["points"] = pd.to_numeric(merged_df["points"], errors="coerce").fillna(0).astype(int)
    merged_df["fines"] = pd.to_numeric(merged_df["fines"], errors="coerce").fillna(0).astype(int)
    merged_df["user_id"] = merged_df["user_id"].astype(str)

    def get_outcome(a, b):
        try:
            a, b = float(a), float(b)
            if a > b:
                return "Win_A"
            if a < b:
                return "Win_B"
            return "Draw"
        except (ValueError, TypeError):
            return "Unknown"

    preds_df["outcome"] = preds_df.apply(lambda r: get_outcome(r["pred_score_a"], r["pred_score_b"]), axis=1)
    consensus = preds_df.groupby(["match_id", "outcome"]).size().reset_index(name="picks")
    total_picks = preds_df.groupby("match_id").size().reset_index(name="total")
    consensus = pd.merge(consensus, total_picks, on="match_id")
    consensus["pick_ratio"] = consensus["picks"] / consensus["total"]
    consensus["is_maverick"] = consensus["pick_ratio"] <= 0.3
    preds_analytics = pd.merge(
        preds_df, consensus[["match_id", "outcome", "is_maverick"]], on=["match_id", "outcome"], how="left"
    )

    maverick_stats = preds_analytics.groupby("user_id", as_index=False)["is_maverick"].sum().rename(
        columns={"is_maverick": "Maverick Picks"}
    )
    exact_score_stats = merged_df[merged_df["points"] >= 3].groupby("user_id", as_index=False).size().rename(
        columns={"size": "Exact Scores"}
    )
    total_played_stats = merged_df.groupby("user_id", as_index=False).size().rename(columns={"size": "Total Played"})

    tab1, tab2 = st.tabs(["🥇 Bảng điểm & quỹ phạt", "🧠 Phân tích phong cách"])

    with tab1:
        leaderboard_pts = merged_df.groupby("user_id", as_index=False)["points"].sum()
        leaderboard_fines = merged_df.groupby("user_id", as_index=False)["fines"].sum()

        leaderboard = pd.merge(users_df, leaderboard_pts, on="user_id", how="left")
        leaderboard = pd.merge(leaderboard, leaderboard_fines, on="user_id", how="left")
        leaderboard["points"] = leaderboard["points"].fillna(0).astype(int)
        leaderboard["fines"] = leaderboard["fines"].fillna(0).astype(int)
        leaderboard = leaderboard.sort_values(by=["points", "fines"], ascending=[False, True]).reset_index(drop=True)
        leaderboard["Hạng"] = leaderboard.index + 1

        display_df = leaderboard[["Hạng", "name", "points", "fines"]].rename(
            columns={"name": "Người chơi", "points": "Tổng điểm", "fines": "Tiền phạt (k)"}
        )

        if len(display_df) >= 1:
            top3 = [
                (display_df.iloc[i]["Người chơi"], int(display_df.iloc[i]["Tổng điểm"]))
                for i in range(min(3, len(display_df)))
            ]
            render_podium(top3)

        total_pts = int(display_df["Tổng điểm"].sum())
        total_fines = int(display_df["Tiền phạt (k)"].sum())
        render_stat_cards([
            (str(len(display_df)), "Người chơi"),
            (str(total_pts), "Tổng điểm"),
            (f"{total_fines}k", "Tổng quỹ phạt"),
            (str(len(finished_matches)), "Trận đã đá"),
        ])

        col1, col2 = st.columns([1.2, 1.3])
        with col1:
            dynamic_height = (len(display_df) + 1) * 35 + 40
            st.dataframe(display_df, width="stretch", hide_index=True, height=dynamic_height)
        with col2:
            if not display_df.empty and display_df["Tổng điểm"].sum() > 0:
                sorted_df = display_df.sort_values("Tổng điểm", ascending=True)
                fig = px.bar(
                    sorted_df,
                    y="Người chơi",
                    x="Tổng điểm",
                    orientation="h",
                    text="Tổng điểm",
                    color="Tổng điểm",
                    color_continuous_scale=["#1e3a8a", "#3b82f6", "#fbbf24"],
                )
                fig.update_traces(textposition="outside")
                fig.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#94a3b8", family="Inter"),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", title="Điểm số"),
                    yaxis=dict(title=""),
                    margin=dict(l=0, r=20, t=10, b=0),
                    height=max(300, len(sorted_df) * 40),
                    showlegend=False,
                    coloraxis_showscale=False,
                )
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Chưa có dữ liệu biểu đồ.")

        with st.expander("🔍 Chi tiết chấm điểm & tiền phạt từng trận"):
            detail_df = merged_df.copy()
            detail_df["user_id"] = detail_df["user_id"].astype(str)
            detail_df["home_team_id"] = detail_df["home_team_id"].astype(str)
            detail_df["away_team_id"] = detail_df["away_team_id"].astype(str)

            detail_df = pd.merge(detail_df, users_df[["user_id", "name"]], on="user_id", how="left")
            detail_df = pd.merge(
                detail_df, teams_df[["id", "team_name"]], left_on="home_team_id", right_on="id", how="left"
            ).rename(columns={"team_name": "Team A"})
            detail_df = pd.merge(
                detail_df, teams_df[["id", "team_name"]], left_on="away_team_id", right_on="id", how="left"
            ).rename(columns={"team_name": "Team B"})

            def format_score(row, prefix="real"):
                try:
                    score_a, score_b = int(float(row[f"{prefix}_score_a"])), int(float(row[f"{prefix}_score_b"]))
                except (ValueError, TypeError):
                    score_a, score_b = 0, 0
                base = f"{score_a} - {score_b}"
                try:
                    stage = int(float(row.get("stage_id", 1)))
                except (ValueError, TypeError):
                    stage = 1
                if stage > 1 and score_a == score_b:
                    adv_id = row.get(f"{prefix}_advanced_team_id")
                    if pd.notna(adv_id) and str(adv_id).strip():
                        adv_name = id_to_name.get(str(int(float(adv_id))), "")
                        if adv_name:
                            base += f" (PEN: {adv_name})"
                return base

            detail_df["Kết quả"] = detail_df.apply(lambda r: format_score(r, "real"), axis=1)
            detail_df["Dự đoán"] = detail_df.apply(lambda r: format_score(r, "pred"), axis=1)
            detail_df["Trận"] = detail_df.apply(
                lambda r: f"T{r['match_number']}: {r['Team A']} vs {r['Team B']}", axis=1
            )

            final_detail = detail_df[["name", "Trận", "Dự đoán", "Kết quả", "points", "fines"]]
            final_detail.columns = ["Người chơi", "Trận đấu", "Dự đoán", "Kết quả", "Điểm", "Phạt (k)"]
            st.dataframe(
                final_detail.sort_values(by=["Trận đấu", "Người chơi"]),
                width="stretch",
                hide_index=True,
            )

    with tab2:
        st.markdown('<div class="content-card-title">🧬 Hồ sơ dữ liệu người chơi</div>', unsafe_allow_html=True)
        analytics_df = pd.merge(users_df, total_played_stats, on="user_id", how="left").fillna(0)
        analytics_df = pd.merge(analytics_df, exact_score_stats, on="user_id", how="left").fillna(0)
        analytics_df = pd.merge(analytics_df, maverick_stats, on="user_id", how="left").fillna(0)
        analytics_df["Hit Rate (%)"] = (
            analytics_df.apply(
                lambda r: (r["Exact Scores"] / r["Total Played"] * 100)
                if r["Total Played"] > 0
                else 0,
                axis=1,
            )
        ).round(1)

        col_chart1, col_chart2 = st.columns(2)
        chart_layout = dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#94a3b8", family="Inter"),
        )

        with col_chart1:
            st.markdown("**🎯 Tỉ lệ bàn tay vàng (đúng tỉ số)**")
            if analytics_df["Total Played"].sum() > 0:
                fig1 = px.scatter(
                    analytics_df[analytics_df["Total Played"] > 0],
                    x="Hit Rate (%)",
                    y="name",
                    size="Exact Scores",
                    color="Hit Rate (%)",
                    color_continuous_scale=[[0, "#064e3b"], [0.5, "#10b981"], [1, "#fbbf24"]],
                )
                fig1.update_layout(**chart_layout, yaxis_title="", xaxis_title="Tỉ lệ trúng tỉ số (%)")
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
else:
    st.info("Chưa có dữ liệu dự đoán cho các trận đã đá.")
