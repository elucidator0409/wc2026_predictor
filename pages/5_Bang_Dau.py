import pandas as pd
import streamlit as st

from data_service import init_connection, prep_matches, read_sheet
from group_standings_service import compute_group_standings
from team_flags import build_name_to_fifa
from ui_components import (
    _html_inline,
    apply_global_styles,
    custom_loader,
    render_group_standings_grid,
    render_page_header,
    render_sidebar,
    sync_auth_session,
)

st.set_page_config(page_title="Bảng Đấu WC 2026", page_icon="📊", layout="wide", initial_sidebar_state="collapsed")

apply_global_styles()
sync_auth_session()
render_sidebar()

render_page_header(
    "📊 Bảng đấu vòng bảng",
    "12 bảng A–L · cập nhật theo kết quả thật",
    variant="fix",
    eyebrow="Group Standings",
)


@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    sh = init_connection()
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    return prep_matches(matches_raw, teams_df), teams_df


with custom_loader("Đang tính bảng đấu..."):
    matches_df, teams_df = load_data()

standings = compute_group_standings(matches_df, teams_df)
name_to_fifa = build_name_to_fifa(teams_df)

if not standings:
    st.info("Chưa có dữ liệu bảng đấu. Kết quả sẽ hiện khi admin cập nhật trận vòng bảng.")
    st.stop()

_html_inline('<div class="group-standings-page-marker"></div>')
render_group_standings_grid(standings, name_to_fifa=name_to_fifa)
