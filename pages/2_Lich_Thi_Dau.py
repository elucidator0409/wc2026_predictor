import pandas as pd
import streamlit as st

from data_service import init_connection, prep_matches, read_sheet
from schedule_service import format_date_compact_vn, format_time_vn
from ui_components import apply_global_styles, custom_loader, render_page_header, render_sidebar, sync_auth_session, _get_col_letter

st.set_page_config(page_title="Admin - Cập Nhật Kết Quả", page_icon="🔒", layout="wide")

apply_global_styles()
sync_auth_session()
render_sidebar()

if "admin_logged_in" not in st.session_state: st.session_state["admin_logged_in"] = False

if not st.session_state["admin_logged_in"]:
    render_page_header("⚙️ Góc của Elu", "Đăng nhập để thao túng kết quả trận đấu", variant="admin", eyebrow="Admin Panel")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            pwd = st.text_input("Admin Password:", type="password")
            submit_login = st.form_submit_button("Đăng nhập", type="primary", width="stretch")
            if submit_login:
                correct_admin_pass = st.secrets.get("admin_password", "")
                if not correct_admin_pass: st.error("⚠️ Chưa cấu hình mật khẩu Admin (thiếu secrets.toml).")
                elif pwd == correct_admin_pass:
                    st.session_state["admin_logged_in"] = True
                    st.success("Đăng nhập thành công!")
                    st.rerun()
                else: st.error("❌ Sai mật khẩu.")
    st.stop()

col_title, col_logout = st.columns([8, 1])
with col_logout:
    if st.button("🚪 Đăng xuất"):
        st.session_state["admin_logged_in"] = False
        st.rerun()

if "success_msg" in st.session_state:
    st.success(st.session_state["success_msg"])
    del st.session_state["success_msg"]

render_page_header("⚙️ Quản trị kết quả", "Cập nhật tỉ số, cặp knock-out và khóa trận đấu", variant="admin", eyebrow="Admin Panel")

@st.cache_data(ttl=300, show_spinner=False)
def load_matches_data():
    sh = init_connection()
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    return prep_matches(matches_raw, teams_df), teams_df

with custom_loader("Đang đồng bộ dữ liệu quản trị..."):
    matches_df, teams_df = load_matches_data()

team_names_list = ["TBD"] + teams_df["team_name"].tolist()
name_to_id = {row["team_name"]: row["id"] for _, row in teams_df.iterrows()}
name_to_id["TBD"] = None
id_to_name = {str(row["id"]): row["team_name"] for _, row in teams_df.iterrows()}

pending_matches = matches_df[matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna()]
finished_matches = matches_df[matches_df["real_score_a"].notna() & matches_df["real_score_b"].notna()]

def _kickoff_label(row) -> str:
    kickoff = row.get("kickoff_vn")
    if kickoff is None:
        return ""
    try:
        dt = kickoff.to_pydatetime() if hasattr(kickoff, "to_pydatetime") else kickoff
        return f"🕐 {format_time_vn(dt)} UTC+7 · {format_date_compact_vn(dt)}"
    except (AttributeError, TypeError, ValueError):
        return ""


pending_matches = pending_matches.sort_values(["kickoff_vn", "match_number"])
finished_matches = finished_matches.sort_values(["kickoff_vn", "match_number"])
knockout_matches_sorted = matches_df[matches_df["stage_id"] > 1].sort_values(["kickoff_vn", "match_number"])
to_lock_matches_sorted = matches_df[
    (matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna())
].sort_values(["kickoff_vn", "match_number"])

tab_options = ["🔴 Chờ cập nhật", "🟢 Chỉnh sửa đã đá", "⚙️ Vòng Knock-out", "🔒 Khóa trận"]
active_tab = st.radio("Chọn chức năng:", tab_options, horizontal=True, key="active_tab", label_visibility="collapsed")
st.write("---")

def _apply_admin_updates(admin_inputs_dict, update_type="score"):
    sh = init_connection()
    ws_matches = sh.worksheet("matches")
    data_matches = ws_matches.get_all_values()
    raw_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()
    raw_df.replace("", pd.NA, inplace=True)
    id_col = "id" if "id" in raw_df.columns else "match_id"

    # Đảm bảo các cột cần thiết tồn tại
    for col in ("real_score_a", "real_score_b", "real_advanced_team_id", "home_team_id", "away_team_id", "is_locked"):
        if col not in raw_df.columns: raw_df[col] = None

    updates = []
    for m_id, payload in admin_inputs_dict.items():
        idx_list = raw_df.index[raw_df[id_col].astype(str) == m_id].tolist()
        if not idx_list: continue
        idx = idx_list[0]
        
        if update_type == "score":
            ra, rb, adv_t, is_ko = payload
            raw_df.loc[idx, "real_score_a"] = str(ra)
            raw_df.loc[idx, "real_score_b"] = str(rb)
            raw_df.loc[idx, "real_advanced_team_id"] = str(name_to_id[adv_t]) if is_ko and ra == rb and adv_t != "TBD" else None
        elif update_type == "knockout":
            team_a_name, team_b_name = payload
            raw_df.loc[idx, "home_team_id"] = str(name_to_id[team_a_name])
            raw_df.loc[idx, "away_team_id"] = str(name_to_id[team_b_name])
        elif update_type == "lock":
            lock_status = payload
            raw_df.loc[idx, "is_locked"] = str(lock_status).upper()

        row_data = raw_df.iloc[idx].fillna("").values.tolist()
        sheet_row = int(idx) + 2
        col_letter = _get_col_letter(len(row_data))
        updates.append({'range': f'A{sheet_row}:{col_letter}{sheet_row}', 'values': [row_data]})

    if updates: ws_matches.batch_update(updates)
    st.cache_data.clear()
    st.rerun()


if active_tab == tab_options[0]:
    st.markdown('<div class="content-card-title">Các trận chờ kết quả</div>', unsafe_allow_html=True)
    display_limit = st.slider("Số trận hiển thị", min_value=5, max_value=50, value=15, step=5)
    with st.form("update_score_form"):
        admin_inputs = {}
        for _, row in pending_matches.head(display_limit).iterrows():
            m_id = str(row["match_id"] if "match_id" in row else row["id"])
            team_a, team_b = row["team_a"], row["team_b"]
            is_knockout = int(float(row["stage_id"])) > 1

            kickoff = _kickoff_label(row)
            kickoff_html = f' <span>· {kickoff}</span>' if kickoff else ""
            st.markdown(
                f'<div class="pred-match-header">⚽ Trận {row["match_number"]}: {team_a} vs {team_b} '
                f'<span>· {row["match_label"]}</span>{kickoff_html}</div>',
                unsafe_allow_html=True,
            )
            col1, col2, col3, col4, col5 = st.columns([1.5, 1, 0.5, 1, 2])
            with col2: real_a = st.number_input(f"{team_a}", min_value=0, max_value=20, value=0, key=f"real_{m_id}_a", label_visibility="collapsed")
            with col3: st.markdown("<h4 style='text-align:center;margin:0;'>–</h4>", unsafe_allow_html=True)
            with col4: real_b = st.number_input(f"{team_b}", min_value=0, max_value=20, value=0, key=f"real_{m_id}_b", label_visibility="collapsed")
            with col1:
                adv_team = "TBD"
                if is_knockout and team_a != "TBD" and team_b != "TBD": adv_team = st.selectbox("PEN:", [team_a, team_b], key=f"adv_{m_id}")
            with col5: is_confirmed = st.checkbox("Xác nhận", key=f"confirm_{m_id}")

            if is_confirmed: admin_inputs[m_id] = (real_a, real_b, adv_team, is_knockout)
            st.write("---")

        if st.form_submit_button("🔥 Cập nhật lên Cloud", type="primary", width="stretch"):
            if not admin_inputs: st.warning("Chưa xác nhận trận nào!")
            else:
                st.session_state["success_msg"] = "✅ Đã cập nhật tỉ số thành công!"
                _apply_admin_updates(admin_inputs, "score")

elif active_tab == tab_options[1]:
    st.markdown('<div class="content-card-title">Chỉnh sửa trận đã có kết quả</div>', unsafe_allow_html=True)
    if finished_matches.empty: st.info("Chưa có trận nào được cập nhật kết quả.")
    else:
        with st.form("edit_score_form"):
            edit_inputs = {}
            for _, row in finished_matches.iterrows():
                m_id = str(row["match_id"] if "match_id" in row else row["id"])
                team_a, team_b = row["team_a"], row["team_b"]
                is_knockout = int(float(row["stage_id"])) > 1
                current_a = int(float(row["real_score_a"])) if pd.notna(row["real_score_a"]) else 0
                current_b = int(float(row["real_score_b"])) if pd.notna(row["real_score_b"]) else 0
                current_adv_id = str(row.get("real_advanced_team_id", "")).strip()
                current_adv_name = id_to_name.get(current_adv_id, "TBD") if current_adv_id else "TBD"

                kickoff = _kickoff_label(row)
                kickoff_suffix = f" · {kickoff}" if kickoff else ""
                st.markdown(f"**✏️ Trận {row['match_number']}: {team_a} vs {team_b}** *({row['match_label']})*{kickoff_suffix}")
                col1, col2, col3, col4, col5 = st.columns([1.5, 1, 0.5, 1, 2])
                with col2: edit_a = st.number_input(f"{team_a}", min_value=0, max_value=20, value=current_a, key=f"edit_{m_id}_a", label_visibility="collapsed")
                with col3: st.markdown("<h4 style='text-align:center;margin:0;'>–</h4>", unsafe_allow_html=True)
                with col4: edit_b = st.number_input(f"{team_b}", min_value=0, max_value=20, value=current_b, key=f"edit_{m_id}_b", label_visibility="collapsed")
                with col1:
                    adv_team = "TBD"
                    if is_knockout and team_a != "TBD" and team_b != "TBD":
                        options_adv = [team_a, team_b]
                        idx_adv = options_adv.index(current_adv_name) if current_adv_name in options_adv else 0
                        adv_team = st.selectbox("PEN:", options_adv, index=idx_adv, key=f"adv_edit_{m_id}")
                with col5: is_edited = st.checkbox("Xác nhận sửa", key=f"check_edit_{m_id}")

                if is_edited: edit_inputs[m_id] = (edit_a, edit_b, adv_team, is_knockout)
                st.write("---")

            if st.form_submit_button("💾 Lưu thay đổi", type="primary", width="stretch"):
                if not edit_inputs: st.warning("Chưa chọn trận nào để sửa.")
                else:
                    st.session_state["success_msg"] = "✅ Đã sửa kết quả thành công!"
                    _apply_admin_updates(edit_inputs, "score")

elif active_tab == tab_options[2]:
    st.markdown('<div class="content-card-title">Cài đặt cặp đấu Knock-out</div>', unsafe_allow_html=True)
    knockout_matches = knockout_matches_sorted.copy()

    with st.form("setup_knockout_form"):
        setup_inputs = {}
        for _, row in knockout_matches.iterrows():
            m_id = str(row["match_id"] if "match_id" in row else row["id"])
            idx_a = team_names_list.index(row["team_a"]) if row["team_a"] in team_names_list else 0
            idx_b = team_names_list.index(row["team_b"]) if row["team_b"] in team_names_list else 0

            st.markdown(f"**🛡️ Trận {row['match_number']} ({row['match_label']})**")
            col1, col2, col3 = st.columns([2, 0.5, 2])
            with col1: sel_a = st.selectbox("Nhà", team_names_list, index=idx_a, key=f"ko_a_{m_id}", label_visibility="collapsed")
            with col2: st.markdown("<h4 style='text-align:center;margin:0;'>VS</h4>", unsafe_allow_html=True)
            with col3: sel_b = st.selectbox("Khách", team_names_list, index=idx_b, key=f"ko_b_{m_id}", label_visibility="collapsed")
            setup_inputs[m_id] = (sel_a, sel_b)
            st.write("---")

        if st.form_submit_button("💾 Lưu cặp đấu", type="primary", width="stretch"):
            st.session_state["success_msg"] = "🏆 Đã cập nhật cặp đấu Knock-out!"
            _apply_admin_updates(setup_inputs, "knockout")

elif active_tab == tab_options[3]:
    st.markdown('<div class="content-card-title">🔒 Quản lý khóa dự đoán</div>', unsafe_allow_html=True)
    to_lock_matches = to_lock_matches_sorted.copy()

    if to_lock_matches.empty: st.info("Tất cả trận đã có kết quả.")
    else:
        with st.form("lock_matches_form"):
            lock_inputs = {}
            for _, row in to_lock_matches.iterrows():
                m_id = str(row["match_id"] if "match_id" in row else row["id"])
                is_currently_locked = str(row["is_locked"]).strip().upper() == "TRUE"
                col1, col2 = st.columns([3, 1])
                kickoff = _kickoff_label(row)
                kickoff_suffix = f" · {kickoff}" if kickoff else ""
                with col1: st.markdown(f"**⚽ Trận {row['match_number']}: {row['team_a']} vs {row['team_b']}**{kickoff_suffix}")
                with col2: lock_check = st.checkbox("Khóa", value=is_currently_locked, key=f"lock_{m_id}")
                lock_inputs[m_id] = lock_check
                st.write("---")

            if st.form_submit_button("🛡️ Cập nhật trạng thái khóa", type="primary", width="stretch"):
                st.session_state["success_msg"] = "🛡️ Đã cập nhật trạng thái khóa!"
                _apply_admin_updates(lock_inputs, "lock")