import html

import pandas as pd
import streamlit as st

from data_service import (
    hash_password,
    init_connection,
    normalize_users_df,
    prep_matches,
    read_predictions_sheet,
    read_sheet,
    upsert_user_predictions,
    vietnam_timestamp,
)
from team_flags import build_name_to_fifa
from schedule_service import match_round_label_vn
from scoring import (
    calculate_fines,
    calculate_points,
    format_history_momentum,
    format_history_verdict,
    format_matchup_display,
    format_matchup_html,
    format_pred_pick,
    format_pred_pick_html,
    is_match_finished,
    normalize_pred_outcome,
)
from players_service import load_players_df, prep_players, top_players
from ui_components import (
    apply_global_styles,
    custom_loader,
    render_login_branding,
    render_login_footer,
    render_outcome_picker,
    render_page_header,
    render_pred_confirm_checkbox,
    render_pred_match_header,
    render_pred_page_banner,
    render_pred_history_desktop_table,
    render_pred_history_mobile_section,
    render_pred_tabs,
    render_sidebar,
    render_squad_mini_panel,
    render_user_account_panel,
    sync_auth_session,
    _html,
)

st.set_page_config(page_title="Dự Đoán WC 2026", page_icon="✍️", layout="wide")

apply_global_styles()
sync_auth_session()
render_sidebar()

if "chk_reset_counter" not in st.session_state: st.session_state["chk_reset_counter"] = 0
if "authenticated_user_id" not in st.session_state: st.session_state["authenticated_user_id"] = None
if "success_msg_pred" in st.session_state:
    st.success(st.session_state["success_msg_pred"])
    st.toast("Lưu thành công! Bảng dự đoán đã được cập nhật.", icon="🎉")
    del st.session_state["success_msg_pred"]

render_page_header("Dự đoán", "Chọn kết quả Đội A / Hòa / Đội B và chốt trước giờ bóng lăn", variant="predict", eyebrow="Prediction Center")

@st.cache_data(ttl=3600, show_spinner=False)
def load_players_for_pred():
    sh = init_connection()
    players_raw = load_players_df(sh)
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    return prep_players(players_raw, teams_df)


@st.cache_data(ttl=300, show_spinner=False)
def load_and_prep_data():
    sh = init_connection()
    users_df = normalize_users_df(read_sheet(sh, "users"))
    preds_df = read_predictions_sheet(sh)
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")

    for df in (matches_raw,):
        df.replace("", pd.NA, inplace=True)

    matches_df = prep_matches(matches_raw, teams_df)
    return users_df, matches_df, preds_df, teams_df

with custom_loader("Đang tải dữ liệu ..."):
    users_df, matches_df, preds_df, teams_df = load_and_prep_data()

name_to_id = {row["team_name"]: row["id"] for _, row in teams_df.iterrows()}
name_to_id["TBD"] = None
id_to_name = {row["id"]: row["team_name"] for _, row in teams_df.iterrows()}
name_to_fifa = build_name_to_fifa(teams_df)
user_names = users_df["name"].tolist()

if not st.session_state["authenticated_user_id"]:
    _html('<div class="login-page-wrap">')
    login_col = st.container()
    with login_col:
        render_login_branding(title="Đăng nhập", eyebrow="Khu vực dự đoán", icon="✍️")
        _html('<div class="login-form-marker"></div>')
        with st.container(border=True):
            with st.form("login_form"):
                login_id = st.text_input("Tên hiển thị hoặc Mã ID", placeholder="Ví dụ: U01 hoặc Tony")
                login_pwd = st.text_input("Mật khẩu / Mã PIN", type="password", placeholder="Nhập mật khẩu của bạn")
                submit_login = st.form_submit_button("🔓 Đăng nhập hệ thống", type="primary", width="stretch")

                if submit_login:
                    login_id_clean = login_id.strip()
                    user_match = users_df[(users_df["name"] == login_id_clean) | (users_df["user_id"] == login_id_clean)]

                    if user_match.empty: st.error("❌ Tên đăng nhập không tồn tại!")
                    else:
                        stored_password_hash = str(user_match["password"].values[0]).strip()
                        if len(stored_password_hash) < 64 and stored_password_hash.endswith(".0"):
                            stored_password_hash = stored_password_hash[:-2]
                        if hash_password(login_pwd.strip()) == stored_password_hash or login_pwd.strip() == stored_password_hash:
                            st.session_state["authenticated_user_id"] = str(user_match["user_id"].values[0])
                            st.success("🔓 Đăng nhập thành công!")
                            st.rerun()
                        else: st.error("❌ Sai mật khẩu!")
        render_login_footer()
    _html("</div>")
    st.stop()

selected_user_id = st.session_state["authenticated_user_id"]
user_row = users_df[users_df["user_id"] == selected_user_id]
selected_user_name = user_row["name"].values[0]
stored_password_hash = str(user_row["password"].values[0]).strip()
if len(stored_password_hash) < 64 and stored_password_hash.endswith(".0"):
    stored_password_hash = stored_password_hash[:-2]

def _render_one_match(row, selected_user_id, preds_df, id_to_name):
    m_id = str(row["match_id"] if "match_id" in row else row["id"])
    team_a, team_b = row["team_a"], row["team_b"]
    team_a_fifa = row.get("team_a_fifa") if "team_a_fifa" in row.index else name_to_fifa.get(team_a)
    team_b_fifa = row.get("team_b_fifa") if "team_b_fifa" in row.index else name_to_fifa.get(team_b)
    is_knockout = row["stage_id"] > 1
    old_pred = preds_df[(preds_df["user_id"] == selected_user_id) & (preds_df["match_id"].astype(str) == m_id)]
    
    default_outcome = "D"
    if not old_pred.empty:
        saved = normalize_pred_outcome(old_pred["pred_outcome"].values[0])
        if saved: default_outcome = saved

    old_adv_id = old_pred["pred_advanced_team_id"].values[0] if not old_pred.empty and pd.notna(old_pred["pred_advanced_team_id"].values[0]) else None
    old_adv_name = id_to_name.get(str(old_adv_id), "TBD") if old_adv_id else team_a

    saved_outcome = normalize_pred_outcome(old_pred["pred_outcome"].values[0]) if not old_pred.empty else None
    has_saved = saved_outcome is not None
    picker_key = f"outcome_{selected_user_id}_{m_id}"
    current_outcome = normalize_pred_outcome(st.session_state.get(picker_key, default_outcome))

    pred_badge = None
    if has_saved and current_outcome == saved_outcome:
        pred_badge = "saved"
    elif has_saved and current_outcome != saved_outcome:
        pred_badge = "draft"
    elif not has_saved and current_outcome and current_outcome != default_outcome:
        pred_badge = "draft"

    render_pred_match_header(
        row["match_number"], team_a, team_b,
        group_round=row.get("group_round") or row.get("match_label"),
        stage_id=row.get("stage_id"),
        is_knockout=is_knockout,
        has_saved_pred=has_saved,
        pred_badge=pred_badge,
        team_a_fifa=team_a_fifa, team_b_fifa=team_b_fifa, name_to_fifa=name_to_fifa,
        kickoff_vn=row.get("kickoff_vn"),
    )

    outcome = render_outcome_picker(
        team_a,
        team_b,
        default_outcome,
        widget_key=f"outcome_{selected_user_id}_{m_id}",
    )

    if team_a != "TBD" and team_b != "TBD":
        with st.expander("Đội hình 2 đội", expanded=False):
            players_df = load_players_for_pred()
            code_a = str(team_a_fifa or name_to_fifa.get(team_a, "")).strip().upper()
            code_b = str(team_b_fifa or name_to_fifa.get(team_b, "")).strip().upper()
            col_a, col_b = st.columns(2)
            with col_a:
                if code_a:
                    render_squad_mini_panel(
                        team_a,
                        code_a,
                        top_players(players_df, code_a, limit=3).to_dict("records"),
                        name_to_fifa=name_to_fifa,
                    )
                else:
                    st.caption("Chưa có mã FIFA đội A.")
            with col_b:
                if code_b:
                    render_squad_mini_panel(
                        team_b,
                        code_b,
                        top_players(players_df, code_b, limit=3).to_dict("records"),
                        name_to_fifa=name_to_fifa,
                    )
                else:
                    st.caption("Chưa có mã FIFA đội B.")

    adv_team = "TBD"
    dynamic_chk_key = f"chk_pred_{selected_user_id}_{m_id}_{st.session_state['chk_reset_counter']}"

    if is_knockout and outcome == "D" and team_a != "TBD" and team_b != "TBD":
        _html('<div class="pen-picker-shell"><span class="pen-picker-label">Đội đi tiếp sau loạt PEN</span></div>')
        options_adv = [team_a, team_b]
        idx_adv = options_adv.index(old_adv_name) if old_adv_name in options_adv else 0
        adv_team = st.selectbox(
            "Đội đi tiếp (PEN):",
            options_adv,
            index=idx_adv,
            key=f"adv_{selected_user_id}_{m_id}",
            label_visibility="collapsed",
        )
        is_confirmed = render_pred_confirm_checkbox(dynamic_chk_key)
    else:
        is_confirmed = render_pred_confirm_checkbox(dynamic_chk_key)

    if is_confirmed: return m_id, (outcome, adv_team, is_knockout)
    return None

with st.sidebar:
    st.markdown("### ⚙️ Tài khoản")
    render_user_account_panel(selected_user_id, selected_user_name, user_names, stored_password_hash, hash_password, init_connection, None, pd)

saved_count = len(preds_df[preds_df["user_id"] == selected_user_id])
tab1, tab2 = render_pred_tabs(["✍️ Cập nhật dự đoán", "📜 Lịch sử dự đoán"])

with tab1:
    upcoming_matches = matches_df[(matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna()) & (matches_df["is_locked"] != True)].copy()

    if upcoming_matches.empty:
        st.info("Tất cả trận hiện tại đã khóa hoặc kết thúc. Không còn trận để dự đoán!")
    else:
        upcoming_matches = upcoming_matches.sort_values(["kickoff_vn", "match_number"]).head(10)
        render_pred_page_banner(selected_user_name, len(upcoming_matches), saved_count)
        st.markdown('<div class="pred-form-actions-marker"></div>', unsafe_allow_html=True)

        with st.form("prediction_form"):
            user_inputs = {}
            use_two_cols = len(upcoming_matches) >= 3
            matches_list = list(upcoming_matches.iterrows())

            def _render_match_card(row):
                with st.container(border=True):
                    return _render_one_match(row, selected_user_id, preds_df, id_to_name)

            if use_two_cols:
                for i in range(0, len(matches_list), 2):
                    col_left, col_right = st.columns(2, gap="large")
                    with col_left:
                        result = _render_match_card(matches_list[i][1])
                        if result:
                            m_id, payload = result
                            user_inputs[m_id] = payload
                    if i + 1 < len(matches_list):
                        with col_right:
                            result = _render_match_card(matches_list[i + 1][1])
                            if result:
                                m_id, payload = result
                                user_inputs[m_id] = payload
            else:
                for _, row in matches_list:
                    result = _render_match_card(row)
                    if result:
                        m_id, payload = result
                        user_inputs[m_id] = payload

            st.markdown('<div class="pred-form-actions">', unsafe_allow_html=True)
            submitted = st.form_submit_button("💾 Lưu tất cả dự đoán đã chốt", type="primary", width="stretch")
            st.markdown("</div>", unsafe_allow_html=True)

        if submitted:
            if not user_inputs:
                st.warning("Bạn chưa tích 'Chốt dự đoán' cho bất kỳ trận nào.")
            else:
                sh = init_connection()
                ws_matches = sh.worksheet("matches")
                data_matches = ws_matches.get_all_values()
                fresh_matches_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()

                ignored_matches = []
                ts = vietnam_timestamp()
                ws_preds = sh.worksheet("predictions")
                entries = []

                for m_id, (outcome, adv_t, is_ko) in user_inputs.items():
                    id_col_fresh = "id" if "id" in fresh_matches_df.columns else "match_id"
                    match_status = fresh_matches_df[fresh_matches_df[id_col_fresh].astype(str) == m_id]
                    is_locked_now = False
                    if not match_status.empty and "is_locked" in match_status.columns:
                        is_locked_now = str(match_status["is_locked"].values[0]).strip().upper() == "TRUE"

                    if is_locked_now:
                        ignored_matches.append(m_id)
                        continue

                    adv_id = str(name_to_id.get(adv_t)) if (is_ko and outcome == "D" and adv_t != "TBD") else ""
                    entries.append((m_id, normalize_pred_outcome(outcome) or "", adv_id, ts))

                upsert_user_predictions(ws_preds, selected_user_id, entries)

                for m_id in user_inputs:
                    st.session_state.pop(f"outcome_{selected_user_id}_{m_id}", None)
                    st.session_state.pop(f"adv_{selected_user_id}_{m_id}", None)

                st.session_state["chk_reset_counter"] += 1
                st.cache_data.clear()

                if ignored_matches:
                    st.session_state["success_msg_pred"] = "⚠️ Một số trận đã bị khóa trước khi lưu. Các trận còn lại đã cập nhật!"
                else:
                    st.session_state["success_msg_pred"] = "🎉 Đã lưu dự đoán lên Cloud thành công!"
                st.rerun()

with tab2:
    _html('<div class="pred-history-panel-marker" aria-hidden="true"></div>')
    _html(
        f'<div class="pred-history-title">📜 Lịch sử — {html.escape(selected_user_name)}</div>'
        f'<div class="pred-history-caption">Số trận chính thức · chỉ hiện trận bạn đã dự đoán</div>'
    )
    user_history_df = preds_df[preds_df["user_id"] == selected_user_id].copy()

    if user_history_df.empty:
        st.info("Bạn chưa dự đoán trận nào.")
    else:
        display_history = pd.merge(user_history_df, matches_df, on="match_id", how="inner")
        display_history["match_number"] = pd.to_numeric(display_history["match_number"], errors="coerce")
        display_history = display_history.sort_values(by=["kickoff_vn", "match_number"])

        def _history_stage_id(row):
            try:
                return int(float(row["stage_id"]))
            except (ValueError, TypeError):
                return 1

        def _history_adv_name(row):
            stage_id = _history_stage_id(row)
            if stage_id <= 1 or normalize_pred_outcome(row.get("pred_outcome")) != "D":
                return None
            try:
                adv_id = row.get("pred_advanced_team_id")
                if pd.notna(adv_id) and str(adv_id).strip():
                    return id_to_name.get(str(int(float(adv_id))), "")
            except (ValueError, TypeError):
                pass
            return None

        def _history_fifa(row, team_key: str):
            team = row.get(team_key, "")
            fifa_key = f"{team_key}_fifa"
            return row.get(fifa_key) or name_to_fifa.get(team)

        display_history["Bảng"] = display_history.apply(
            lambda row: match_round_label_vn(
                group_round=row.get("group_round"),
                match_label=row.get("match_label"),
                stage_id=row.get("stage_id"),
            ),
            axis=1,
        )
        display_history["Trận đấu"] = display_history.apply(
            lambda row: format_matchup_display(
                team_a=row["team_a"],
                team_b=row["team_b"],
                name_to_fifa=name_to_fifa,
                team_a_fifa=_history_fifa(row, "team_a"),
                team_b_fifa=_history_fifa(row, "team_b"),
            ),
            axis=1,
        )
        display_history["Dự đoán"] = display_history.apply(
            lambda row: format_pred_pick(
                row.get("pred_outcome"),
                team_a=row["team_a"],
                team_b=row["team_b"],
                adv_team_name=_history_adv_name(row),
                is_knockout=_history_stage_id(row) > 1,
                name_to_fifa=name_to_fifa,
                team_a_fifa=_history_fifa(row, "team_a"),
                team_b_fifa=_history_fifa(row, "team_b"),
            ),
            axis=1,
        )
        display_history["Trận đấu_html"] = display_history.apply(
            lambda row: format_matchup_html(
                team_a=row["team_a"],
                team_b=row["team_b"],
                name_to_fifa=name_to_fifa,
                team_a_fifa=_history_fifa(row, "team_a"),
                team_b_fifa=_history_fifa(row, "team_b"),
            ),
            axis=1,
        )
        display_history["Dự đoán_html"] = display_history.apply(
            lambda row: format_pred_pick_html(
                row.get("pred_outcome"),
                team_a=row["team_a"],
                team_b=row["team_b"],
                adv_team_name=_history_adv_name(row),
                is_knockout=_history_stage_id(row) > 1,
                name_to_fifa=name_to_fifa,
                team_a_fifa=_history_fifa(row, "team_a"),
                team_b_fifa=_history_fifa(row, "team_b"),
            ),
            axis=1,
        )
        display_history["Kết quả"] = display_history.apply(format_history_verdict, axis=1)

        total_preds = len(display_history)
        finished_mask = display_history.apply(is_match_finished, axis=1)
        finished_count = int(finished_mask.sum())
        finished_rows = display_history[finished_mask]
        total_points = int(finished_rows.apply(calculate_points, axis=1).sum()) if finished_count else 0
        total_fines = int(finished_rows.apply(calculate_fines, axis=1).sum()) if finished_count else 0
        summary_parts = [
            f"{total_preds} dự đoán",
            f"{finished_count} trận đã có kết quả",
            f"+{total_points} điểm",
        ]
        if total_fines > 0:
            summary_parts.append(f"phạt {total_fines}k")
        summary_text = " · ".join(summary_parts)
        momentum = format_history_momentum(display_history)
        if momentum:
            summary_text = f"{momentum} · {summary_text}"

        # 🤖 Tự động phát hiện thiết bị qua User-Agent trực tiếp từ Python
        try:
            user_agent = st.context.headers.get("User-Agent", "")
            is_mobile = any(kw in user_agent for kw in ["Mobile", "Android", "iPhone", "iPad", "webOS", "Opera Mini"])
            default_view = "📱 Bản Điện thoại" if is_mobile else "💻 Bản Máy tính"
        except Exception:
            default_view = "📱 Bản Điện thoại"

        # Đổi sang st.radio horizontal để tự động thừa hưởng class CSS Custom cực đẹp của App
        view_mode = st.radio(
            "Chế độ xem lịch sử",
            options=["📱 Bản Điện thoại", "💻 Bản Máy tính"],
            index=0 if default_view == "📱 Bản Điện thoại" else 1,
            horizontal=True,
            key="history_view_toggle",
            label_visibility="collapsed"
        )
        
        _html('<div style="margin-top: 15px;"></div>')
        
        if view_mode == "💻 Bản Máy tính":
            render_pred_history_desktop_table(display_history)
        else:
            render_pred_history_mobile_section(display_history)
            
        _html(f'<div class="pred-history-summary">{html.escape(summary_text)}</div>')
