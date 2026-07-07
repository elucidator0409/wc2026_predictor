import pandas as pd
import streamlit as st

from data_service import init_connection, prep_matches, read_sheet
from knockout_bracket_service import build_knockout_bracket
from team_flags import build_name_to_fifa
from ui_components import (
    _html_inline,
    apply_global_styles,
    custom_loader,
    render_knockout_bracket,
    render_page_header,
    render_sidebar,
    sync_auth_session,
)

st.set_page_config(page_title="Bracket Knock-out WC 2026", page_icon="🏅", layout="wide", initial_sidebar_state="collapsed")

apply_global_styles()
sync_auth_session()
render_sidebar()

render_page_header(
    "🏅 Bracket Knock-out",
    "Nhánh đấu loại trực tiếp · đội & tỉ số từ Góc của Elu",
    variant="fix",
    eyebrow="Knockout Bracket",
)


@st.cache_data(ttl=300, show_spinner=False)
def load_data():
    sh = init_connection()
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    return prep_matches(matches_raw, teams_df), teams_df


with custom_loader("Đang dựng bracket..."):
    matches_df, teams_df = load_data()

name_to_fifa = build_name_to_fifa(teams_df)
bracket = build_knockout_bracket(matches_df)

if not bracket.get("has_data"):
    st.info("Chưa có trận knock-out. Admin cài đặt cặp đấu tại **Góc của Elu → Vòng Knock-out**.")
    st.stop()

ko_matches = matches_df[matches_df["stage_id"].apply(lambda x: int(float(x)) > 1 if pd.notna(x) else False)]
assigned = ko_matches[
    ((ko_matches["team_a"].notna()) & (ko_matches["team_a"] != "TBD"))
    | ((ko_matches["team_b"].notna()) & (ko_matches["team_b"] != "TBD"))
]
finished = ko_matches[ko_matches["real_score_a"].notna() & ko_matches["real_score_b"].notna()]

st.caption(
    f"**{len(assigned)}** trận đã gán đội · **{len(finished)}** trận đã có kết quả · "
    "Vuốt ngang trên mobile để xem toàn bộ nhánh."
)

_html_inline('<div class="ko-bracket-page-marker" data-layout="split"></div>')
render_knockout_bracket(bracket, name_to_fifa)
