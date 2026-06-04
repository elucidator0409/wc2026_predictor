import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from google.oauth2.service_account import Credentials

from ui_components import apply_global_styles, custom_loader, sync_auth_session

st.set_page_config(page_title="Bảng Xếp Hạng & Phân Tích", page_icon="🏆", layout="wide")

# 👉 Gọi Global CSS
apply_global_styles()
sync_auth_session()

# 👉 Giữ nguyên Sidebar Menu gốc của bạn
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
    <h1 style='text-align: center; color: #047857; border-bottom: 3px solid #10B981; padding-bottom: 10px;'>
        🏆 BẢNG VÀNG 
    </h1>
""", unsafe_allow_html=True)

@st.cache_resource
def init_connection():
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["spreadsheet_id"])

@st.cache_data(ttl=300, show_spinner=False)
def load_data_for_ranking():
    sh = init_connection()
    
    def read_safe(sheet_name):
        data = sh.worksheet(sheet_name).get_all_values()
        if not data: return pd.DataFrame()
        return pd.DataFrame(data[1:], columns=data[0])
        
    users_df = read_safe("users")
    preds_df = read_safe("predictions")
    matches_df = read_safe("matches")
    teams_df = read_safe("teams")
    
    users_df.replace("", pd.NA, inplace=True)
    preds_df.replace("", pd.NA, inplace=True)
    matches_df.replace("", pd.NA, inplace=True)
    
    if 'pred_advanced_team_id' not in preds_df.columns:
        preds_df['pred_advanced_team_id'] = None
    if 'real_advanced_team_id' not in matches_df.columns:
        matches_df['real_advanced_team_id'] = None
        
    return users_df, preds_df, matches_df, teams_df

with custom_loader("Đang thống kê điểm số và quỹ phạt..."):
    users_df, preds_df, matches_df, teams_df = load_data_for_ranking()

id_to_name = {str(row['id']): row['team_name'] for _, row in teams_df.iterrows()}

if 'real_score_a' not in matches_df.columns or 'real_score_b' not in matches_df.columns:
    st.info("Chưa có trận đấu nào được cập nhật kết quả. Bảng xếp hạng sẽ xuất hiện khi có kết quả đầu tiên!")
    st.stop()

id_col = 'id' if 'id' in matches_df.columns else 'match_id'
finished_matches = matches_df[matches_df['real_score_a'].notna() & matches_df['real_score_b'].notna()].copy()

preds_df['match_id'] = preds_df['match_id'].astype(str)
finished_matches[id_col] = finished_matches[id_col].astype(str)

merged_df = pd.merge(preds_df, finished_matches, left_on='match_id', right_on=id_col, how='inner')

# ==========================================
# LOGIC TÍNH ĐIỂM (GIỮ NGUYÊN 100%)
# ==========================================
def calculate_points(row):
    try:
        pred_a, pred_b = int(float(row['pred_score_a'])), int(float(row['pred_score_b']))
        real_a, real_b = int(float(row['real_score_a'])), int(float(row['real_score_b']))
    except (ValueError, TypeError): return 0
    
    points = 0
    if pred_a == real_a and pred_b == real_b: points += 3
    else:
        pred_diff, real_diff = pred_a - pred_b, real_a - real_b
        if (pred_diff > 0 and real_diff > 0) or (pred_diff < 0 and real_diff < 0) or (pred_diff == 0 and real_diff == 0):
            points += 1
            
    try: stage = int(float(row.get('stage_id', 1)))
    except: stage = 1
        
    if stage > 1 and real_a == real_b and pred_a == pred_b:
        pred_adv = row.get('pred_advanced_team_id')
        real_adv = row.get('real_advanced_team_id')
        try:
            if pd.notna(pred_adv) and pd.notna(real_adv) and str(int(float(pred_adv))) == str(int(float(real_adv))):
                points += 1
        except Exception: pass
    return points

# ==========================================
# NEW FEAT: LOGIC TÍNH TIỀN PHẠT ĐOÁN SAI ĐỘI THẮNG
# ==========================================
def calculate_fines(row):
    try:
        pred_a, pred_b = int(float(row['pred_score_a'])), int(float(row['pred_score_b']))
        real_a, real_b = int(float(row['real_score_a'])), int(float(row['real_score_b']))
        try: stage = int(float(row.get('stage_id', 1)))
        except: stage = 1
    except (ValueError, TypeError): 
        return 10  # Mặc định phạt nếu dữ liệu lỗi
        
    def clean_id(val):
        if pd.isna(val) or str(val).strip() == "": return ""
        try: return str(int(float(val)))
        except: return str(val).strip()

    home_id = clean_id(row.get('home_team_id'))
    away_id = clean_id(row.get('away_team_id'))
    
    # 1. Xác định Đội Thắng Thực Tế (Real Winner)
    if real_a > real_b:
        real_winner = home_id
    elif real_a < real_b:
        real_winner = away_id
    else:
        real_winner = clean_id(row.get('real_advanced_team_id')) if stage > 1 else 'DRAW'
        
    # 2. Xác định Đội Thắng Dự Đoán (Predicted Winner)
    if pred_a > pred_b:
        pred_winner = home_id
    elif pred_a < pred_b:
        pred_winner = away_id
    else:
        pred_winner = clean_id(row.get('pred_advanced_team_id')) if stage > 1 else 'DRAW'
        
    # 3. Đối chiếu so sánh kết quả xu hướng
    if pred_winner == real_winner and real_winner != "":
        return 0  # Đoán đúng đội thắng/đi tiếp -> Không bị phạt
    return 10     # Đoán sai -> Phạt 10k

if not merged_df.empty:
    merged_df['points'] = merged_df.apply(calculate_points, axis=1)
    merged_df['fines'] = merged_df.apply(calculate_fines, axis=1) # Tính tiền phạt cho từng trận
    
    merged_df['points'] = pd.to_numeric(merged_df['points'], errors='coerce').fillna(0).astype(int)
    merged_df['fines'] = pd.to_numeric(merged_df['fines'], errors='coerce').fillna(0).astype(int)
    merged_df['user_id'] = merged_df['user_id'].astype(str)
    
    # ------------------------------------------
    # CHUẨN BỊ DỮ LIỆU PHÂN TÍCH (ANALYTICS)
    # ------------------------------------------
    def get_outcome(a, b):
        try:
            a, b = float(a), float(b)
            if a > b: return 'Win_A'
            elif a < b: return 'Win_B'
            else: return 'Draw'
        except: return 'Unknown'

    preds_df['outcome'] = preds_df.apply(lambda r: get_outcome(r['pred_score_a'], r['pred_score_b']), axis=1)
    consensus = preds_df.groupby(['match_id', 'outcome']).size().reset_index(name='picks')
    total_picks = preds_df.groupby('match_id').size().reset_index(name='total')
    consensus = pd.merge(consensus, total_picks, on='match_id')
    consensus['pick_ratio'] = consensus['picks'] / consensus['total']
    
    consensus['is_maverick'] = consensus['pick_ratio'] <= 0.3
    preds_analytics = pd.merge(preds_df, consensus[['match_id', 'outcome', 'is_maverick']], on=['match_id', 'outcome'], how='left')
    
    maverick_stats = preds_analytics.groupby('user_id', as_index=False)['is_maverick'].sum().rename(columns={'is_maverick': 'Maverick Picks'})
    exact_score_stats = merged_df[merged_df['points'] >= 3].groupby('user_id', as_index=False).size().rename(columns={'size': 'Exact Scores'})
    total_played_stats = merged_df.groupby('user_id', as_index=False).size().rename(columns={'size': 'Total Played'})

    # ------------------------------------------
    # GIAO DIỆN TABS
    # ------------------------------------------
    tab1, tab2 = st.tabs(["🥇 Bảng Điểm & Quỹ Phạt", "🧠 Phân Tích Phong Cách"])
    
    with tab1:
        # Tính tổng điểm và tổng tiền phạt gom theo từng người
        leaderboard_pts = merged_df.groupby('user_id', as_index=False)['points'].sum()
        leaderboard_fines = merged_df.groupby('user_id', as_index=False)['fines'].sum()
        
        leaderboard = pd.merge(users_df, leaderboard_pts, on='user_id', how='left')
        leaderboard = pd.merge(leaderboard, leaderboard_fines, on='user_id', how='left')
        
        leaderboard['points'] = leaderboard['points'].fillna(0).astype(int)
        leaderboard['fines'] = leaderboard['fines'].fillna(0).astype(int)
        
        # Xếp hạng: Ưu tiên điểm cao lên trước, nếu bằng điểm ai ít tiền phạt hơn xếp trên
        leaderboard = leaderboard.sort_values(by=['points', 'fines'], ascending=[False, True]).reset_index(drop=True)
        leaderboard['Hạng'] = leaderboard.index + 1
        
        # Đưa tiền phạt (k) trực tiếp lên bảng vàng thành tích
        display_df = leaderboard[['Hạng', 'name', 'points', 'fines']].rename(
            columns={'name': 'Người Chơi', 'points': 'Tổng Điểm', 'fines': 'Tiền Phạt (k)'}
        )
        
        col1, col2 = st.columns([1.2, 1.3])
        with col1: 
            dynamic_height = (len(display_df) + 1) * 35 + 40
            st.dataframe(display_df, width="stretch", hide_index=True, height=dynamic_height)
        with col2:
            if not display_df.empty and display_df['Tổng Điểm'].sum() > 0:
                fig = px.bar(
                    display_df.sort_values('Tổng Điểm', ascending=True), 
                    y='Người Chơi', x='Tổng Điểm', text='Tổng Điểm',
                    orientation='h', color='Tổng Điểm', color_continuous_scale='Blues'
                )
                fig.update_traces(textposition='outside')
                fig.update_layout(showlegend=False, xaxis_title="Điểm số", yaxis_title="", margin=dict(l=0, r=0, t=0, b=0))
                st.plotly_chart(fig, width="stretch")
            else:
                st.info("Chưa có dữ liệu đồ thị.")
            
        st.divider()
        with st.expander("🔍 Chi tiết lịch sử chấm điểm & Tiền phạt từng trận"):
            detail_df = pd.merge(merged_df, users_df[['user_id', 'name']], on='user_id', how='left')
            detail_df = pd.merge(detail_df, teams_df[['id', 'team_name']], left_on='home_team_id', right_on='id', how='left').rename(columns={'team_name': 'Team A'})
            detail_df = pd.merge(detail_df, teams_df[['id', 'team_name']], left_on='away_team_id', right_on='id', how='left').rename(columns={'team_name': 'Team B'})
            
            def format_score(row, prefix="real"):
                try:
                    score_a, score_b = int(float(row[f'{prefix}_score_a'])), int(float(row[f'{prefix}_score_b']))
                except:
                    score_a, score_b = 0, 0
                base = f"{score_a} - {score_b}"
                try: stage = int(float(row.get('stage_id', 1)))
                except: stage = 1
                if stage > 1 and score_a == score_b:
                    adv_id = row.get(f'{prefix}_advanced_team_id')
                    if pd.notna(adv_id) and str(adv_id).strip() != "":
                        adv_name = id_to_name.get(str(int(float(adv_id))), "")
                        if adv_name: base += f" (PEN: {adv_name})"
                return base

            detail_df['Kết Quả Thực Tế'] = detail_df.apply(lambda r: format_score(r, 'real'), axis=1)
            detail_df['Dự Đoán'] = detail_df.apply(lambda r: format_score(r, 'pred'), axis=1)
            detail_df['Trận'] = detail_df.apply(lambda r: f"T{r['match_number']}: {r['Team A']} vs {r['Team B']}", axis=1)
            
            # Thêm cột Tiền Phạt vào bảng log chi tiết
            final_detail = detail_df[['name', 'Trận', 'Dự Đoán', 'Kết Quả Thực Tế', 'points', 'fines']]
            final_detail.columns = ['Người Chơi', 'Trận Đấu', 'Dự Đoán Của Bạn', 'Kết Quả Thực Tế', 'Điểm Số', 'Tiền Phạt (k)']
            st.dataframe(final_detail.sort_values(by=['Trận Đấu', 'Người Chơi']), width="stretch", hide_index=True)

    with tab2:
        st.write("### 🧬 Hồ Sơ Dữ Liệu Người Chơi")
        analytics_df = pd.merge(users_df, total_played_stats, on='user_id', how='left').fillna(0)
        analytics_df = pd.merge(analytics_df, exact_score_stats, on='user_id', how='left').fillna(0)
        analytics_df = pd.merge(analytics_df, maverick_stats, on='user_id', how='left').fillna(0)
        analytics_df['Hit Rate (%)'] = (analytics_df['Exact Scores'] / analytics_df['Total Played'] * 100).fillna(0).round(1)
        
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.markdown("**🎯 Top Tỉ Lệ Bàn Tay Vàng (Đoán trúng y xì tỉ số)**")
            st.caption("Khả năng đọc trận đấu cực cao thay vì chỉ đoán bừa kết quả.")
            if analytics_df['Total Played'].sum() > 0:
                fig1 = px.scatter(
                    analytics_df[analytics_df['Total Played'] > 0], 
                    x='Hit Rate (%)', y='name', size='Exact Scores', color='Hit Rate (%)',
                    hover_name='name', color_continuous_scale='Greens'
                )
                fig1.update_layout(yaxis_title="", xaxis_title="Tỉ lệ trúng tỉ số (%)")
                st.plotly_chart(fig1, width="stretch")
            else:
                st.info("Chưa có đủ dữ liệu để vẽ biểu đồ.")
            
        with col_chart2:
            st.markdown("**🐺 Top Maverick (Săn Kèo Đi Ngược Đám Đông)**")
            st.caption("Số lần chọn kết quả mà dưới 30% người chơi khác dám chọn.")
            if analytics_df['Maverick Picks'].sum() > 0:
                fig2 = px.bar(
                    analytics_df.sort_values('Maverick Picks', ascending=True), 
                    x='Maverick Picks', y='name', text='Maverick Picks',
                    orientation='h', color='Maverick Picks', color_continuous_scale='Oranges'
                )
                fig2.update_traces(textposition='outside')
                fig2.update_layout(yaxis_title="", xaxis_title="Số lần bẻ lái")
                st.plotly_chart(fig2, width="stretch")
            else:
                st.info("Chưa có đủ dữ liệu để vẽ biểu đồ.")
else:
    st.info("Chưa có ai dự đoán trúng các trận đã đá (hoặc chưa có dữ liệu kết quả).")