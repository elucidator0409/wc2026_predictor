import streamlit as st

# 👉 Import Người gác cổng & CSS tập trung
from ui_components import apply_global_styles, sync_auth_session

# 1. Cấu hình trang gốc (Áp dụng cho toàn bộ app)
st.set_page_config(
    page_title="World Cup 2026 Predictor",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 👉 Kích hoạt giao diện sạch & Giữ trạng thái đăng nhập
apply_global_styles()
sync_auth_session()
   
# Thêm chữ/hình ảnh vào đầu Sidebar
with st.sidebar:
    st.markdown("### 📌 MENU CHÍNH")
    st.page_link("app.py", label="Trang chủ", icon="🏠")
    st.page_link("pages/1_Du_Doan.py", label="Khu Vực Dự Đoán", icon="✍️")
    st.page_link("pages/3_Bang_Xep_Hang.py", label="Bảng Xếp Hạng", icon="🏆")
    st.page_link("pages/4_Xem_Lich_Thi_Dau.py", label="Lịch Thi Đấu", icon="🗓️")
    
    st.markdown("### 🔒 DÀNH CHO ADMIN")
    st.page_link("pages/2_Lich_Thi_Dau.py", label="Quản Trị Kết Quả", icon="⚙️")
    st.info("💡 Mẹo: Nhớ chốt đơn trước giờ bóng lăn nhé!")

# 2. Nhúng CSS Custom CHỈ dành riêng cho Hero Banner (Phần ẩn UI đã giao cho file CSS ngoài)
st.markdown("""
    <style>
        .hero-container {
            background: linear-gradient(135deg, #0f2027, #203a43, #2c5364);
            padding: 3rem 2rem;
            border-radius: 15px;
            text-align: center;
            color: white;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
            margin-bottom: 2rem;
        }
        .hero-title {
            font-size: 3.5rem;
            font-weight: 900;
            margin-bottom: 1rem;
            letter-spacing: 1px;
            text-transform: uppercase;
        }
        .highlight {
            color: #fbbf24; /* Màu vàng Gold */
        }
    </style>
""", unsafe_allow_html=True)

# 3. Hero Banner
st.markdown("""
    <div class="hero-container">
        <div class="hero-title">🏆 <span class="highlight">World Cup 2026</span> Predictor</div>
        <div style="font-size: 1.2rem; font-weight: 300; opacity: 0.9;">Hệ thống dự đoán bóng đá chuyên nghiệp</div>
    </div>
""", unsafe_allow_html=True)


# 4. Thể lệ & Cách tính điểm (CẬP NHẬT LUẬT MỚI)
st.write("## 📜 Thể Lệ & Luật Chơi")

col_rule1, col_rule2 = st.columns(2)

with col_rule1:
    st.markdown("""
    ### 🟢 HỆ THỐNG TÍNH ĐIỂM
    Luật nhà làm :
    * 🥇 **Đoán đúng tỉ số :** Nhận ngay **3 Điểm**.
    * 🥈 **Đoán đúng kết quả (Thắng/Thua/Hòa):** Nhận **1 Điểm** .
    * 🥅 **Luật Knock-out (Penalty):** Nếu trận đấu hòa, đoán đúng đội chiến thắng trong loạt luân lưu: Nhận thêm **1 Điểm**.
    """)

with col_rule2:
    st.markdown("""
    ### 🔴 ĐÓNG QUỸ
    Tổng phát sẽ tự động tính toán sau tiếng còi mãn cuộc:
    * ✅ **Đoán đúng đội thắng / đi tiếp:** Phạt **0k** .
    * ❌ **Đoán sai đội thắng / đi tiếp:** Đóng **10k** vào quỹ.
    """)

st.write("---")

# 5. Điều hướng nhanh (Call-to-Action)
st.write("## 🚀 Ready")
st.write("Sử dụng thanh menu bên trái để điều hướng, hoặc bấm vào các phím tắt dưới đây:")

# Nút bấm liên kết thẳng đến các trang
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.page_link("pages/1_Du_Doan.py", label="Tới Khu Vực Dự Đoán", icon="✍️")
with c2:
    st.page_link("pages/3_Bang_Xep_Hang.py", label="Xem Bảng Xếp Hạng", icon="🥇")
with c3:
    st.page_link("pages/4_Xem_Lich_Thi_Dau.py", label="Xem Lịch Thi Đấu", icon="🗓️")
with c4:
    st.page_link("pages/2_Lich_Thi_Dau.py", label="Khu Vực Admin", icon="⚙️")