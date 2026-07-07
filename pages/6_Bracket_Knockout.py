import pandas as pd
import streamlit as st

from data_service import init_connection, prep_matches, read_sheet
from ui_components import (
    apply_global_styles,
    custom_loader,
    render_home_knockout_bracket,
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

render_home_knockout_bracket(matches_df, teams_df, stop_on_empty=True)
