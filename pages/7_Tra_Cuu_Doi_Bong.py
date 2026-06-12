import pandas as pd
import streamlit as st

from data_service import init_connection, read_sheet
from players_service import (
    filter_squad,
    load_players_df,
    prep_players,
    squad_by_position,
    squad_summary,
    team_options,
)
from team_flags import build_name_to_fifa
from ui_components import (
    apply_global_styles,
    custom_loader,
    render_page_header,
    render_sidebar,
    render_squad_player_table,
    render_squad_team_header,
    sync_auth_session,
)

st.set_page_config(page_title="Tra cứu đội hình", page_icon="👕", layout="wide", initial_sidebar_state="collapsed")

apply_global_styles()
sync_auth_session()
render_sidebar()

team_param = st.query_params.get("team", "").strip().upper()

render_page_header(
    "👕 Tra cứu đội hình",
    "48 đội · 26 cầu thủ mỗi đội — caps, bàn thắng, CLB",
    variant="fix",
    eyebrow="Squad Lookup",
)


@st.cache_data(ttl=3600, show_spinner=False)
def load_squad_data():
    sh = init_connection()
    players_raw = load_players_df(sh)
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    players_df = prep_players(players_raw, teams_df)
    return players_df, teams_df


with custom_loader("Đang tải dữ liệu cầu thủ..."):
    players_df, teams_df = load_squad_data()

if players_df.empty:
    st.error("Chưa có dữ liệu cầu thủ. Kiểm tra tab `wc2026_full_players_1200` trên Google Sheet.")
    st.stop()

name_to_fifa = build_name_to_fifa(teams_df)
options = team_options(teams_df)
if not options:
    st.error("Chưa có dữ liệu đội.")
    st.stop()

labels = [o["label"] for o in options]
code_by_label = {o["label"]: o["fifa_code"] for o in options}
meta_by_code = {o["fifa_code"]: o for o in options}

default_label = labels[0]
if team_param and team_param in meta_by_code:
    default_label = meta_by_code[team_param]["label"]
else:
    for o in options:
        if o["fifa_code"] == team_param:
            default_label = o["label"]
            break

default_idx = labels.index(default_label) if default_label in labels else 0

col_pick, col_search = st.columns([1.2, 1])
with col_pick:
    picked_label = st.selectbox("Chọn đội", labels, index=default_idx, key="squad_team_pick")
with col_search:
    search_q = st.text_input("Tìm cầu thủ / CLB", placeholder="vd. Messi, Barcelona...", key="squad_search")

selected_code = code_by_label[picked_label]
meta = meta_by_code[selected_code]

if st.query_params.get("team", "").upper() != selected_code:
    st.query_params["team"] = selected_code

pos_tabs = st.tabs(["Tất cả", "GK", "DF", "MF", "FW"])
pos_map = ["ALL", "GK", "DF", "MF", "FW"]

for tab, pos in zip(pos_tabs, pos_map):
    with tab:
        squad = filter_squad(players_df, selected_code, position=pos, search=search_q)
        summary = squad_summary(squad)
        render_squad_team_header(
            meta["team_name"],
            selected_code,
            meta.get("group_letter", ""),
            summary,
            name_to_fifa=name_to_fifa,
        )
        render_squad_player_table(squad_by_position(squad))
