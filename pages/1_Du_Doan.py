import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import hashlib
import gspread
from gspread_dataframe import set_with_dataframe
from google.oauth2.service_account import Credentials

# 👉 Nhúng Component
from ui_components import apply_global_styles, custom_loader,sync_auth_session

st.set_page_config(page_title="Dự Đoán WC 2026", page_icon="✍️", layout="wide")

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

if 'chk_reset_counter' not in st.session_state:
    st.session_state['chk_reset_counter'] = 0
if 'authenticated_user_id' not in st.session_state:
    st.session_state['authenticated_user_id'] = None



if 'success_msg_pred' in st.session_state:
    st.success(st.session_state['success_msg_pred'])
    st.toast("Lưu thành công! Bảng dự đoán đã được cập nhật.", icon="🎉")
    st.html("""
        <script>
            setTimeout(function() {
                window.scrollTo({top: 0, behavior: 'smooth'});
                const stApp = document.querySelector('.stApp');
                if (stApp) stApp.scrollTo({top: 0, behavior: 'smooth'});
            }, 100);
        </script>
    """)
    del st.session_state['success_msg_pred']

st.markdown("""
    <h1 style='text-align: center; color: #1E3A8A; border-bottom: 3px solid #3B82F6; padding-bottom: 10px; margin-bottom: 30px;'>
        ✍️ TRUNG TÂM DỰ ĐOÁN
    </h1>
""", unsafe_allow_html=True)

def hash_password(password):
    try:
        salt = st.secrets["password_salt"]
    except:
        salt = "MuoiMacDinh_@123"
    salted_password = str(password) + salt
    return hashlib.sha256(salted_password.encode('utf-8')).hexdigest()

@st.cache_resource
def init_connection():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=scopes
    )
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["spreadsheet_id"])

# 👉 Tắt thông báo Spinner mặc định
@st.cache_data(ttl=300, show_spinner=False)
def load_and_prep_data():
    sh = init_connection()
    
    def read_safe(sheet_name):
        data = sh.worksheet(sheet_name).get_all_values()
        if not data: 
            return pd.DataFrame()
        return pd.DataFrame(data[1:], columns=data[0])
    
    users_df = read_safe("users")
    preds_df = read_safe("predictions")
    matches_raw = read_safe("matches")
    teams_df = read_safe("teams")
    
    users_df.replace("", pd.NA, inplace=True)
    preds_df.replace("", pd.NA, inplace=True)
    matches_raw.replace("", pd.NA, inplace=True)
    
    if 'password' not in users_df.columns:
        users_df['password'] = "1234"
        
    users_df['user_id'] = users_df['user_id'].astype(str)
    users_df['name'] = users_df['name'].astype(str)
    users_df['password'] = users_df['password'].astype(str)
    
    if 'pred_advanced_team_id' not in preds_df.columns:
        preds_df['pred_advanced_team_id'] = None
    
    preds_df['user_id'] = preds_df['user_id'].astype(str)
    preds_df['match_id'] = preds_df['match_id'].astype(str)
        
    if 'real_score_a' not in matches_raw.columns:
        matches_raw['real_score_a'] = None
    if 'real_score_b' not in matches_raw.columns:
        matches_raw['real_score_b'] = None
    if 'real_advanced_team_id' not in matches_raw.columns:
        matches_raw['real_advanced_team_id'] = None
        
    if 'is_locked' not in matches_raw.columns:
        matches_raw['is_locked'] = False
    else:
        matches_raw['is_locked'] = matches_raw['is_locked'].astype(str).str.strip().str.upper() == 'TRUE'
        
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
    
    return users_df, matches_df, preds_df, teams_df

# 👉 Bọc hàm load data bằng Custom Loader
with custom_loader("Đang tải dữ liệu từ trung tâm dự đoán..."):
    users_df, matches_df, preds_df, teams_df = load_and_prep_data()

name_to_id = {row['team_name']: row['id'] for _, row in teams_df.iterrows()}
name_to_id["TBD"] = None
id_to_name = {row['id']: row['team_name'] for _, row in teams_df.iterrows()}
user_names = users_df['name'].tolist()

if not st.session_state['authenticated_user_id']:
    st.info("🔒 Vui lòng đăng nhập để tham gia dự đoán.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            login_id = st.text_input("👤 Tên hiển thị (hoặc Mã ID):", placeholder="Ví dụ: U01 hoặc Tên của bạn")
            login_pwd = st.text_input("🔑 Mật khẩu / Mã PIN:", type="password")
            submit_login = st.form_submit_button("Đăng nhập hệ thống", type="primary", use_container_width=True)
            
            if submit_login:
                login_id_clean = login_id.strip()
                user_match = users_df[(users_df['name'] == login_id_clean) | (users_df['user_id'] == login_id_clean)]
                
                if user_match.empty:
                    st.error("❌ Tên đăng nhập hoặc Mã ID không tồn tại!")
                else:
                    stored_password_hash = str(user_match['password'].values[0]).strip()
                    if len(stored_password_hash) < 64 and stored_password_hash.endswith('.0'):
                        stored_password_hash = stored_password_hash[:-2]
                        
                    if hash_password(login_pwd.strip()) == stored_password_hash or login_pwd.strip() == stored_password_hash:
                        st.session_state['authenticated_user_id'] = str(user_match['user_id'].values[0])
                        st.success("🔓 Đăng nhập thành công!")
                        st.rerun()
                    else:
                        st.error("❌ Sai mật khẩu! Vui lòng thử lại.")
    st.stop()

selected_user_id = st.session_state['authenticated_user_id']
user_row = users_df[users_df['user_id'] == selected_user_id]
selected_user_name = user_row['name'].values[0]
stored_password_hash = str(user_row['password'].values[0]).strip()
if len(stored_password_hash) < 64 and stored_password_hash.endswith('.0'):
    stored_password_hash = stored_password_hash[:-2]

with st.sidebar:
    st.write("### ⚙️ Quản lý tài khoản")
    st.write(f"👤 Đang đăng nhập: **{selected_user_name}**")
    
    with st.expander("📝 Đổi tên hiển thị"):
        with st.form("change_name_form"):
            new_name = st.text_input("Tên hiển thị mới:", value=selected_user_name)
            submit_name = st.form_submit_button("Cập nhật tên")
            
            if submit_name:
                new_name_clean = new_name.strip()
                if not new_name_clean:
                    st.error("❌ Tên không được để trống!")
                elif new_name_clean == selected_user_name:
                    st.warning("⚠️ Tên mới giống hệt tên cũ.")
                elif new_name_clean in user_names:
                    st.error("❌ Tên này đã có người sử dụng!")
                else:
                    sh = init_connection()
                    ws_users = sh.worksheet("users")
                    
                    data_users = ws_users.get_all_values()
                    fresh_users_df = pd.DataFrame(data_users[1:], columns=data_users[0]) if data_users else pd.DataFrame()
                    fresh_users_df.replace("", pd.NA, inplace=True)
                    
                    fresh_users_df['user_id'] = fresh_users_df['user_id'].astype(str)
                    fresh_users_df.loc[fresh_users_df['user_id'] == selected_user_id, 'name'] = new_name_clean
                    
                    ws_users.clear()
                    fresh_users_df = fresh_users_df.astype(object).fillna("").replace(["nan", "NaN", "<NA>"], "")
                    set_with_dataframe(ws_users, fresh_users_df)
                    
                    st.cache_data.clear()
                    st.success("✅ Đổi tên thành công!")
                    st.rerun()

    with st.expander("🔑 Đổi mật khẩu"):
        with st.form("change_password_form"):
            old_pass = st.text_input("Mật khẩu hiện tại", type="password")
            new_pass = st.text_input("Mật khẩu mới", type="password")
            confirm_pass = st.text_input("Xác nhận mật khẩu mới", type="password")
            submit_change = st.form_submit_button("Cập nhật mật khẩu")
            
            if submit_change:
                if hash_password(old_pass) != stored_password_hash and old_pass != stored_password_hash:
                    st.error("❌ Mật khẩu hiện tại không đúng!")
                elif new_pass != confirm_pass:
                    st.error("❌ Mật khẩu mới không khớp nhau!")
                elif len(new_pass) < 4:
                    st.error("⚠️ Mật khẩu phải có ít nhất 4 ký tự.")
                else:
                    sh = init_connection()
                    ws_users = sh.worksheet("users")
                    
                    data_users = ws_users.get_all_values()
                    fresh_users_df = pd.DataFrame(data_users[1:], columns=data_users[0]) if data_users else pd.DataFrame()
                    fresh_users_df.replace("", pd.NA, inplace=True)
                    
                    fresh_users_df['user_id'] = fresh_users_df['user_id'].astype(str)
                    fresh_users_df['password'] = fresh_users_df['password'].astype(str)
                    
                    fresh_users_df.loc[fresh_users_df['user_id'] == selected_user_id, 'password'] = hash_password(new_pass)
                    
                    ws_users.clear()
                    fresh_users_df = fresh_users_df.astype(object).fillna("").replace(["nan", "NaN", "<NA>"], "")
                    set_with_dataframe(ws_users, fresh_users_df)
                    
                    st.cache_data.clear()
                    st.success("✅ Đổi mật khẩu thành công! Cập nhật lại trang để áp dụng.")

    st.write("---")
    if st.button("🚪 Đăng xuất", type="primary", use_container_width=True):
        st.session_state['authenticated_user_id'] = None
        st.query_params.clear()
        st.rerun()

st.caption("💡 Hãy lựa chọn kỹ lưỡng. Các trận đấu sẽ tự động khóa trước giờ bóng lăn.")
tab1, tab2 = st.tabs(["✍️ Cập nhật dự đoán", "📜 Lịch sử dự đoán của bạn"])

with tab1:
    st.write(f"### Nhập dự đoán cho: **{selected_user_name}**")

    upcoming_matches = matches_df[(matches_df['real_score_a'].isna() | matches_df['real_score_b'].isna()) & (matches_df['is_locked'] != True)].copy()

    if upcoming_matches.empty:
        st.info("Tất cả các trận đấu hiện tại đã bị khóa hoặc đã kết thúc. Không còn trận nào để dự đoán!")
    else:
        st.info("Hệ thống hiện chỉ mở dự đoán cho **10 trận đấu tiếp theo** chưa bị khóa.")
        upcoming_matches = upcoming_matches.head(10)

        with st.form("prediction_form"):
            user_inputs = {}
            
            for index, row in upcoming_matches.iterrows():
                m_id = str(row['match_id'] if 'match_id' in row else row['id']) 
                team_a, team_b = row['team_a'], row['team_b']
                group_label, is_knockout = row['match_label'], row['stage_id'] > 1 
                
                old_pred = preds_df[(preds_df['user_id'] == selected_user_id) & (preds_df['match_id'].astype(str) == m_id)]
                # 🛡️ Áo giáp chống lỗi NaN
                default_a = int(float(old_pred['pred_score_a'].values[0])) if not old_pred.empty and pd.notna(old_pred['pred_score_a'].values[0]) and str(old_pred['pred_score_a'].values[0]).strip() != "" else 0
                default_b = int(float(old_pred['pred_score_b'].values[0])) if not old_pred.empty and pd.notna(old_pred['pred_score_b'].values[0]) and str(old_pred['pred_score_b'].values[0]).strip() != "" else 0
                
                old_adv_id = old_pred['pred_advanced_team_id'].values[0] if not old_pred.empty and pd.notna(old_pred['pred_advanced_team_id'].values[0]) else None
                old_adv_name = id_to_name.get(old_adv_id, "TBD") if old_adv_id else "TBD"

                st.markdown(f"**⚽ Trận {row['match_number']}: {team_a} vs {team_b}** *(Bảng/Vòng: {group_label})*")
                
                col1, col2, col3, col4, col5 = st.columns([1.5, 1, 0.5, 1, 1.5])
                with col2:
                    score_a = st.number_input(f"{team_a}", min_value=0, max_value=20, value=default_a, key=f"pred_{selected_user_id}_{m_id}_a", label_visibility="collapsed")
                with col3:
                     st.markdown("<h4 style='text-align: center; margin: 0;'>-</h4>", unsafe_allow_html=True)
                with col4:
                    score_b = st.number_input(f"{team_b}", min_value=0, max_value=20, value=default_b, key=f"pred_{selected_user_id}_{m_id}_b", label_visibility="collapsed")
                
                with col1:
                    adv_team = "TBD"
                    if is_knockout and team_a != "TBD" and team_b != "TBD":
                        options_adv = [team_a, team_b]
                        idx_adv = options_adv.index(old_adv_name) if old_adv_name in options_adv else 0
                        adv_team = st.selectbox("Đội đi tiếp:", options_adv, index=idx_adv, key=f"adv_{selected_user_id}_{m_id}")
                        st.caption("*(Chỉ tính nếu dự đoán Hòa)*")
                
                with col5:
                    dynamic_chk_key = f"chk_pred_{selected_user_id}_{m_id}_{st.session_state['chk_reset_counter']}"
                    is_confirmed = st.checkbox("Chốt dự đoán", key=dynamic_chk_key)
                
                if is_confirmed:
                    user_inputs[m_id] = (score_a, score_b, adv_team, is_knockout)
                    
                st.write("---")

            submitted = st.form_submit_button("💾 Lưu Dự Đoán", type="primary")

        if submitted:
            if not user_inputs:
                st.warning("Bạn chưa tích chọn 'Chốt dự đoán' cho bất kỳ trận nào.")
            else:
                sh = init_connection()
                ws_matches = sh.worksheet("matches")
                
                data_matches = ws_matches.get_all_values()
                fresh_matches_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()
                fresh_matches_df.replace("", pd.NA, inplace=True)
                
                new_preds, ignored_matches = [], []
                
                for m_id, (sa, sb, adv_t, is_ko) in user_inputs.items():
                    id_col_fresh = 'id' if 'id' in fresh_matches_df.columns else 'match_id'
                    match_status = fresh_matches_df[fresh_matches_df[id_col_fresh].astype(str) == m_id]
                    
                    is_locked_now = False
                    if not match_status.empty and 'is_locked' in match_status.columns:
                        is_locked_now = str(match_status['is_locked'].values[0]).strip().upper() == 'TRUE'
                    
                    if is_locked_now:
                        ignored_matches.append(m_id)
                        continue 
                    
                    adv_id = None
                    if is_ko and sa == sb and adv_t != "TBD":
                        adv_id = name_to_id.get(adv_t)

                    new_preds.append({
                        'user_id': selected_user_id,
                        'match_id': m_id,
                        'pred_score_a': sa,
                        'pred_score_b': sb,
                        'pred_advanced_team_id': adv_id, 
                        'timestamp': (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d %H:%M:%S")
                    })
                
                if new_preds:
                    new_preds_df = pd.DataFrame(new_preds)
                    
                    ws_preds = sh.worksheet("predictions")
                    data_preds = ws_preds.get_all_values()
                    current_preds_df = pd.DataFrame(data_preds[1:], columns=data_preds[0]) if data_preds else pd.DataFrame()
                    current_preds_df.replace("", pd.NA, inplace=True)
                    
                    current_preds_df['match_id'] = current_preds_df['match_id'].astype(str)
                    current_preds_df['user_id'] = current_preds_df['user_id'].astype(str)
                    
                    if 'pred_advanced_team_id' not in current_preds_df.columns:
                        current_preds_df['pred_advanced_team_id'] = None
                    
                    valid_m_ids = [p['match_id'] for p in new_preds]
                    current_preds_df = current_preds_df[~((current_preds_df['user_id'] == selected_user_id) & (current_preds_df['match_id'].isin(valid_m_ids)))]
                    
                    final_preds_df = pd.concat([current_preds_df, new_preds_df], ignore_index=True)
                    ws_preds.clear()
                    final_preds_df = final_preds_df.astype(object).fillna("").replace(["nan", "NaN", "<NA>"], "")
                    set_with_dataframe(ws_preds, final_preds_df)
                
                for m_id in user_inputs.keys():
                    st.session_state.pop(f"pred_{selected_user_id}_{m_id}_a", None)
                    st.session_state.pop(f"pred_{selected_user_id}_{m_id}_b", None)
                    st.session_state.pop(f"adv_{selected_user_id}_{m_id}", None)
                
                st.session_state['chk_reset_counter'] += 1
                st.cache_data.clear()
                
                if ignored_matches:
                    st.session_state['success_msg_pred'] = "⚠️ Một số trận đấu đã bị khóa trước khi bạn kịp lưu. Các trận còn lại đã cập nhật!"
                else:
                    st.session_state['success_msg_pred'] = "🎉 Đã lưu dự đoán lên Cloud thành công!"
                    
                st.rerun()

with tab2:
    st.write(f"### Lịch sử dự đoán của: **{selected_user_name}**")
    user_history_df = preds_df[preds_df['user_id'] == selected_user_id].copy()
    
    if user_history_df.empty:
        st.info("Bạn chưa dự đoán trận nào.")
    else:
        display_history = pd.merge(user_history_df, matches_df, left_on='match_id', right_on='match_id', how='inner')
        
        display_history['match_number'] = pd.to_numeric(display_history['match_number'], errors='coerce')
        display_history = display_history.sort_values(by='match_number')
        
        display_history['Trận'] = display_history['match_number']
        display_history['Bảng/Vòng'] = display_history['match_label']
        
        def format_prediction(row):
            try:
                score_a = int(float(row['pred_score_a']))
                score_b = int(float(row['pred_score_b']))
            except (ValueError, TypeError):
                score_a, score_b = 0, 0
                
            base_pred = f"{row['team_a']}  {score_a} - {score_b}  {row['team_b']}"
            
            try: stage_id = int(float(row['stage_id']))
            except: stage_id = 1
            
            if stage_id > 1 and score_a == score_b:
                try:
                    adv_name = id_to_name.get(int(float(row['pred_advanced_team_id'])), "")
                    if adv_name: base_pred += f" (PEN: {adv_name})"
                except: pass
            return base_pred

        display_history['Dự Đoán Của Bạn'] = display_history.apply(format_prediction, axis=1)
        display_history['Thời Gian Ghi Nhận'] = display_history['timestamp']
        
        final_table = display_history[['Trận', 'Bảng/Vòng', 'Dự Đoán Của Bạn', 'Thời Gian Ghi Nhận']]
        st.dataframe(final_table, width="stretch", hide_index=True)