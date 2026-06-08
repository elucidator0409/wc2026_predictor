import pandas as pd
import streamlit as st

from data_service import init_connection, prep_matches, read_sheet
from ui_components import (
    apply_global_styles,
    custom_loader,
    render_match_card,
    render_page_header,
    render_sidebar,
    render_stat_cards,
    sync_auth_session,
)

st.set_page_config(page_title="Xem Lịch Thi Đấu", page_icon="🗓️", layout="wide")

apply_global_styles()
sync_auth_session()
render_sidebar()

render_page_header(
    "🏟️ Lịch thi đấu & kết quả",
    "Theo dõi toàn bộ 104 trận World Cup 2026",
    variant="fix",
    eyebrow="Fixtures & Results",
)


@st.cache_data(ttl=300, show_spinner=False)
def load_matches_data():
    sh = init_connection()
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    return prep_matches(matches_raw, teams_df)


with custom_loader("Đang tải dữ liệu trận đấu..."):
    matches_df = load_matches_data()

pending_matches = matches_df[matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna()]
finished_matches = matches_df[matches_df["real_score_a"].notna() & matches_df["real_score_b"].notna()]

render_stat_cards([
    (str(len(matches_df)), "Tổng trận", "⚽"),
    (str(len(pending_matches)), "Sắp diễn ra", "⏳"),
    (str(len(finished_matches)), "Đã kết thúc", "✅"),
    (str(matches_df["stage_id"].max()), "Giai đoạn", "🏆"),
])

st.caption("Trận chưa đá hiển thị 0–0 mặc định. Kết quả cập nhật realtime từ admin.")

tab1, tab2 = st.tabs(["⚽ Các trận sắp tới", "✅ Các trận đã kết thúc"])


def render_matches_list(df, is_finished=False):
    if df.empty:
        st.info("Không có trận đấu nào trong danh sách này.")
        return

    search = st.text_input(
        "🔍 Tìm đội hoặc bảng/vòng:",
        placeholder="Ví dụ: Brazil, Bảng A, Round of 16...",
        key=f"search_{'done' if is_finished else 'upcoming'}",
    )

    filtered = df
    if search.strip():
        q = search.strip().lower()
        filtered = df[
            df["team_a"].str.lower().str.contains(q, na=False)
            | df["team_b"].str.lower().str.contains(q, na=False)
            | df["match_label"].str.lower().str.contains(q, na=False)
        ]

    if filtered.empty:
        st.warning("Không tìm thấy trận phù hợp.")
        return

    st.caption(f"Hiển thị {len(filtered)} / {len(df)} trận")

    for _, row in filtered.iterrows():
        try:
            score_a = int(float(row["real_score_a"])) if pd.notna(row["real_score_a"]) else 0
            score_b = int(float(row["real_score_b"])) if pd.notna(row["real_score_b"]) else 0
        except (ValueError, TypeError):
            score_a, score_b = 0, 0

        render_match_card(
            row["match_number"],
            row["match_label"],
            row["team_a"],
            row["team_b"],
            score_a,
            score_b,
            is_finished=is_finished,
        )


with tab1:
    render_matches_list(pending_matches, is_finished=False)

with tab2:
    render_matches_list(finished_matches, is_finished=True)
