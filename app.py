import streamlit as st

from ui_components import (
    apply_global_styles,
    render_home_cta_cards,
    render_hero_home,
    render_sidebar,
    render_stat_cards,
    sync_auth_session,
)

st.set_page_config(
    page_title="World Cup 2026 Predictor",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

apply_global_styles()
sync_auth_session()
render_sidebar()

render_hero_home()

render_stat_cards([
    ("+3", "Điểm / đúng kết quả"),
    ("+1", "Điểm / đúng PEN"),
    ("10k", "Phạt / sai kết quả"),
    ("104", "Trận đấu WC 2026"),
])

st.markdown('<div class="section-title">📜 Thể lệ & luật chơi</div>', unsafe_allow_html=True)

st.markdown(
    """
    <div class="rule-grid">
        <div class="rule-card rule-card--points">
            <h3>🟢 Hệ thống tính điểm</h3>
            <ul>
                <li><strong>Đoán đúng kết quả</strong> (Đội A thắng / Hòa / Đội B thắng): +3 điểm</li>
                <li><strong>Vòng Knock-out</strong> (Đoán đúng đội đi tiếp (Hiệp phụ/Penalty) khi chọn Hòa): +1 điểm</li>
            </ul>
        </div>
        <div class="rule-card rule-card--fines">
            <h3>🔴 Quỹ phạt</h3>
            <ul>
                <li><strong>Đoán đúng kết quả:</strong> 0k</li>
                <li><strong>Đoán sai kết quả:</strong> đóng 10k vào quỹ</li>
                <li>Tổng phạt tự động tính sau khi có kết quả chính thức</li>
            </ul>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.markdown('<div class="section-title">🚀 Bắt đầu ngay</div>', unsafe_allow_html=True)
st.caption("Chọn nhanh khu vực bạn muốn vào. Sidebar vẫn luôn có sẵn nếu cần điều hướng chi tiết.")

render_home_cta_cards([
    {
        "href": "/Du_Doan",
        "icon": "✍️",
        "title": "Dự đoán ngay",
        "desc": "Chọn A thắng / Hòa / B thắng và chốt trước giờ bóng lăn.",
        "tone": "blue",
        "cta": "Vào dự đoán",
    },
    {
        "href": "/Xem_Lich_Thi_Dau",
        "icon": "🗓️",
        "title": "Xem lịch thi đấu",
        "desc": "Tra cứu 104 trận, đội tham gia, bảng đấu và kết quả.",
        "tone": "green",
        "cta": "Xem lịch",
    },
    {
        "href": "/Tra_Cuu_Doi_Bong",
        "icon": "👕",
        "title": "Tra cứu đội hình",
        "desc": "48 đội, 26 cầu thủ — caps, bàn thắng, CLB trước khi dự đoán.",
        "tone": "green",
        "cta": "Xem đội hình",
    },
    {
        "href": "/Bang_Xep_Hang",
        "icon": "🏆",
        "title": "Bảng xếp hạng",
        "desc": "Theo dõi điểm số, quỹ phạt và phong cách dự đoán.",
        "tone": "gold",
        "cta": "Xem BXH",
    },
    {
        "href": "/Lich_Thi_Dau",
        "icon": "⚙️",
        "title": "Góc của Elu",
        "desc": "Cập nhật kết quả, khóa trận và quản trị vòng đấu.",
        "tone": "purple",
        "cta": "Admin",
    },
])
