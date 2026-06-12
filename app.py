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


def render_home_rules_section():
    st.html(
        """
<section class="home-rules" aria-labelledby="home-rules-title">
  <div class="home-section-heading">
    <span class="home-section-kicker">Luật chơi</span>
    <h2 id="home-rules-title">Thể lệ & cách tính quỹ</h2>
  </div>
  <div class="rule-grid">
    <article class="rule-card rule-card--points">
      <div class="rule-card-top">
        <span class="rule-card-icon" aria-hidden="true">+</span>
        <div>
          <h3>Hệ thống tính điểm</h3>
          <p>Chấm theo kết quả chính, cộng thêm cho knock-out.</p>
        </div>
      </div>
      <ul class="rule-list">
        <li>
          <span class="rule-value">+3</span>
          <span><strong>Đúng kết quả</strong><small>Đội A thắng, hòa, hoặc đội B thắng.</small></span>
        </li>
        <li>
          <span class="rule-value">+1</span>
          <span><strong>Đúng đội đi tiếp</strong><small>Áp dụng vòng knock-out khi chọn hòa sau 90 phút.</small></span>
        </li>
      </ul>
    </article>
    <article class="rule-card rule-card--fines">
      <div class="rule-card-top">
        <span class="rule-card-icon" aria-hidden="true">!</span>
        <div>
          <h3>Quỹ phạt</h3>
          <p>Phạt theo kết quả chính thức sau khi trận khép lại.</p>
        </div>
      </div>
      <ul class="rule-list">
        <li>
          <span class="rule-value">0k</span>
          <span><strong>Đúng kết quả</strong><small>Không đóng thêm vào quỹ.</small></span>
        </li>
        <li>
          <span class="rule-value">10k</span>
          <span><strong>Sai kết quả</strong><small>Tự động cộng vào tổng phạt của người chơi.</small></span>
        </li>
      </ul>
    </article>
  </div>
</section>
        """
    )


render_hero_home()

render_stat_cards([
    ("+3", "Điểm / đúng kết quả"),
    ("+1", "Điểm / đúng PEN"),
    ("10k", "Phạt / sai kết quả"),
    ("104", "Trận đấu WC 2026"),
])

render_home_rules_section()

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
