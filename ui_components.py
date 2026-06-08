import contextlib
import html
import os
import re

import streamlit as st

DISPLAY_NAME_EMOJIS = [
    "⚽", "🏆", "🔥", "⭐", "🎯", "💪", "😎", "👑",
    "🦁", "🐯", "🦅", "🍺", "🎉", "❤️", "💙", "💚",
    "🤙", "✌️", "🥇", "🎮", "🧢", "🌟", "⚡", "🍀",
]


def _html(content: str):
    """Render raw HTML without Markdown interpreting indented blocks as code."""
    st.html(content)


def apply_global_styles():
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Không tìm thấy file assets/style.css")


@contextlib.contextmanager
def custom_loader(text="Đang xử lý dữ liệu..."):
    loader_placeholder = st.empty()
    loader_placeholder.markdown(
        f'<div class="custom-loader-wrapper">'
        f'<div class="spinner"></div>'
        f'<div class="loader-text">{html.escape(text)}</div>'
        f"</div>",
        unsafe_allow_html=True,
    )
    try:
        yield
    finally:
        loader_placeholder.empty()


def sync_auth_session():
    if "authenticated_user_id" not in st.session_state:
        st.session_state["authenticated_user_id"] = None

    if st.session_state["authenticated_user_id"] is None and "user_id" in st.query_params:
        st.session_state["authenticated_user_id"] = st.query_params["user_id"]

    if st.session_state["authenticated_user_id"] is not None:
        st.query_params["user_id"] = st.session_state["authenticated_user_id"]


def render_sidebar():
    with st.sidebar:
        _html(
            '<div class="sidebar-brand">'
            '<div class="sidebar-brand-icon">🏆</div>'
            '<div class="sidebar-brand-title">WC 2026</div>'
            '<div class="sidebar-brand-sub">Predictor Platform</div>'
            "</div>"
        )
        st.markdown("### 📌 Menu chính")
        st.page_link("app.py", label="Trang chủ", icon="🏠")
        st.page_link("pages/1_Du_Doan.py", label="Khu vực dự đoán", icon="✍️")
        st.page_link("pages/3_Bang_Xep_Hang.py", label="Bảng xếp hạng", icon="🏆")
        st.page_link("pages/4_Xem_Lich_Thi_Dau.py", label="Lịch thi đấu", icon="🗓️")

        st.markdown("### 🔒 Admin")
        st.page_link("pages/2_Lich_Thi_Dau.py", label="Quản trị kết quả", icon="⚙️")

        _html(
            '<div class="sidebar-tip">'
            "💡 Nhớ chốt dự đoán trước giờ bóng lăn để không bị khóa!"
            "</div>"
        )


def render_page_header(title, subtitle="", variant="default", eyebrow=""):
    variant_class = f"page-header--{variant}" if variant != "default" else ""
    eyebrow_html = (
        f'<div class="page-header-eyebrow">{html.escape(eyebrow)}</div>' if eyebrow else ""
    )
    subtitle_html = (
        f'<p class="page-header-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
    )
    _html(
        f'<div class="page-header {variant_class}">'
        f'<div class="page-header-inner">'
        f"{eyebrow_html}"
        f'<h1 class="page-header-title">{html.escape(title)}</h1>'
        f"{subtitle_html}"
        f"</div></div>"
    )


def render_hero_home():
    _html(
        '<div class="page-header page-header--home">'
        '<div class="page-header-inner">'
        '<div class="page-header-eyebrow">FIFA World Cup · USA · Canada · Mexico</div>'
        '<h1 class="page-header-title">🏆 <span class="highlight">World Cup 2026</span> Predictor</h1>'
        '<p class="page-header-subtitle">Hệ thống dự đoán bóng đá chuyên nghiệp — cùng tranh tài, cùng vui!</p>'
        "</div></div>"
    )


def render_stat_cards(stats: list[tuple[str, str, str]]):
    """stats: list of (value, label, optional icon)"""
    cards = []
    for item in stats:
        value, label = item[0], item[1]
        icon = item[2] if len(item) > 2 else ""
        cards.append(
            f'<div class="stat-card">'
            f'<div class="stat-card-value">{html.escape(str(icon))} {html.escape(str(value))}</div>'
            f'<div class="stat-card-label">{html.escape(label)}</div>'
            f"</div>"
        )
    _html(f'<div class="stats-row">{"".join(cards)}</div>')


def render_match_card(match_number, group_label, team_a, team_b, score_a, score_b, is_finished=False):
    status_class = "match-card-status--done" if is_finished else "match-card-status--pending"
    status_text = "✅ Kết thúc" if is_finished else "⏳ Sắp đá"
    _html(
        f'<div class="match-card">'
        f'<div class="match-card-meta">'
        f'<div class="match-card-number">Trận {html.escape(str(match_number))}</div>'
        f'<div class="match-card-group">{html.escape(str(group_label))}</div>'
        f"</div>"
        f'<div class="match-card-team match-card-team--home">{html.escape(str(team_a))}</div>'
        f'<div class="match-card-score">{score_a} – {score_b}</div>'
        f'<div class="match-card-team match-card-team--away">{html.escape(str(team_b))}</div>'
        f'<div class="match-card-status {status_class}">{status_text}</div>'
        f"</div>"
    )


def render_podium(top3: list[tuple[str, int]]):
    """top3: list of (name, points) for ranks 1-3 in rank order."""
    if not top3:
        return

    medals = ["🥇", "🥈", "🥉"]
    bars = ["1", "2", "3"]
    order = [1, 0, 2] if len(top3) >= 3 else list(range(len(top3)))

    items = []
    for idx in order:
        if idx >= len(top3):
            continue
        name, pts = top3[idx]
        items.append(
            f'<div class="podium-item">'
            f'<div class="podium-bar podium-bar--{bars[idx]}">{medals[idx]}</div>'
            f'<div class="podium-name">{html.escape(str(name))}</div>'
            f'<div class="podium-pts">{pts} điểm</div>'
            f"</div>"
        )
    _html(f'<div class="podium">{"".join(items)}</div>')


def render_login_card(title="Đăng nhập", subtitle="Nhập thông tin để tham gia dự đoán"):
    _html(
        f'<div class="login-card">'
        f'<div class="login-card-title">{html.escape(title)}</div>'
        f'<div class="login-card-sub">{html.escape(subtitle)}</div>'
        f"</div>"
    )


def get_user_avatar_display(user_name: str, avatar_icon: str | None = None) -> str:
    """Show avatar char: saved icon > leading emoji in name > first letter."""
    if avatar_icon and str(avatar_icon).strip():
        return str(avatar_icon).strip()[:2]
    match = re.match(r"^[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", user_name or "")
    if match:
        return match.group(0)[:2]
    clean = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", "", user_name or "").strip()
    if clean:
        return clean[0].upper()
    return "?"


def init_name_draft(user_id: str, current_name: str) -> str:
    draft_key = f"name_draft_{user_id}"
    if draft_key not in st.session_state:
        st.session_state[draft_key] = current_name
    return draft_key


def render_emoji_name_picker(draft_key: str, original_name: str):
    """Quick-pick emojis to decorate display name."""
    _html(
        '<div class="emoji-picker-box">'
        '<div class="emoji-picker-label">Chọn icon để thêm vào tên</div>'
        "</div>"
    )

    row_size = 6
    for row_start in range(0, len(DISPLAY_NAME_EMOJIS), row_size):
        row = DISPLAY_NAME_EMOJIS[row_start : row_start + row_size]
        cols = st.columns(row_size, gap="small")
        for col_idx, emoji in enumerate(row):
            with cols[col_idx]:
                if st.button(
                    emoji,
                    key=f"emoji_btn_{draft_key}_{row_start + col_idx}",
                    width="stretch",
                    help=f"Thêm {emoji}",
                ):
                    st.session_state[draft_key] = st.session_state.get(draft_key, original_name) + emoji
                    st.rerun()

    _html('<div class="emoji-action-row-marker"></div>')
    btn1, btn2, btn3 = st.columns(3, gap="small")
    with btn1:
        if st.button("⌫ Xóa", key=f"emoji_back_{draft_key}", width="stretch"):
            st.session_state[draft_key] = st.session_state.get(draft_key, "")[:-1]
            st.rerun()
    with btn2:
        if st.button("↩️ Reset", key=f"emoji_reset_{draft_key}", width="stretch"):
            st.session_state[draft_key] = original_name
            st.rerun()
    with btn3:
        if st.button("🧹 Icon", key=f"emoji_clear_{draft_key}", width="stretch"):
            st.session_state[draft_key] = re.sub(
                r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+",
                "",
                st.session_state.get(draft_key, original_name),
            ).strip() or original_name
            st.rerun()

    preview = st.session_state.get(draft_key, original_name)
    _html(
        f'<div class="name-preview">'
        f'<span class="name-preview-label">Xem trước</span>'
        f'<span class="name-preview-value">{html.escape(preview)}</span>'
        f"</div>"
    )


def render_user_account_panel(
    user_id: str,
    user_name: str,
    user_names: list[str],
    stored_password_hash: str,
    hash_password_fn,
    init_connection_fn,
    set_with_dataframe_fn,
    pd_module,
):
    """Sidebar account block: rename (with emoji), password, logout."""
    avatar_char = get_user_avatar_display(user_name)
    _html(
        f'<div class="account-panel">'
        f'<div class="account-panel-header">'
        f'<div class="account-avatar" title="Icon hiển thị từ tên">{html.escape(avatar_char)}</div>'
        f'<div class="account-meta">'
        f'<div class="account-label">Đang đăng nhập</div>'
        f'<div class="account-name">{html.escape(user_name)}</div>'
        f'<div class="account-hint">Icon lấy từ emoji trong tên hiển thị</div>'
        f"</div></div></div>"
    )

    draft_key = init_name_draft(user_id, user_name)

    with st.expander("📝 Đổi tên hiển thị", expanded=False):
        render_emoji_name_picker(draft_key, user_name)
        with st.form("change_name_form"):
            new_name = st.text_input(
                "Tên hiển thị mới:",
                value=st.session_state[draft_key],
                help="Gõ tên hoặc chọn icon phía trên — emoji sẽ được thêm vào tên.",
            )
            submit_name = st.form_submit_button("Cập nhật tên", width="stretch")
            if submit_name:
                new_name_clean = new_name.strip()
                st.session_state[draft_key] = new_name_clean
                if not new_name_clean:
                    st.error("❌ Tên không được để trống!")
                elif new_name_clean == user_name:
                    st.warning("⚠️ Tên mới giống hệt tên cũ.")
                elif new_name_clean in user_names:
                    st.error("❌ Tên này đã có người sử dụng!")
                else:
                    sh = init_connection_fn()
                    ws_users = sh.worksheet("users")
                    data_users = ws_users.get_all_values()
                    fresh_users_df = (
                        pd_module.DataFrame(data_users[1:], columns=data_users[0])
                        if data_users
                        else pd_module.DataFrame()
                    )
                    fresh_users_df.replace("", pd_module.NA, inplace=True)
                    fresh_users_df["user_id"] = fresh_users_df["user_id"].astype(str)
                    fresh_users_df.loc[fresh_users_df["user_id"] == user_id, "name"] = new_name_clean
                    ws_users.clear()
                    fresh_users_df = (
                        fresh_users_df.astype(object)
                        .fillna("")
                        .replace(["nan", "NaN", "<NA>"], "")
                    )
                    set_with_dataframe_fn(ws_users, fresh_users_df)
                    st.cache_data.clear()
                    st.session_state[draft_key] = new_name_clean
                    st.success("✅ Đổi tên thành công!")
                    st.rerun()

    with st.expander("🔑 Đổi mật khẩu", expanded=False):
        with st.form("change_password_form"):
            old_pass = st.text_input("Mật khẩu hiện tại", type="password")
            new_pass = st.text_input("Mật khẩu mới", type="password")
            confirm_pass = st.text_input("Xác nhận mật khẩu mới", type="password")
            submit_change = st.form_submit_button("Cập nhật mật khẩu", width="stretch")
            if submit_change:
                if hash_password_fn(old_pass) != stored_password_hash and old_pass != stored_password_hash:
                    st.error("❌ Mật khẩu hiện tại không đúng!")
                elif new_pass != confirm_pass:
                    st.error("❌ Mật khẩu mới không khớp nhau!")
                elif len(new_pass) < 4:
                    st.error("⚠️ Mật khẩu phải có ít nhất 4 ký tự.")
                else:
                    sh = init_connection_fn()
                    ws_users = sh.worksheet("users")
                    data_users = ws_users.get_all_values()
                    fresh_users_df = (
                        pd_module.DataFrame(data_users[1:], columns=data_users[0])
                        if data_users
                        else pd_module.DataFrame()
                    )
                    fresh_users_df.replace("", pd_module.NA, inplace=True)
                    fresh_users_df["user_id"] = fresh_users_df["user_id"].astype(str)
                    fresh_users_df["password"] = fresh_users_df["password"].astype(str)
                    fresh_users_df.loc[fresh_users_df["user_id"] == user_id, "password"] = hash_password_fn(new_pass)
                    ws_users.clear()
                    fresh_users_df = (
                        fresh_users_df.astype(object)
                        .fillna("")
                        .replace(["nan", "NaN", "<NA>"], "")
                    )
                    set_with_dataframe_fn(ws_users, fresh_users_df)
                    st.cache_data.clear()
                    st.success("✅ Đổi mật khẩu thành công!")

    if st.button("🚪 Đăng xuất", type="primary", key="logout_btn", width="stretch"):
        st.session_state["authenticated_user_id"] = None
        st.query_params.clear()
        st.rerun()


def render_pred_match_header(match_number, team_a, team_b, group_label, is_knockout=False):
    ko_badge = '<span class="pred-ko-badge">KNOCK-OUT</span>' if is_knockout else ""
    _html(
        f'<div class="pred-card-header">'
        f'<div class="pred-card-meta">'
        f'<span class="pred-card-number">Trận {html.escape(str(match_number))}</span>'
        f'<span class="pred-card-group">{html.escape(str(group_label))}</span>'
        f"{ko_badge}"
        f"</div>"
        f'<div class="pred-card-teams">'
        f'<span class="pred-card-team">{html.escape(str(team_a))}</span>'
        f'<span class="pred-card-vs">VS</span>'
        f'<span class="pred-card-team">{html.escape(str(team_b))}</span>'
        f"</div></div>"
    )


def render_pred_page_banner(user_name: str, open_count: int, saved_count: int):
    _html(
        f'<div class="pred-page-banner">'
        f'<div class="pred-banner-left">'
        f'<div class="pred-banner-title">Xin chào, {html.escape(user_name)}</div>'
        f'<div class="pred-banner-sub">Chọn trận, nhập tỉ số và tích <strong>Chốt dự đoán</strong> trước khi lưu.</div>'
        f"</div>"
        f'<div class="pred-banner-stats">'
        f'<div class="pred-banner-stat"><span>{open_count}</span><label>Trận mở</label></div>'
        f'<div class="pred-banner-stat"><span>{saved_count}</span><label>Đã dự đoán</label></div>'
        f"</div></div>"
    )

