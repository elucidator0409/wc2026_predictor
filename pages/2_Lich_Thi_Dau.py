import streamlit as st
import pandas as pd
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

# 👉 Nhúng Component
from ui_components import apply_global_styles, custom_loader, sync_auth_session

st.set_page_config(page_title="Admin - Cập Nhật Kết Quả", page_icon="🔒", layout="wide")

# 👉 Gọi Global CSS
apply_global_styles()
sync_auth_session()

with st.sidebar:
    st.markdown("### 📌 MENU CHÍNH")
    st.page_link("app.py", label="Trang chủ", icon="🏠")
    st.page_link("pages/1_Du_Doan.py", label="Khu Vực Dự Đoán", icon="✍️")
    st.page_link("pages/3_Bang_Xep_Hang.py", label="Bảng Xếp Hạng", icon="🏆")
    st.page_link("pages/4_Xem_Lich_Thi_Dau.py", label="Lịch Thi Đấu", icon="🗓️")
    
    st.markdown("### 🔒 DÀNH CHO ADMIN")
    st.page_link("pages/2_Lich_Thi_Dau.py", label="Quản Trị Kết Quả", icon="⚙️")
    st.info("💡 Mẹo: Nhớ chốt đơn trước giờ bóng lăn nhé!")

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["spreadsheet_id"])

if 'admin_logged_in' not in st.session_state:
    st.session_state['admin_logged_in'] = False

if not st.session_state['admin_logged_in']:
    st.markdown("""
        <h1 style='color: #B91C1C; border-bottom: 3px solid #EF4444; padding-bottom: 10px;'>
            ⚙️ HỆ THỐNG QUẢN TRỊ (ADMIN)
        </h1>
    """, unsafe_allow_html=True)
    st.info("Vui lòng nhập mật khẩu để truy cập chức năng cập nhật tỉ số.")
    
    with st.form("login_form"):
        pwd = st.text_input("Mật khẩu Admin:", type="password")
        submit_login = st.form_submit_button("Đăng nhập", type="primary")
        
        if submit_login:
            try:
                correct_admin_pass = st.secrets["admin_password"]
            except KeyError:
                st.error("⚠️ Hệ thống chưa được cấu hình mật khẩu Admin (Thiếu file Secrets). Vui lòng liên hệ Developer!")
                st.stop()
                
            if pwd == correct_admin_pass: 
                st.session_state['admin_logged_in'] = True
                st.success("Đăng nhập thành công!")
                st.rerun()
            else:
                st.error("❌ Sai mật khẩu. Vui lòng thử lại!")
    st.stop()

col_title, col_logout = st.columns([8, 1])
with col_logout:
    if st.button("🚪 Đăng xuất"):
        st.session_state['admin_logged_in'] = False
        st.rerun()

if 'success_msg' in st.session_state:
    st.success(st.session_state['success_msg'])
    del st.session_state['success_msg']

st.markdown("""
    <h1 style='color: #B91C1C; border-bottom: 3px solid #EF4444; padding-bottom: 10px;'>
        ⚙️ HỆ THỐNG QUẢN TRỊ (ADMIN)
    </h1>
""", unsafe_allow_html=True)

# 👉 Tắt thông báo Spinner mặc định
@st.cache_data(ttl=300, show_spinner=False)
def load_matches_data():
    sh = init_connection()
    
    def read_safe(sheet_name):
        data = sh.worksheet(sheet_name).get_all_values()
        if not data: return pd.DataFrame()
        return pd.DataFrame(data[1:], columns=data[0])
        
    matches_raw = read_safe("matches")
    teams_df = read_safe("teams")
    
    matches_raw.replace("", pd.NA, inplace=True)
    teams_df.replace("", pd.NA, inplace=True)
    
    if 'real_score_a' not in matches_raw.columns:
        matches_raw['real_score_a'] = None
    if 'real_score_b' not in matches_raw.columns:
        matches_raw['real_score_b'] = None
    if 'real_advanced_team_id' not in matches_raw.columns:
        matches_raw['real_advanced_team_id'] = None 
    if 'is_locked' not in matches_raw.columns:
        matches_raw['is_locked'] = False
        
    matches_raw['home_team_id'] = pd.to_numeric(matches_raw['home_team_id'], errors='coerce').fillna(0).astype(int).astype(str)
    matches_raw['away_team_id'] = pd.to_numeric(matches_raw['away_team_id'], errors='coerce').fillna(0).astype(int).astype(str)
    teams_df['id'] = pd.to_numeric(teams_df['id'], errors='coerce').fillna(0).astype(int).astype(str)
    
    matches_df = pd.merge(matches_raw, teams_df[['id', 'team_name']], left_on='home_team_id', right_on='id', how='left')
    matches_df.rename(columns={'team_name': 'team_a'}, inplace=True)
    matches_df.drop('id_y', axis=1, inplace=True, errors='ignore')
    
    matches_df = pd.merge(matches_df, teams_df[['id', 'team_name']], left_on='away_team_id', right_on='id', how='left')
    matches_df.rename(columns={'team_name': 'team_b'}, inplace=True)
    matches_df.drop('id', axis=1, inplace=True, errors='ignore')
    
    matches_df.rename(columns={'id_x': 'match_id'}, inplace=True, errors='ignore')
    matches_df['match_id'] = matches_df['match_id'].astype(str)
    
    matches_df['team_a'] = matches_df['team_a'].fillna("TBD")
    matches_df['team_b'] = matches_df['team_b'].fillna("TBD")
    
    matches_df['stage_id'] = pd.to_numeric(matches_df['stage_id'], errors='coerce').fillna(1).astype(int)
    
    return matches_df, teams_df

# 👉 Bọc hàm load data bằng Custom Loader
with custom_loader("Đang đồng bộ dữ liệu quản trị..."):
    matches_df, teams_df = load_matches_data()

st.divider()

team_names_list = ["TBD"] + teams_df['team_name'].tolist()
name_to_id = {row['team_name']: row['id'] for _, row in teams_df.iterrows()}
name_to_id["TBD"] = None
id_to_name = {row['id']: row['team_name'] for _, row in teams_df.iterrows()}

pending_matches = matches_df[matches_df['real_score_a'].isna() | matches_df['real_score_b'].isna()]
finished_matches = matches_df[matches_df['real_score_a'].notna() & matches_df['real_score_b'].notna()]

tab_options = ["🔴 Chờ cập nhật", "🟢 Chỉnh sửa đã đá", "⚙️ Vòng Knock-out", "🔒 Khóa Trận Đấu"]
active_tab = st.radio("Chọn chức năng:", tab_options, horizontal=True, key="active_tab", label_visibility="collapsed")
st.write("---")

if active_tab == tab_options[0]:
    st.write("### Các trận đấu đang chờ kết quả")
    display_limit = st.slider("Số lượng trận hiển thị", min_value=5, max_value=50, value=15, step=5)
    
    with st.form("update_score_form"):
        admin_inputs = {}
        for index, row in pending_matches.head(display_limit).iterrows():
            m_id = str(row['match_id'] if 'match_id' in row else row['id'])
            team_a, team_b = row['team_a'], row['team_b']
            is_knockout = int(float(row['stage_id'])) > 1 
            
            st.markdown(f"**⚽ Trận {row['match_number']}: {team_a} vs {team_b}** *(Bảng/Vòng: {row['match_label']})*")
            col1, col2, col3, col4, col5 = st.columns([1.5, 1, 0.5, 1, 2])
            with col2:
                real_a = st.number_input(f"{team_a}", min_value=0, max_value=20, value=0, key=f"real_{m_id}_a", label_visibility="collapsed")
            with col3:
                st.markdown("<h4 style='text-align: center; margin: 0;'>-</h4>", unsafe_allow_html=True)
            with col4:
                real_b = st.number_input(f"{team_b}", min_value=0, max_value=20, value=0, key=f"real_{m_id}_b", label_visibility="collapsed")
            
            with col1:
                adv_team = "TBD"
                if is_knockout and team_a != "TBD" and team_b != "TBD":
                    adv_team = st.selectbox("Đội thắng Penalty:", [team_a, team_b], key=f"adv_{m_id}")
                    
            with col5:
                is_confirmed = st.checkbox("Xác nhận có kết quả", key=f"confirm_{m_id}")
            
            if is_confirmed:
                admin_inputs[m_id] = (real_a, real_b, adv_team, is_knockout)
            st.write("---")

        if st.form_submit_button("🔥 Cập nhật tỉ số lên Cloud", type="primary"):
            if not admin_inputs:
                st.warning("Bạn chưa 'Xác nhận' cho trận đấu nào!")
            else:
                sh = init_connection()
                ws_matches = sh.worksheet("matches")
                
                data_matches = ws_matches.get_all_values()
                raw_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()
                raw_df.replace("", pd.NA, inplace=True)
                
                id_col = 'id' if 'id' in raw_df.columns else 'match_id'
                if 'real_advanced_team_id' not in raw_df.columns: raw_df['real_advanced_team_id'] = None
                
                for m_id, (ra, rb, adv_t, is_ko) in admin_inputs.items():
                    raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_score_a'] = str(ra)
                    raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_score_b'] = str(rb)
                    if is_ko and ra == rb and adv_t != "TBD":
                        raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_advanced_team_id'] = name_to_id[adv_t]
                    else:
                        raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_advanced_team_id'] = None
                    
                    st.session_state.pop(f"real_{m_id}_a", None)
                    st.session_state.pop(f"real_{m_id}_b", None)
                    st.session_state.pop(f"adv_{m_id}", None)
                    st.session_state.pop(f"confirm_{m_id}", None)
                
                ws_matches.clear()
                raw_df = raw_df.astype(object).fillna("").replace(["nan", "NaN", "<NA>"], "")
                set_with_dataframe(ws_matches, raw_df)
                
                st.cache_data.clear()
                st.session_state['success_msg'] = "✅ Đã cập nhật tỉ số lên Cloud thành công!"
                st.rerun()

elif active_tab == tab_options[1]:
    st.write("### Chỉnh sửa các trận đã có kết quả")
    if finished_matches.empty:
        st.info("Chưa có trận đấu nào được cập nhật kết quả.")
    else:
        with st.form("edit_score_form"):
            edit_inputs = {}
            for index, row in finished_matches.iterrows():
                m_id = str(row['match_id'] if 'match_id' in row else row['id'])
                team_a, team_b = row['team_a'], row['team_b']
                is_knockout = int(float(row['stage_id'])) > 1
                current_a = int(float(row['real_score_a'])) if pd.notna(row['real_score_a']) and str(row['real_score_a']).strip() != "" else 0
                current_b = int(float(row['real_score_b'])) if pd.notna(row['real_score_b']) and str(row['real_score_b']).strip() != "" else 0
                try: current_adv_id = int(float(row.get('real_advanced_team_id', 0)))
                except: current_adv_id = None
                current_adv_name = id_to_name.get(str(current_adv_id), "TBD") if pd.notna(current_adv_id) else "TBD"

                st.markdown(f"**✏️ Trận {row['match_number']}: {team_a} vs {team_b}** *(Bảng/Vòng: {row['match_label']})*")
                col1, col2, col3, col4, col5 = st.columns([1.5, 1, 0.5, 1, 2])
                with col2:
                    edit_a = st.number_input(f"{team_a}", min_value=0, max_value=20, value=current_a, key=f"edit_{m_id}_a", label_visibility="collapsed")
                with col3:
                    st.markdown("<h4 style='text-align: center; margin: 0;'>-</h4>", unsafe_allow_html=True)
                with col4:
                    edit_b = st.number_input(f"{team_b}", min_value=0, max_value=20, value=current_b, key=f"edit_{m_id}_b", label_visibility="collapsed")
                with col1:
                    adv_team = "TBD"
                    if is_knockout and team_a != "TBD" and team_b != "TBD":
                        options_adv = [team_a, team_b]
                        idx_adv = options_adv.index(current_adv_name) if current_adv_name in options_adv else 0
                        adv_team = st.selectbox("Đội thắng Penalty:", options_adv, index=idx_adv, key=f"adv_edit_{m_id}")
                with col5:
                    is_edited = st.checkbox("Xác nhận sửa trận này", key=f"check_edit_{m_id}")
                
                if is_edited: edit_inputs[m_id] = (edit_a, edit_b, adv_team, is_knockout)
                st.write("---")

            if st.form_submit_button("💾 Lưu thay đổi lên Cloud", type="primary"):
                if not edit_inputs: st.warning("Bạn chưa chọn 'Xác nhận sửa' cho trận nào.")
                else:
                    sh = init_connection()
                    ws_matches = sh.worksheet("matches")
                    
                    data_matches = ws_matches.get_all_values()
                    raw_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()
                    raw_df.replace("", pd.NA, inplace=True)
                    
                    id_col = 'id' if 'id' in raw_df.columns else 'match_id'
                    if 'real_advanced_team_id' not in raw_df.columns: raw_df['real_advanced_team_id'] = None
                    
                    for m_id, (ea, eb, adv_t, is_ko) in edit_inputs.items():
                        raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_score_a'] = str(ea)
                        raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_score_b'] = str(eb)
                        if is_ko and ea == eb and adv_t != "TBD":
                            raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_advanced_team_id'] = name_to_id[adv_t]
                        else:
                            raw_df.loc[raw_df[id_col].astype(str) == m_id, 'real_advanced_team_id'] = None
                        
                        st.session_state.pop(f"edit_{m_id}_a", None)
                        st.session_state.pop(f"edit_{m_id}_b", None)
                        st.session_state.pop(f"adv_edit_{m_id}", None)
                        st.session_state.pop(f"check_edit_{m_id}", None)
                    
                    ws_matches.clear()
                    raw_df = raw_df.astype(object).fillna("").replace(["nan", "NaN", "<NA>"], "")
                    set_with_dataframe(ws_matches, raw_df)
                    st.cache_data.clear()
                    st.session_state['success_msg'] = "✅ Đã sửa kết quả trên Cloud thành công!"
                    st.rerun()

elif active_tab == tab_options[2]:
    st.write("### Cài đặt đội bóng tham gia Vòng Loại Trực Tiếp")
    knockout_matches = matches_df[matches_df['stage_id'] > 1].copy()
    
    with st.form("setup_knockout_form"):
        setup_inputs = {}
        for index, row in knockout_matches.iterrows():
            m_id = str(row['match_id'] if 'match_id' in row else row['id'])
            label = row['match_label'] 
            idx_a = team_names_list.index(row['team_a']) if row['team_a'] in team_names_list else 0
            idx_b = team_names_list.index(row['team_b']) if row['team_b'] in team_names_list else 0
            
            st.markdown(f"**🛡️ Trận {row['match_number']} ({label})**")
            col1, col2, col3 = st.columns([2, 0.5, 2])
            with col1:
                sel_a = st.selectbox(f"Đội Nhà (Trận {m_id})", options=team_names_list, index=idx_a, key=f"ko_a_{m_id}", label_visibility="collapsed")
            with col2:
                 st.markdown("<h4 style='text-align: center; margin: 0;'>ĐẤU VỚI</h4>", unsafe_allow_html=True)
            with col3:
                sel_b = st.selectbox(f"Đội Khách (Trận {m_id})", options=team_names_list, index=idx_b, key=f"ko_b_{m_id}", label_visibility="collapsed")
            setup_inputs[m_id] = (sel_a, sel_b)
            st.write("---")
            
        if st.form_submit_button("💾 Lưu Cặp Đấu Knock-out", type="primary"):
            sh = init_connection()
            ws_matches = sh.worksheet("matches")
            
            data_matches = ws_matches.get_all_values()
            raw_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()
            raw_df.replace("", pd.NA, inplace=True)
            
            id_col = 'id' if 'id' in raw_df.columns else 'match_id'
            
            for m_id, (team_a_name, team_b_name) in setup_inputs.items():
                raw_df.loc[raw_df[id_col].astype(str) == m_id, 'home_team_id'] = name_to_id[team_a_name]
                raw_df.loc[raw_df[id_col].astype(str) == m_id, 'away_team_id'] = name_to_id[team_b_name]
            
            ws_matches.clear()
            raw_df = raw_df.astype(object).fillna("").replace(["nan", "NaN", "<NA>"], "")
            set_with_dataframe(ws_matches, raw_df)
            st.cache_data.clear()
            st.session_state['success_msg'] = "🏆 Đã cập nhật xong cặp đấu Vòng Knock-out lên Cloud!"
            st.rerun()

elif active_tab == tab_options[3]:
    st.write("### 🔒 Quản Lý Khóa Dự Đoán")
    to_lock_matches = matches_df[matches_df['real_score_a'].isna() | matches_df['real_score_b'].isna()].copy()
    
    if to_lock_matches.empty:
        st.info("Tất cả các trận đấu đều đã đá xong và có kết quả.")
    else:
        with st.form("lock_matches_form"):
            lock_inputs = {}
            for index, row in to_lock_matches.iterrows():
                m_id = str(row['match_id'] if 'match_id' in row else row['id'])
                team_a, team_b = row['team_a'], row['team_b']
                is_currently_locked = str(row['is_locked']).strip().upper() == 'TRUE'
                col1, col2 = st.columns([3, 1])
                with col1: st.markdown(f"**⚽ Trận {row['match_number']}: {team_a} vs {team_b}**")
                with col2: lock_check = st.checkbox("Khóa (Cấm sửa)", value=is_currently_locked, key=f"lock_{m_id}")
                lock_inputs[m_id] = lock_check
                st.write("---")
                
            if st.form_submit_button("🛡️ Cập nhật Trạng Thái Khóa", type="primary"):
                sh = init_connection()
                ws_matches = sh.worksheet("matches")
                
                data_matches = ws_matches.get_all_values()
                raw_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()
                raw_df.replace("", pd.NA, inplace=True)
                
                id_col = 'id' if 'id' in raw_df.columns else 'match_id'
                if 'is_locked' not in raw_df.columns: raw_df['is_locked'] = False
                    
                for m_id, lock_status in lock_inputs.items():
                    raw_df.loc[raw_df[id_col].astype(str) == m_id, 'is_locked'] = str(lock_status).upper()
                
                ws_matches.clear()
                raw_df = raw_df.astype(object).fillna("").replace(["nan", "NaN", "<NA>"], "")
                set_with_dataframe(ws_matches, raw_df)
                st.cache_data.clear()
                st.session_state['success_msg'] = "🛡️ Đã khóa các trận đấu thành công trên Cloud!"
                st.rerun()