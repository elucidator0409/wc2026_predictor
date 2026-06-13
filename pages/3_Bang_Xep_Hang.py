import pandas as pd
import plotly.express as px
import streamlit as st

from analytics_service import (
    OUTCOME_LABELS,
    OUTCOME_ORDER,
    RISK_CHART_COLORS,
    build_scored_predictions,
    calculate_crowd_consensus,
    format_accuracy_takeaway,
    format_lead_time_takeaway,
    format_momentum_takeaway,
    format_risk_bias_takeaway,
    get_confusion_matrix,
    get_cumulative_scores,
    get_prediction_lead_time,
    get_user_risk_profile,
    lead_time_medians,
    lead_time_stats,
    summarize_accuracy,
    summarize_lead_time,
    summarize_momentum,
    summarize_risk_bias,
    top_momentum_players,
)
from data_service import init_connection, normalize_predictions_df, prep_matches, read_sheet
from leaderboard_service import build_leaderboard, latest_match_insight, podium_entries, top_rank_tie_count
from team_flags import build_name_to_fifa, flag_emoji
from scoring import _parse_stage, calculate_fines, calculate_points, format_pred_display, format_real_display, normalize_pred_outcome
from ui_components import (
    _html,
    apply_global_styles,
    custom_loader,
    render_analytics_guide,
    render_analytics_insight_chips,
    render_analytics_section_header,
    render_analytics_sub_tabs,
    render_analytics_takeaway,
    render_lb_main_tabs,
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


@st.cache_data(ttl=300, show_spinner=False)
def build_analytics_bundle(users_df, preds_df, matches_df, finished_matches_df):
    scored_df = build_scored_predictions(preds_df, finished_matches_df, users_df)
    cumulative_df = get_cumulative_scores(scored_df)
    lead_df = get_prediction_lead_time(preds_df, matches_df, users_df)
    stats = lead_time_stats(preds_df, lead_df)
    consensus_df = calculate_crowd_consensus(preds_df)
    risk_profile_df = get_user_risk_profile(preds_df, consensus_df, users_df)
    return scored_df, cumulative_df, lead_df, stats, consensus_df, risk_profile_df


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

tab1, tab2 = render_lb_main_tabs(["🏆 Leaderboard", "📊 Phân tích dữ liệu hành vi"])

chart_layout = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#cbd5e1", family="Inter", size=13),
)

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
    _html('<div class="lb-analytics-panel-marker" aria-hidden="true"></div>')
    render_analytics_section_header(
        eyebrow="Insights",
        title="Phân tích dữ liệu hành vi",
        subtitle="Who's climbing the ranks, how picks match results, and when people lock in predictions.",
    )
    scored_df, cumulative_df, lead_df, lead_stats, consensus_df, risk_profile_df = build_analytics_bundle(
        users_df, preds_df, matches_df, finished_matches
    )
    outcome_caption = " · ".join(f"{code} = {OUTCOME_LABELS[code]}" for code in OUTCOME_ORDER)
    t_mom, t_acc, t_lead, t_risk = render_analytics_sub_tabs(
        ["🏁 Momentum", "🎯 Accuracy", "⏱️ Lead Time", "🎲 Risk Bias"]
    )

    with t_mom:
        render_analytics_guide(
            icon="📈",
            title="Cuộc đua điểm theo thời gian",
            summary=(
                "Mỗi đường là tổng điểm tích lũy của một người sau từng trận đã có kết quả. "
                "Ai leo nhanh hơn = dự đoán đúng nhiều hơn trong các trận vừa qua."
            ),
            tips=[
                "Đường đi ngang = không dự đoán trận đó (không cộng điểm, cũng không trừ trên biểu đồ).",
                "Chỉ tính trận đã đá — tiền phạt bỏ lỡ trận không hiện ở đây.",
                f"Hiện có {len(finished_matches)} trận đã có kết quả.",
            ],
        )
        if cumulative_df.empty:
            st.info("Chưa có dữ liệu để vẽ cuộc đua điểm.")
        else:
            mom_summary = summarize_momentum(cumulative_df, len(finished_matches))
            render_analytics_insight_chips(
                [
                    (mom_summary["leader_name"], "Đang dẫn đầu", "gold"),
                    (str(mom_summary["leader_points"]), "Điểm hiện tại", "ok"),
                    (
                        f"+{mom_summary['last_match_gain']}",
                        f"Trận #{mom_summary['last_match_number']} · {mom_summary['last_match_winner']}",
                        "info",
                    ),
                    (str(mom_summary["n_players"]), "Người có dự đoán", "muted"),
                ]
            )
            plot_ids = top_momentum_players(
                cumulative_df, limit=6, highlight_user_id=current_user_id
            )
            plot_df = cumulative_df[cumulative_df["user_id"].isin(plot_ids)].copy()
            n_hidden = int(cumulative_df["user_id"].nunique()) - plot_df["name"].nunique()
            if n_hidden > 0:
                _html(
                    f'<p class="analytics-tab-note">Biểu đồ hiển thị top 6 + bạn '
                    f"(ẩn {n_hidden} người còn lại để dễ đọc).</p>"
                )
            fig = px.line(
                plot_df,
                x="kickoff_vn",
                y="cumulative_points",
                color="name",
                markers=True,
                color_discrete_sequence=_LB_CHART_COLORS,
                labels={
                    "kickoff_vn": "Thời gian trận",
                    "cumulative_points": "Điểm tích lũy",
                    "name": "Người chơi",
                },
            )
            fig.update_layout(
                **chart_layout,
                xaxis=dict(gridcolor="rgba(255,255,255,0.06)", title=""),
                yaxis=dict(gridcolor="rgba(255,255,255,0.06)", title="Điểm tích lũy", dtick=1),
                margin=dict(l=0, r=16, t=8, b=0),
                height=360,
                legend=dict(title="", orientation="h", yanchor="bottom", y=-0.28, x=0),
            )
            st.plotly_chart(fig, width="stretch")
            render_analytics_takeaway(format_momentum_takeaway(mom_summary))

    with t_acc:
        render_analytics_guide(
            icon="🎯",
            title="Bạn hay dự đoán đúng kiểu gì?",
            summary=(
                "Bảng 3×3 so sánh dự đoán của bạn với kết quả thật. "
                "Ô chéo (trùng hàng & cột) = đoán đúng; ô khác = đoán sai theo hướng nào."
            ),
            tips=[
                f"Hàng = kết quả thật · Cột = bạn đã dự đoán. {outcome_caption}.",
                "Màu vàng đậm = nhiều lần trùng — càng sáng càng hay gặp.",
                "Chọn từng người ở dropdown để xem phong cách riêng.",
            ],
        )
        if scored_df.empty:
            st.info("Chưa có dữ liệu để vẽ bản đồ nhiệt.")
        else:
            user_options = (
                scored_df[["user_id", "name"]]
                .drop_duplicates()
                .sort_values("name")
                .reset_index(drop=True)
            )
            name_to_id = dict(zip(user_options["name"], user_options["user_id"]))
            name_list = user_options["name"].tolist()
            default_idx = 0
            if current_user_id:
                id_to_name = dict(zip(user_options["user_id"].astype(str), user_options["name"]))
                default_name = id_to_name.get(str(current_user_id))
                if default_name in name_list:
                    default_idx = name_list.index(default_name)
            col_pick, col_chart = st.columns([1, 1.35], gap="large")
            with col_pick:
                selected_name = st.selectbox("Chọn người chơi", name_list, index=default_idx)
                matrix = get_confusion_matrix(scored_df, name_to_id[selected_name])
                acc_summary = summarize_accuracy(matrix, selected_name)
                if acc_summary.get("total", 0) == 0:
                    st.info(f"{selected_name} chưa có dự đoán trên trận đã đá.")
                else:
                    render_analytics_insight_chips(
                        [
                            (f"{acc_summary['accuracy_pct']}%", "Tỉ lệ đúng", "ok" if acc_summary["accuracy_pct"] >= 50 else "bad"),
                            (f"{acc_summary['hits']}/{acc_summary['total']}", "Đúng / Tổng", "gold"),
                            (acc_summary["favorite_label"], "Hay chọn", "info"),
                        ]
                    )
                    render_analytics_takeaway(format_accuracy_takeaway(acc_summary))
            with col_chart:
                if acc_summary.get("total", 0) > 0:
                    axis_labels = [OUTCOME_LABELS[o] for o in OUTCOME_ORDER]
                    fig = px.imshow(
                        matrix.values,
                        x=axis_labels,
                        y=axis_labels,
                        text_auto=True,
                        aspect="equal",
                        color_continuous_scale=[[0, "rgba(15,23,42,0.9)"], [0.5, "#3b82f6"], [1, "#fbbf24"]],
                        labels=dict(x="Dự đoán", y="Thực tế", color="Số lần"),
                    )
                    fig.update_layout(
                        **chart_layout,
                        xaxis=dict(side="bottom", title="Dự đoán"),
                        yaxis=dict(title="Thực tế"),
                        margin=dict(l=0, r=16, t=8, b=0),
                        height=340,
                        coloraxis_showscale=True,
                    )
                    fig.update_traces(textfont=dict(size=16, color="#f8fafc"))
                    st.plotly_chart(fig, width="stretch")

    with t_lead:
        render_analytics_guide(
            icon="⏱️",
            title="Bạn thường dự đoán sớm hay sát giờ đá?",
            summary=(
                "Lead time = số giờ bạn gửi dự đoán trước giờ bóng lăn (giờ Việt Nam). "
                "Càng cao = càng sớm; gần 0 = sát giờ; âm = sau giờ đá (sửa muộn)."
            ),
            tips=[
                f"{lead_stats['with_timestamp']}/{lead_stats['total_predictions']} dự đoán có timestamp ({lead_stats['coverage_pct']}%).",
                "Biểu đồ cột = trung bình giờ trước giờ đá của mỗi người (dễ đọc hơn box plot).",
                "Mở «Chi tiết phân phối» nếu muốn xem khoảng dao động từng người.",
            ],
        )
        if lead_stats["total_predictions"] == 0:
            st.info("Chưa có dữ liệu dự đoán để phân tích lead time.")
        elif lead_stats["with_timestamp"] == 0:
            st.warning("Không có dự đoán nào ghi timestamp — cần Lưu lại dự đoán để có dữ liệu.")
        else:
            if lead_stats["coverage_pct"] < 50:
                st.warning(
                    f"Chỉ {lead_stats['coverage_pct']}% dự đoán có timestamp — biểu đồ có thể không đại diện."
                )
            lead_summary = summarize_lead_time(lead_df, lead_stats)
            median_df = lead_time_medians(lead_df)
            if median_df.empty:
                st.info("Chưa đủ dữ liệu timestamp hợp lệ để vẽ biểu đồ.")
            else:
                chips = [
                    (f"{lead_summary.get('overall_median_hours', '—')}h", "TB cả nhóm", "gold"),
                    (lead_summary.get("early_bird_name", "—"), "Dự sớm nhất", "ok"),
                    (lead_summary.get("last_minute_name", "—"), "Gần giờ đá nhất", "info"),
                ]
                if lead_stats["late_count"] > 0:
                    chips.append((str(lead_stats["late_count"]), "Sau giờ đá", "bad"))
                render_analytics_insight_chips(chips)
                bar_df = median_df.rename(
                    columns={"name": "Người chơi", "median_hours": "Giờ trước giờ đá"}
                )
                fig = px.bar(
                    bar_df.sort_values("Giờ trước giờ đá", ascending=True),
                    y="Người chơi",
                    x="Giờ trước giờ đá",
                    orientation="h",
                    text="Giờ trước giờ đá",
                    color="Người chơi",
                    color_discrete_sequence=_LB_CHART_COLORS,
                )
                fig.update_traces(texttemplate="%{x:.0f}h", textposition="outside")
                fig.update_layout(
                    **chart_layout,
                    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", title="Giờ trước giờ đá"),
                    yaxis=dict(title=""),
                    margin=dict(l=0, r=16, t=8, b=0),
                    height=min(420, max(260, len(bar_df) * 28)),
                    showlegend=False,
                )
                st.plotly_chart(fig, width="stretch")
                render_analytics_takeaway(format_lead_time_takeaway(lead_summary))
                with st.expander("📊 Chi tiết phân phối (box plot)"):
                    plot_df = lead_df[lead_df["lead_hours"].notna()].copy()
                    if plot_df.empty:
                        st.caption("Không có dữ liệu hợp lệ.")
                    else:
                        box_fig = px.box(
                            plot_df,
                            x="name",
                            y="lead_hours",
                            color="name",
                            color_discrete_sequence=_LB_CHART_COLORS,
                            labels={"name": "Người chơi", "lead_hours": "Giờ trước giờ đá"},
                        )
                        box_fig.update_layout(
                            **chart_layout,
                            xaxis=dict(title=""),
                            yaxis=dict(gridcolor="rgba(255,255,255,0.06)", title="Giờ trước giờ đá"),
                            margin=dict(l=0, r=16, t=8, b=0),
                            height=360,
                            showlegend=False,
                        )
                        _html(
                            '<p class="analytics-tab-note">Hộp = 50% dự đoán giữa; '
                            "vạch giữa = trung vị; râu = min/max.</p>"
                        )
                        st.plotly_chart(box_fig, width="stretch")

    with t_risk:
        render_analytics_guide(
            icon="🎲",
            title="Cửa trên vs Cửa dưới (Wisdom of the Crowd)",
            summary=(
                "Không có tỷ lệ cược nhà cái — hệ thống lấy pick được nhiều người chọn nhất trong trận "
                "làm Cửa trên (Safe). Ai chọn khác số đông được tính Cửa dưới (Risky)."
            ),
            tips=[
                "Safe (xanh dương) = đi theo đám đông · Risky (cam) = ngược số đông.",
                "Tính trên mọi dự đoán đã lưu, không chỉ trận đã đá.",
                f"Hiện có {len(consensus_df)} trận có consensus từ nhóm.",
            ],
        )
        if risk_profile_df.empty:
            st.info("Chưa có đủ dữ liệu để phân tích khẩu vị rủi ro.")
        else:
            risk_summary = summarize_risk_bias(risk_profile_df, consensus_df)
            chips = [
                (str(risk_summary["n_matches_with_consensus"]), "Trận có consensus", "gold"),
                (risk_summary.get("safest_name", "—"), "Hay đi theo đám đông", "ok"),
                (risk_summary.get("riskiest_name", "—"), "Hay chọn ngược đám đông", "info"),
            ]
            render_analytics_insight_chips(chips)
            color_map = {
                "Safe": RISK_CHART_COLORS["Safe"],
                "Risky": RISK_CHART_COLORS["Risky"],
            }
            fig = px.bar(
                risk_profile_df.sort_values("name"),
                x="name",
                y="pct",
                color="pick_type",
                barmode="stack",
                text="pct",
                color_discrete_map=color_map,
                category_orders={"pick_type": ["Safe", "Risky"]},
                labels={
                    "name": "Người chơi",
                    "pct": "Tỷ lệ (%)",
                    "pick_type": "Loại pick",
                },
            )
            fig.update_traces(texttemplate="%{y:.0f}%", textposition="inside")
            fig.update_layout(
                **chart_layout,
                xaxis=dict(title=""),
                yaxis=dict(range=[0, 100], ticksuffix="%", title="Tỷ lệ (%)"),
                margin=dict(l=0, r=16, t=8, b=0),
                height=380,
                legend=dict(title=""),
            )
            st.plotly_chart(fig, width="stretch")
            render_analytics_takeaway(format_risk_bias_takeaway(risk_summary))
