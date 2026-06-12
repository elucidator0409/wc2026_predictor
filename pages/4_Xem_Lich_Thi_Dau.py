import pandas as pd
import streamlit as st

from data_service import init_connection, prep_matches, read_sheet
from schedule_service import format_date_header_vn, is_group_stage
from scoring import _parse_int
from team_flags import build_name_to_fifa
from ui_components import (
    apply_global_styles,
    custom_loader,
    render_fixture_day_header,
    render_fixture_row,
    render_fixture_schedule_close,
    render_fixture_schedule_open,
    render_page_header,
    render_sidebar,
    render_stat_cards,
    sync_auth_session,
)

st.set_page_config(page_title="Xem Lịch Thi Đấu", page_icon="🗓️", layout="wide", initial_sidebar_state="collapsed")

apply_global_styles()
sync_auth_session()
render_sidebar()

group_filter_param = st.query_params.get("group", "").strip().upper()

render_page_header(
    "🏟️ Lịch thi đấu & kết quả",
    "104 trận World Cup 2026 — giờ Việt Nam (UTC+7)",
    variant="fix",
    eyebrow="Fixtures & Results",
)

if group_filter_param:
    st.info(f"Đang lọc **Bảng {group_filter_param}**")
    if st.button("Xem tất cả", key="clear_group_filter"):
        if "group" in st.query_params:
            del st.query_params["group"]
        st.rerun()


@st.cache_data(ttl=300, show_spinner=False)
def load_matches_data():
    sh = init_connection()
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    return prep_matches(matches_raw, teams_df), teams_df


with custom_loader("Đang tải dữ liệu trận đấu..."):
    matches_df, teams_df = load_matches_data()

name_to_fifa = build_name_to_fifa(teams_df)

pending_matches = matches_df[matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna()]
finished_matches = matches_df[matches_df["real_score_a"].notna() & matches_df["real_score_b"].notna()]

render_stat_cards([
    (str(len(matches_df)), "Tổng trận", "⚽"),
    (str(len(pending_matches)), "Sắp diễn ra", "⏳"),
    (str(len(finished_matches)), "Đã kết thúc", "✅"),
    ("UTC+7", "Múi giờ VN", "🕐"),
])

st.markdown(
    '<div class="fixture-helper">Giờ thi đấu theo lịch chính thức FIFA, quy đổi sang <strong>UTC+7</strong> (Việt Nam / WIB). '
    "Trận chưa đá hiển thị 0–0 mặc định.</div>",
    unsafe_allow_html=True,
)

tab1, tab2 = st.tabs(["⚽ Các trận sắp tới", "✅ Các trận đã kết thúc"])


def _filter_matches(df: pd.DataFrame, search: str, stage_filter: str, group_letter: str = "") -> pd.DataFrame:
    filtered = df.copy()
    if group_letter:
        filtered = filtered[
            filtered["group_round"].astype(str).str.upper().str.contains(f"GROUP {group_letter}", na=False)
            | filtered["match_label"].astype(str).str.upper().str.contains(f"BẢNG {group_letter}", na=False)
        ]
    if stage_filter == "Vòng bảng":
        filtered = filtered[filtered.apply(lambda r: is_group_stage(r.get("group_round"), r.get("stage_id")), axis=1)]
    elif stage_filter == "Knock-out":
        filtered = filtered[~filtered.apply(lambda r: is_group_stage(r.get("group_round"), r.get("stage_id")), axis=1)]

    if search.strip():
        q = search.strip().lower()
        filtered = filtered[
            filtered["team_a"].str.lower().str.contains(q, na=False)
            | filtered["team_b"].str.lower().str.contains(q, na=False)
            | filtered["match_label"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["group_round"].astype(str).str.lower().str.contains(q, na=False)
            | filtered["venue_line"].astype(str).str.lower().str.contains(q, na=False)
        ]
    return filtered.sort_values(["kickoff_vn", "match_number"], na_position="last").reset_index(drop=True)


def render_matches_list(df: pd.DataFrame, is_finished: bool = False) -> None:
    if df.empty:
        st.info("Không có trận đấu nào trong danh sách này.")
        return

    suffix = "done" if is_finished else "upcoming"
    st.markdown('<div class="fixture-toolbar-marker"></div>', unsafe_allow_html=True)
    col_search, col_filter = st.columns([2.2, 1], gap="medium")
    with col_search:
        search = st.text_input(
            "🔍 Tìm đội, bảng, sân:",
            placeholder="Ví dụ: Brazil, Bảng A, MetLife...",
            key=f"search_{suffix}",
        )
    with col_filter:
        stage_filter = st.segmented_control(
            "Loại trận",
            ["Tất cả", "Vòng bảng", "Knock-out"],
            default="Tất cả",
            key=f"stage_filter_{suffix}",
            label_visibility="collapsed",
            width="stretch",
        )

    filtered = _filter_matches(df, search, stage_filter, group_filter_param)
    if filtered.empty:
        st.warning("Không tìm thấy trận phù hợp.")
        return

    st.markdown(
        f'<div class="fixture-count">Hiển thị <strong>{len(filtered)}</strong> / {len(df)} trận · sắp xếp theo ngày UTC+7</div>',
        unsafe_allow_html=True,
    )

    render_fixture_schedule_open()
    current_date = None
    day_rows: list[tuple] = []

    for _, row in filtered.iterrows():
        kickoff = row.get("kickoff_vn")
        if pd.isna(kickoff):
            continue
        kickoff_dt = kickoff.to_pydatetime() if hasattr(kickoff, "to_pydatetime") else kickoff
        day_key = kickoff_dt.date()

        if current_date is not None and day_key != current_date:
            render_fixture_day_header(format_date_header_vn(day_rows[0][0]), len(day_rows))
            for item in day_rows:
                _render_fixture_row(item[1], is_finished)
            day_rows = []

        current_date = day_key
        day_rows.append((kickoff_dt, row))

    if day_rows:
        render_fixture_day_header(format_date_header_vn(day_rows[0][0]), len(day_rows))
        for item in day_rows:
            _render_fixture_row(item[1], is_finished)

    render_fixture_schedule_close()


def _render_fixture_row(row, is_finished: bool) -> None:
    score_a = _parse_int(row["real_score_a"]) if pd.notna(row["real_score_a"]) else 0
    score_b = _parse_int(row["real_score_b"]) if pd.notna(row["real_score_b"]) else 0
    render_fixture_row(
        match_number=row["match_number"],
        kickoff_vn=row["kickoff_vn"],
        team_a=row["team_a"],
        team_b=row["team_b"],
        team_a_fifa=row.get("team_a_fifa"),
        team_b_fifa=row.get("team_b_fifa"),
        name_to_fifa=name_to_fifa,
        venue_line=row.get("venue_line"),
        group_round=row.get("group_round") or row.get("match_label"),
        score_a=score_a,
        score_b=score_b,
        is_finished=is_finished,
    )


with tab1:
    render_matches_list(pending_matches, is_finished=False)

with tab2:
    render_matches_list(finished_matches, is_finished=True)
