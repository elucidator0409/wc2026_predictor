import streamlit as st

from ui_components import (
    apply_global_styles,
    render_hero_home,
    render_sidebar,
    render_stat_cards,
    sync_auth_session,
)

st.set_page_config(
    page_title="World Cup 2026 Predictor",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_global_styles()
sync_auth_session()
render_sidebar()

render_hero_home()

render_stat_cards([
    ("3", "Điểm / đúng tỉ số"),
    ("1", "Điểm / đúng kết quả"),
    ("10k", "Phạt / đoán sai đội thắng"),
    ("104", "Trận đấu WC 2026"),
])

st.markdown('<div class="section-title">📜 Thể lệ & luật chơi</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="rule-grid">
        <div class="rule-card rule-card--points">
            <h3>🟢 Hệ thống tính điểm</h3>
            <ul>
                <li><strong>Đoán đúng tỉ số:</strong> +3 điểm</li>
                <li><strong>Đoán đúng kết quả</strong> (Thắng/Thua/Hòa): +1 điểm</li>
                <li><strong>Knock-out (Penalty):</strong> Đoán đúng đội thắng luân lưu khi hòa: +1 điểm</li>
            </ul>
        </div>
        <div class="rule-card rule-card--fines">
            <h3>🔴 Quỹ phạt</h3>
            <ul>
                <li><strong>Đoán đúng đội thắng / đi tiếp:</strong> 0k</li>
                <li><strong>Đoán sai đội thắng / đi tiếp:</strong> đóng 10k vào quỹ</li>
                <li>Tổng phạt tự động tính sau khi có kết quả chính thức</li>
            </ul>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">🚀 Bắt đầu ngay</div>', unsafe_allow_html=True)
st.caption("Chọn trang bên sidebar hoặc dùng phím tắt bên dưới:")

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.page_link("pages/1_Du_Doan.py", label="Dự đoán", icon="✍️", width="stretch")
with c2:
    st.page_link("pages/3_Bang_Xep_Hang.py", label="Bảng xếp hạng", icon="🥇", width="stretch")
with c3:
    st.page_link("pages/4_Xem_Lich_Thi_Dau.py", label="Lịch thi đấu", icon="🗓️", width="stretch")
with c4:
    st.page_link("pages/2_Lich_Thi_Dau.py", label="Admin", icon="⚙️", width="stretch")
