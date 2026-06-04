import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# 👉 Nhúng Component
from ui_components import apply_global_styles, custom_loader, sync_auth_session

st.set_page_config(page_title="Xem Lịch Thi Đấu", page_icon="🗓️", layout="wide")

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

st.markdown("""
    <h1 style='color: #4338CA; border-bottom: 3px solid #6366F1; padding-bottom: 10px;'>
        🏟️ FIXTURES & RESULTS (Lịch Thi Đấu)
    </h1>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["spreadsheet_id"])

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
    
    return matches_df

# 👉 Bọc hàm load data bằng Custom Loader
with custom_loader("Đang tải dữ liệu trận đấu..."):
    matches_df = load_matches_data()

st.markdown("Cập nhật kết quả các trận đấu trong khuôn khổ giải đấu. Các trận chưa diễn ra sẽ hiển thị mặc định là 0 - 0.")
st.divider()

def render_matches_ui(df, is_finished=False):
    if df.empty:
        st.info("Không có trận đấu nào trong danh sách này.")
        return
    
    for index, row in df.iterrows():
        team_a = row['team_a']
        team_b = row['team_b']
        group_label = row['match_label']
        
        try:
            score_a = int(float(row['real_score_a']))
            score_b = int(float(row['real_score_b']))
        except (ValueError, TypeError):
            score_a, score_b = 0, 0
        
        status_text = "✅ Đã có kết quả" if is_finished else "⏳ Chưa đá"
        status_color = "gray" if is_finished else "#EAB308" 
        
        with st.container():
            col_info, col_team_a, col_score, col_team_b, col_status = st.columns([1.5, 2, 1, 2, 1.5])
            with col_info:
                st.write(f"**Trận {row['match_number']}**")
                st.caption(f"Bảng/Vòng: {group_label}")
            with col_team_a:
                st.markdown(f"<h4 style='text-align: right; margin-top: 10px; color: #1E3A8A;'>{team_a}</h4>", unsafe_allow_html=True)
            with col_score:
                st.markdown(f"<h2 style='text-align: center; margin-top: 0px; color: #DC2626;'>{score_a} - {score_b}</h2>", unsafe_allow_html=True)
            with col_team_b:
                st.markdown(f"<h4 style='text-align: left; margin-top: 10px; color: #1E3A8A;'>{team_b}</h4>", unsafe_allow_html=True)
            with col_status:
                st.markdown(f"<p style='text-align: right; margin-top: 15px; font-weight: bold; color: {status_color};'>{status_text}</p>", unsafe_allow_html=True)
            st.write("---")

tab1, tab2 = st.tabs(["⚽ Các trận sắp tới", "✅ Các trận đã kết thúc"])

pending_matches = matches_df[matches_df['real_score_a'].isna() | matches_df['real_score_b'].isna()]
finished_matches = matches_df[matches_df['real_score_a'].notna() & matches_df['real_score_b'].notna()]

with tab1:
    render_matches_ui(pending_matches, is_finished=False)
with tab2:
    render_matches_ui(finished_matches, is_finished=True)