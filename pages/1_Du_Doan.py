import hashlib
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st
from gspread_dataframe import set_with_dataframe

from data_service import init_connection, prep_matches, read_sheet
from ui_components import (
    apply_global_styles,
    custom_loader,
    render_login_card,
    render_page_header,
    render_pred_match_header,
    render_pred_page_banner,
    render_sidebar,
    render_user_account_panel,
    sync_auth_session,
    _html,
)

st.set_page_config(page_title="Dự Đoán WC 2026", page_icon="✍️", layout="wide")

apply_global_styles()
sync_auth_session()
render_sidebar()

if "chk_reset_counter" not in st.session_state:
    st.session_state["chk_reset_counter"] = 0
if "authenticated_user_id" not in st.session_state:
    st.session_state["authenticated_user_id"] = None

if "success_msg_pred" in st.session_state:
    st.success(st.session_state["success_msg_pred"])
    st.toast("Lưu thành công! Bảng dự đoán đã được cập nhật.", icon="🎉")
    del st.session_state["success_msg_pred"]

render_page_header(
    "✍️ Trung tâm dự đoán",
    "Chọn trận, nhập tỉ số và chốt trước giờ bóng lăn",
    variant="predict",
    eyebrow="Prediction Center",
)


def hash_password(password):
    try:
        salt = st.secrets["password_salt"]
    except KeyError:
        salt = "MuoiMacDinh_@123"
    return hashlib.sha256((str(password) + salt).encode("utf-8")).hexdigest()


@st.cache_data(ttl=300, show_spinner=False)
def load_and_prep_data():
    sh = init_connection()
    users_df = read_sheet(sh, "users")
    preds_df = read_sheet(sh, "predictions")
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")

    for df in (users_df, preds_df, matches_raw):
        df.replace("", pd.NA, inplace=True)

    if "password" not in users_df.columns:
        users_df["password"] = "1234"

    users_df["user_id"] = users_df["user_id"].astype(str)
    users_df["name"] = users_df["name"].astype(str)
    users_df["password"] = users_df["password"].astype(str)

    if "pred_advanced_team_id" not in preds_df.columns:
        preds_df["pred_advanced_team_id"] = None

    preds_df["user_id"] = preds_df["user_id"].astype(str)
    preds_df["match_id"] = preds_df["match_id"].astype(str)

    matches_df = prep_matches(matches_raw, teams_df)
    return users_df, matches_df, preds_df, teams_df


with custom_loader("Đang tải dữ liệu từ trung tâm dự đoán..."):
    users_df, matches_df, preds_df, teams_df = load_and_prep_data()

name_to_id = {row["team_name"]: row["id"] for _, row in teams_df.iterrows()}
name_to_id["TBD"] = None
id_to_name = {row["id"]: row["team_name"] for _, row in teams_df.iterrows()}
user_names = users_df["name"].tolist()

if not st.session_state["authenticated_user_id"]:
    st.info("🔒 Vui lòng đăng nhập để tham gia dự đoán.")
    render_login_card()

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            login_id = st.text_input(
                "👤 Tên hiển thị (hoặc Mã ID):",
                placeholder="Ví dụ: U01 hoặc Tên của bạn",
            )
            login_pwd = st.text_input("🔑 Mật khẩu / Mã PIN:", type="password")
            submit_login = st.form_submit_button(
                "Đăng nhập hệ thống", type="primary", width="stretch"
            )

            if submit_login:
                login_id_clean = login_id.strip()
                user_match = users_df[
                    (users_df["name"] == login_id_clean)
                    | (users_df["user_id"] == login_id_clean)
                ]

                if user_match.empty:
                    st.error("❌ Tên đăng nhập hoặc Mã ID không tồn tại!")
                else:
                    stored_password_hash = str(user_match["password"].values[0]).strip()
                    if len(stored_password_hash) < 64 and stored_password_hash.endswith(".0"):
                        stored_password_hash = stored_password_hash[:-2]

                    if (
                        hash_password(login_pwd.strip()) == stored_password_hash
                        or login_pwd.strip() == stored_password_hash
                    ):
                        st.session_state["authenticated_user_id"] = str(
                            user_match["user_id"].values[0]
                        )
                        st.success("🔓 Đăng nhập thành công!")
                        st.rerun()
                    else:
                        st.error("❌ Sai mật khẩu! Vui lòng thử lại.")
    st.stop()

selected_user_id = st.session_state["authenticated_user_id"]
user_row = users_df[users_df["user_id"] == selected_user_id]
selected_user_name = user_row["name"].values[0]
stored_password_hash = str(user_row["password"].values[0]).strip()
if len(stored_password_hash) < 64 and stored_password_hash.endswith(".0"):
    stored_password_hash = stored_password_hash[:-2]

if len(stored_password_hash) < 64 and stored_password_hash.endswith(".0"):
    stored_password_hash = stored_password_hash[:-2]


def _render_one_match(row, selected_user_id, preds_df, id_to_name):
    """Render inputs for a single match; returns (m_id, payload) if confirmed else None."""
    m_id = str(row["match_id"] if "match_id" in row else row["id"])
    team_a, team_b = row["team_a"], row["team_b"]
    is_knockout = row["stage_id"] > 1

    old_pred = preds_df[
        (preds_df["user_id"] == selected_user_id)
        & (preds_df["match_id"].astype(str) == m_id)
    ]

    default_a = (
        int(float(old_pred["pred_score_a"].values[0]))
        if not old_pred.empty
        and pd.notna(old_pred["pred_score_a"].values[0])
        and str(old_pred["pred_score_a"].values[0]).strip() != ""
        else 0
    )
    default_b = (
        int(float(old_pred["pred_score_b"].values[0]))
        if not old_pred.empty
        and pd.notna(old_pred["pred_score_b"].values[0])
        and str(old_pred["pred_score_b"].values[0]).strip() != ""
        else 0
    )

    old_adv_id = (
        old_pred["pred_advanced_team_id"].values[0]
        if not old_pred.empty and pd.notna(old_pred["pred_advanced_team_id"].values[0])
        else None
    )
    old_adv_name = id_to_name.get(old_adv_id, "TBD") if old_adv_id else "TBD"

    render_pred_match_header(row["match_number"], team_a, team_b, row["match_label"], is_knockout)

    s1, s2, s3 = st.columns([5, 1, 5])
    with s1:
        score_a = st.number_input(
            team_a,
            min_value=0,
            max_value=20,
            value=default_a,
            key=f"pred_{selected_user_id}_{m_id}_a",
            label_visibility="visible",
        )
    with s2:
        st.markdown(
            '<div style="text-align:center;font-weight:800;color:#64748b;margin-top:2rem;">–</div>',
            unsafe_allow_html=True,
        )
    with s3:
        score_b = st.number_input(
            team_b,
            min_value=0,
            max_value=20,
            value=default_b,
            key=f"pred_{selected_user_id}_{m_id}_b",
            label_visibility="visible",
        )

    dynamic_chk_key = f"chk_pred_{selected_user_id}_{m_id}_{st.session_state['chk_reset_counter']}"
    adv_team = "TBD"

    if is_knockout and team_a != "TBD" and team_b != "TBD":
        p1, p2 = st.columns([3, 2])
        with p1:
            options_adv = [team_a, team_b]
            idx_adv = options_adv.index(old_adv_name) if old_adv_name in options_adv else 0
            adv_team = st.selectbox(
                "Đội đi tiếp (PEN):",
                options_adv,
                index=idx_adv,
                key=f"adv_{selected_user_id}_{m_id}",
            )
        with p2:
            st.markdown('<div class="pred-confirm-row">', unsafe_allow_html=True)
            is_confirmed = st.checkbox("Chốt dự đoán", key=dynamic_chk_key)
            st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown('<div class="pred-confirm-row">', unsafe_allow_html=True)
        is_confirmed = st.checkbox("Chốt dự đoán", key=dynamic_chk_key)
        st.markdown("</div>", unsafe_allow_html=True)

    if is_confirmed:
        return m_id, (score_a, score_b, adv_team, is_knockout)
    return None


with st.sidebar:
    st.markdown("### ⚙️ Tài khoản")
    render_user_account_panel(
        user_id=selected_user_id,
        user_name=selected_user_name,
        user_names=user_names,
        stored_password_hash=stored_password_hash,
        hash_password_fn=hash_password,
        init_connection_fn=init_connection,
        set_with_dataframe_fn=set_with_dataframe,
        pd_module=pd,
    )

saved_count = len(preds_df[preds_df["user_id"] == selected_user_id])

tab1, tab2 = st.tabs(["✍️ Cập nhật dự đoán", "📜 Lịch sử dự đoán"])

with tab1:
    upcoming_matches = matches_df[
        (matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna())
        & (matches_df["is_locked"] != True)
    ].copy()

    if upcoming_matches.empty:
        st.info("Tất cả trận hiện tại đã khóa hoặc kết thúc. Không còn trận để dự đoán!")
    else:
        upcoming_matches = upcoming_matches.head(10)
        render_pred_page_banner(selected_user_name, len(upcoming_matches), saved_count)

        st.markdown(
            '<div class="pred-form-actions-marker"></div>',
            unsafe_allow_html=True,
        )

        with st.form("prediction_form"):
            user_inputs = {}
            split_at = (len(upcoming_matches) + 1) // 2
            left_chunk = upcoming_matches.iloc[:split_at]
            right_chunk = upcoming_matches.iloc[split_at:]
            use_two_cols = len(upcoming_matches) >= 3

            if use_two_cols:
                col_left, col_right = st.columns(2, gap="large")
                columns_chunks = [(col_left, left_chunk), (col_right, right_chunk)]
            else:
                columns_chunks = [(st.container(), upcoming_matches)]

            for col, chunk in columns_chunks:
                if chunk.empty:
                    continue
                with col:
                    for _, row in chunk.iterrows():
                        with st.container(border=True):
                            result = _render_one_match(row, selected_user_id, preds_df, id_to_name)
                        if result:
                            m_id, payload = result
                            user_inputs[m_id] = payload

            st.markdown('<div class="pred-form-actions">', unsafe_allow_html=True)
            submitted = st.form_submit_button(
                "💾 Lưu tất cả dự đoán đã chốt",
                type="primary",
                width="stretch",
            )
            st.markdown("</div>", unsafe_allow_html=True)

        if submitted:
            if not user_inputs:
                st.warning("Bạn chưa tích 'Chốt dự đoán' cho bất kỳ trận nào.")
            else:
                sh = init_connection()
                ws_matches = sh.worksheet("matches")
                data_matches = ws_matches.get_all_values()
                fresh_matches_df = (
                    pd.DataFrame(data_matches[1:], columns=data_matches[0])
                    if data_matches
                    else pd.DataFrame()
                )
                fresh_matches_df.replace("", pd.NA, inplace=True)

                new_preds, ignored_matches = [], []

                for m_id, (sa, sb, adv_t, is_ko) in user_inputs.items():
                    id_col_fresh = "id" if "id" in fresh_matches_df.columns else "match_id"
                    match_status = fresh_matches_df[
                        fresh_matches_df[id_col_fresh].astype(str) == m_id
                    ]

                    is_locked_now = False
                    if not match_status.empty and "is_locked" in match_status.columns:
                        is_locked_now = (
                            str(match_status["is_locked"].values[0]).strip().upper() == "TRUE"
                        )

                    if is_locked_now:
                        ignored_matches.append(m_id)
                        continue

                    adv_id = None
                    if is_ko and sa == sb and adv_t != "TBD":
                        adv_id = name_to_id.get(adv_t)

                    new_preds.append(
                        {
                            "user_id": selected_user_id,
                            "match_id": m_id,
                            "pred_score_a": sa,
                            "pred_score_b": sb,
                            "pred_advanced_team_id": adv_id,
                            "timestamp": (datetime.utcnow() + timedelta(hours=7)).strftime(
                                "%Y-%m-%d %H:%M:%S"
                            ),
                        }
                    )

                if new_preds:
                    new_preds_df = pd.DataFrame(new_preds)
                    ws_preds = sh.worksheet("predictions")
                    data_preds = ws_preds.get_all_values()
                    current_preds_df = (
                        pd.DataFrame(data_preds[1:], columns=data_preds[0])
                        if data_preds
                        else pd.DataFrame()
                    )
                    current_preds_df.replace("", pd.NA, inplace=True)
                    current_preds_df["match_id"] = current_preds_df["match_id"].astype(str)
                    current_preds_df["user_id"] = current_preds_df["user_id"].astype(str)

                    if "pred_advanced_team_id" not in current_preds_df.columns:
                        current_preds_df["pred_advanced_team_id"] = None

                    valid_m_ids = [p["match_id"] for p in new_preds]
                    current_preds_df = current_preds_df[
                        ~(
                            (current_preds_df["user_id"] == selected_user_id)
                            & (current_preds_df["match_id"].isin(valid_m_ids))
                        )
                    ]

                    final_preds_df = pd.concat([current_preds_df, new_preds_df], ignore_index=True)
                    ws_preds.clear()
                    final_preds_df = (
                        final_preds_df.astype(object)
                        .fillna("")
                        .replace(["nan", "NaN", "<NA>"], "")
                    )
                    set_with_dataframe(ws_preds, final_preds_df)

                for m_id in user_inputs:
                    st.session_state.pop(f"pred_{selected_user_id}_{m_id}_a", None)
                    st.session_state.pop(f"pred_{selected_user_id}_{m_id}_b", None)
                    st.session_state.pop(f"adv_{selected_user_id}_{m_id}", None)

                st.session_state["chk_reset_counter"] += 1
                st.cache_data.clear()

                if ignored_matches:
                    st.session_state["success_msg_pred"] = (
                        "⚠️ Một số trận đã bị khóa trước khi lưu. Các trận còn lại đã cập nhật!"
                    )
                else:
                    st.session_state["success_msg_pred"] = (
                        "🎉 Đã lưu dự đoán lên Cloud thành công!"
                    )
                st.rerun()

with tab2:
    _html(f'<div class="content-card-title">📜 Lịch sử — {selected_user_name}</div>')
    user_history_df = preds_df[preds_df["user_id"] == selected_user_id].copy()

    if user_history_df.empty:
        st.info("Bạn chưa dự đoán trận nào.")
    else:
        display_history = pd.merge(
            user_history_df, matches_df, left_on="match_id", right_on="match_id", how="inner"
        )
        display_history["match_number"] = pd.to_numeric(
            display_history["match_number"], errors="coerce"
        )
        display_history = display_history.sort_values(by="match_number")

        def format_prediction(row):
            try:
                score_a = int(float(row["pred_score_a"]))
                score_b = int(float(row["pred_score_b"]))
            except (ValueError, TypeError):
                score_a, score_b = 0, 0

            base_pred = f"{row['team_a']}  {score_a} - {score_b}  {row['team_b']}"

            try:
                stage_id = int(float(row["stage_id"]))
            except (ValueError, TypeError):
                stage_id = 1

            if stage_id > 1 and score_a == score_b:
                try:
                    adv_name = id_to_name.get(int(float(row["pred_advanced_team_id"])), "")
                    if adv_name:
                        base_pred += f" (PEN: {adv_name})"
                except (ValueError, TypeError):
                    pass
            return base_pred

        display_history["Dự đoán"] = display_history.apply(format_prediction, axis=1)
        final_table = display_history[
            ["match_number", "match_label", "Dự đoán", "timestamp"]
        ].rename(
            columns={
                "match_number": "Trận",
                "match_label": "Bảng/Vòng",
                "timestamp": "Thời gian",
            }
        )
        st.dataframe(final_table, width="stretch", hide_index=True)
