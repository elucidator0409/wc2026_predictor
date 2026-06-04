import streamlit as st
import contextlib
import os

def apply_global_styles():
    """Đọc file CSS và nhúng (inject) vào toàn bộ trang"""
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Không tìm thấy file assets/style.css")

@contextlib.contextmanager
def custom_loader(text="Đang xử lý dữ liệu..."):
    """
    Component Loader tuỳ chỉnh (Hoạt động như Context Manager).
    Chỉ hiện lên khi đang chạy tác vụ bên trong vòng 'with', sau đó tự động biến mất.
    """
    loader_placeholder = st.empty() # Tạo một vùng chứa tạm thời
    
    # Hiển thị UI Loader
    loader_placeholder.markdown(f"""
        <div class="custom-loader-wrapper">
            <div class="spinner"></div>
            <div class="loader-text">{text}</div>
        </div>
    """, unsafe_allow_html=True)
    
    try:
        # Tạm dừng UI để chạy code bên trong (ví dụ: load data)
        yield
    finally:
        # Code chạy xong thì xoá sạch vùng chứa này
        loader_placeholder.empty()


def sync_auth_session():
    """Đồng bộ trạng thái đăng nhập qua URL cho TẤT CẢ các trang"""
    # Khởi tạo biến nếu chưa có
    if 'authenticated_user_id' not in st.session_state:
        st.session_state['authenticated_user_id'] = None
        
    # Nếu bị mất session (F5) nhưng trên URL vẫn còn lưu vết tích user_id
    if st.session_state['authenticated_user_id'] is None and "user_id" in st.query_params:
        st.session_state['authenticated_user_id'] = st.query_params["user_id"]
        
    # Ngược lại, nếu đang có session thì luôn ghim nó lên URL để đề phòng F5
    if st.session_state['authenticated_user_id'] is not None:
        st.query_params["user_id"] = st.session_state['authenticated_user_id']