import pandas as pd
import streamlit as st

from data_service import (
    init_connection,
    normalize_predictions_df,
    prep_matches,
    read_sheet,
    vietnam_timestamp,
    write_worksheet_dataframe,
)
from prediction_matrix_service import MATRIX_SHEET_NAME, build_prediction_matrix
from team_flags import build_name_to_fifa
from schedule_service import format_date_compact_vn, format_time_vn
from ui_components import (
    _get_col_letter,
    apply_global_styles,
    custom_loader,
    render_page_header,
    render_sidebar,
    sync_auth_session,
    _html,
)

st.set_page_config(page_title="Admin - Cập Nhật Kết Quả", page_icon="🔒", layout="wide")

apply_global_styles()
sync_auth_session()
render_sidebar()

if "admin_logged_in" not in st.session_state:
    st.session_state["admin_logged_in"] = False

if not st.session_state["admin_logged_in"]:
    render_page_header("⚙️ Góc của Elu", "Đăng nhập để thao túng kết quả trận đấu", variant="admin", eyebrow="Admin Panel")
    _html('<div class="login-form-marker admin-login-marker"></div>')
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            pwd = st.text_input("Admin Password:", type="password")
            submit_login = st.form_submit_button("Đăng nhập", type="primary", width="stretch")
            if submit_login:
                correct_admin_pass = st.secrets.get("admin_password", "")
                if not correct_admin_pass:
                    st.error("⚠️ Chưa cấu hình mật khẩu Admin (thiếu secrets.toml).")
                elif pwd == correct_admin_pass:
                    st.session_state["admin_logged_in"] = True
                    st.success("Đăng nhập thành công!")
                    st.rerun()
                else:
                    st.error("❌ Sai mật khẩu.")
    st.stop()

col_title, col_logout = st.columns([8, 1])
with col_logout:
    if st.button("🚪 Đăng xuất"):
        st.session_state["admin_logged_in"] = False
        st.rerun()

if "success_msg" in st.session_state:
    st.success(st.session_state["success_msg"])
    del st.session_state["success_msg"]

render_page_header("⚙️ Quản trị kết quả", "Cập nhật tỉ số, cặp knock-out và khóa trận đấu", variant="admin", eyebrow="Admin Panel")


@st.cache_data(ttl=300, show_spinner=False)
def load_matches_data():
    sh = init_connection()
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")
    teams_df.replace("", pd.NA, inplace=True)
    return prep_matches(matches_raw, teams_df), teams_df


@st.cache_data(ttl=300, show_spinner=False)
def load_matrix_data():
    sh = init_connection()
    users_df = read_sheet(sh, "users")
    preds_df = normalize_predictions_df(read_sheet(sh, "predictions"))
    matches_raw = read_sheet(sh, "matches")
    teams_df = read_sheet(sh, "teams")
    users_df.replace("", pd.NA, inplace=True)
    teams_df.replace("", pd.NA, inplace=True)
    matches_df = prep_matches(matches_raw, teams_df)
    return users_df, preds_df, matches_df, teams_df


with custom_loader("Đang đồng bộ dữ liệu quản trị..."):
    matches_df, teams_df = load_matches_data()

team_names_list = ["TBD"] + teams_df["team_name"].tolist()
name_to_id = {row["team_name"]: row["id"] for _, row in teams_df.iterrows()}
name_to_id["TBD"] = None
id_to_name = {str(row["id"]): row["team_name"] for _, row in teams_df.iterrows()}

pending_matches = matches_df[matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna()]
finished_matches = matches_df[matches_df["real_score_a"].notna() & matches_df["real_score_b"].notna()]

pending_matches = pending_matches.sort_values(["kickoff_vn", "match_number"])
finished_matches = finished_matches.sort_values(["kickoff_vn", "match_number"])
knockout_matches_sorted = matches_df[matches_df["stage_id"] > 1].sort_values(["kickoff_vn", "match_number"])
to_lock_matches_sorted = matches_df[
    (matches_df["real_score_a"].isna() | matches_df["real_score_b"].isna())
].sort_values(["kickoff_vn", "match_number"])


def _kickoff_label(row) -> str:
    kickoff = row.get("kickoff_vn")
    if kickoff is None:
        return ""
    try:
        dt = kickoff.to_pydatetime() if hasattr(kickoff, "to_pydatetime") else kickoff
        return f"🕐 {format_time_vn(dt)} · {format_date_compact_vn(dt)}"
    except (AttributeError, TypeError, ValueError):
        return ""


def _match_id(row) -> str:
    return str(row["match_id"] if "match_id" in row else row["id"])


def _score_preview_line(team_a: str, team_b: str, ra, rb, adv_team: str = "TBD") -> str:
    if ra is None or rb is None:
        return f"Trận {team_a} vs {team_b}: chưa nhập tỉ số"
    line = f"{team_a} {int(ra)}–{int(rb)} {team_b}"
    if adv_team and adv_team != "TBD":
        line += f" (PEN: {adv_team})"
    return line


def _apply_admin_updates(admin_inputs_dict, update_type="score"):
    sh = init_connection()
    ws_matches = sh.worksheet("matches")
    data_matches = ws_matches.get_all_values()
    raw_df = pd.DataFrame(data_matches[1:], columns=data_matches[0]) if data_matches else pd.DataFrame()
    raw_df.replace("", pd.NA, inplace=True)
    id_col = "id" if "id" in raw_df.columns else "match_id"

    for col in ("real_score_a", "real_score_b", "real_advanced_team_id", "home_team_id", "away_team_id", "is_locked"):
        if col not in raw_df.columns:
            raw_df[col] = None

    updates = []
    for m_id, payload in admin_inputs_dict.items():
        idx_list = raw_df.index[raw_df[id_col].astype(str) == m_id].tolist()
        if not idx_list:
            continue
        idx = idx_list[0]

        if update_type == "score":
            ra, rb, adv_t, is_ko = payload
            raw_df.loc[idx, "real_score_a"] = str(ra)
            raw_df.loc[idx, "real_score_b"] = str(rb)
            raw_df.loc[idx, "real_advanced_team_id"] = (
                str(name_to_id[adv_t]) if is_ko and ra == rb and adv_t != "TBD" else None
            )
        elif update_type == "knockout":
            team_a_name, team_b_name = payload
            raw_df.loc[idx, "home_team_id"] = str(name_to_id[team_a_name])
            raw_df.loc[idx, "away_team_id"] = str(name_to_id[team_b_name])
        elif update_type == "lock":
            lock_status = payload
            raw_df.loc[idx, "is_locked"] = str(lock_status).upper()

        row_data = raw_df.iloc[idx].fillna("").values.tolist()
        sheet_row = int(idx) + 2
        col_letter = _get_col_letter(len(row_data))
        updates.append({"range": f"A{sheet_row}:{col_letter}{sheet_row}", "values": [row_data]})

    if updates:
        ws_matches.batch_update(updates)
    st.cache_data.clear()
    st.rerun()


def _render_score_row(row, key_prefix: str, default_a=None, default_b=None, require_score: bool = True):
    m_id = _match_id(row)
    team_a, team_b = row["team_a"], row["team_b"]
    is_knockout = int(float(row["stage_id"])) > 1

    kickoff = _kickoff_label(row)
    kickoff_html = f' <span>· {kickoff}</span>' if kickoff else ""
    st.markdown(
        f'<div class="pred-match-header">⚽ Trận {row["match_number"]}: {team_a} vs {team_b} '
        f'<span>· {row["match_label"]}</span>{kickoff_html}</div>',
        unsafe_allow_html=True,
    )
    col1, col2, col3, col4, col5 = st.columns([1.5, 1, 0.5, 1, 2])
    with col2:
        real_a = st.number_input(
            f"{team_a}",
            min_value=0,
            max_value=20,
            value=None if require_score else (default_a if default_a is not None else 0),
            placeholder="0",
            key=f"{key_prefix}_{m_id}_a",
            label_visibility="collapsed",
        )
    with col3:
        st.markdown("<h4 style='text-align:center;margin:0;'>–</h4>", unsafe_allow_html=True)
    with col4:
        real_b = st.number_input(
            f"{team_b}",
            min_value=0,
            max_value=20,
            value=None if require_score else (default_b if default_b is not None else 0),
            placeholder="0",
            key=f"{key_prefix}_{m_id}_b",
            label_visibility="collapsed",
        )
    with col1:
        adv_team = "TBD"
        if is_knockout and team_a != "TBD" and team_b != "TBD":
            adv_team = st.selectbox("PEN:", [team_a, team_b], key=f"adv_{key_prefix}_{m_id}")
    with col5:
        is_confirmed = st.checkbox("Xác nhận", key=f"confirm_{key_prefix}_{m_id}")

    return m_id, team_a, team_b, real_a, real_b, adv_team, is_knockout, is_confirmed


def _collect_confirmed_scores(rows_df, key_prefix: str, require_score: bool = True):
    collected = {}
    missing_scores = []
    zero_zero_warnings = []

    for _, row in rows_df.iterrows():
        m_id, team_a, team_b, ra, rb, adv_team, is_ko, confirmed = _render_score_row(
            row,
            key_prefix,
            default_a=int(float(row["real_score_a"])) if pd.notna(row.get("real_score_a")) else 0,
            default_b=int(float(row["real_score_b"])) if pd.notna(row.get("real_score_b")) else 0,
            require_score=require_score,
        )
        st.write("---")
        if not confirmed:
            continue
        if require_score and (ra is None or rb is None):
            missing_scores.append(f"Trận {row['match_number']}: {team_a} vs {team_b}")
            continue
        if require_score and ra == 0 and rb == 0:
            zero_zero_warnings.append(f"Trận {row['match_number']}: {team_a} vs {team_b}")
        collected[m_id] = (ra, rb, adv_team, is_ko)

    return collected, missing_scores, zero_zero_warnings


def _render_submit_preview(lines: list[str], title: str):
    if not lines:
        return
    with st.expander(title, expanded=True):
        for line in lines:
            st.markdown(f"- {line}")


tab_options = [
    "🔴 Chờ cập nhật",
    "🟢 Chỉnh sửa đã đá",
    "⚙️ Vòng Knock-out",
    "🔒 Khóa trận",
    "📊 Ma trận → Sheet",
]
active_tab = st.radio("Chọn chức năng:", tab_options, horizontal=True, key="active_tab", label_visibility="collapsed")
st.write("---")

if active_tab == tab_options[0]:
    st.markdown('<div class="content-card-title">Các trận chờ kết quả</div>', unsafe_allow_html=True)
    display_limit = st.slider("Số trận hiển thị", min_value=5, max_value=50, value=15, step=5)
    batch = pending_matches.head(display_limit)

    with st.form("update_score_form"):
        admin_inputs, missing, zero_warn = _collect_confirmed_scores(batch, "real", require_score=True)

        if admin_inputs:
            preview = []
            for _, row in batch.iterrows():
                m_id = _match_id(row)
                if m_id in admin_inputs:
                    ra, rb, adv, _ = admin_inputs[m_id]
                    preview.append(_score_preview_line(row["team_a"], row["team_b"], ra, rb, adv))
            _render_submit_preview(preview, f"📋 Sẽ cập nhật {len(admin_inputs)} trận")

        if st.form_submit_button("🔥 Cập nhật lên Cloud", type="primary", width="stretch"):
            if missing:
                st.warning("Một số trận đã xác nhận nhưng chưa nhập tỉ số: " + "; ".join(missing))
            elif not admin_inputs:
                st.warning("Chưa xác nhận trận nào!")
            elif zero_warn:
                st.warning("⚠️ Có trận 0–0 — kiểm tra lại: " + "; ".join(zero_warn))
            else:
                st.session_state["success_msg"] = f"✅ Đã cập nhật {len(admin_inputs)} trận thành công!"
                _apply_admin_updates(admin_inputs, "score")

elif active_tab == tab_options[1]:
    st.markdown('<div class="content-card-title">Chỉnh sửa trận đã có kết quả</div>', unsafe_allow_html=True)
    if finished_matches.empty:
        st.info("Chưa có trận nào được cập nhật kết quả.")
    else:
        display_limit = st.slider(
            "Số trận hiển thị",
            min_value=5,
            max_value=50,
            value=15,
            step=5,
            key="edit_display_limit",
        )
        batch = finished_matches.head(display_limit)

        with st.form("edit_score_form"):
            edit_inputs, missing, _ = _collect_confirmed_scores(batch, "edit", require_score=False)

            if edit_inputs:
                preview = []
                for _, row in batch.iterrows():
                    m_id = _match_id(row)
                    if m_id in edit_inputs:
                        ra, rb, adv, _ = edit_inputs[m_id]
                        preview.append(_score_preview_line(row["team_a"], row["team_b"], ra, rb, adv))
                _render_submit_preview(preview, f"📋 Sẽ sửa {len(edit_inputs)} trận")

            if st.form_submit_button("💾 Lưu thay đổi", type="primary", width="stretch"):
                if missing:
                    st.warning("Một số trận đã xác nhận nhưng thiếu tỉ số.")
                elif not edit_inputs:
                    st.warning("Chưa chọn trận nào để sửa.")
                else:
                    st.session_state["success_msg"] = f"✅ Đã sửa {len(edit_inputs)} trận thành công!"
                    _apply_admin_updates(edit_inputs, "score")

elif active_tab == tab_options[2]:
    st.markdown('<div class="content-card-title">Cài đặt cặp đấu Knock-out</div>', unsafe_allow_html=True)
    knockout_matches = knockout_matches_sorted.copy()
    display_limit = st.slider(
        "Số trận hiển thị",
        min_value=5,
        max_value=50,
        value=min(15, len(knockout_matches)),
        step=5,
        key="ko_display_limit",
    )
    batch = knockout_matches.head(display_limit)

    with st.form("setup_knockout_form"):
        setup_inputs = {}
        preview = []
        for _, row in batch.iterrows():
            m_id = _match_id(row)
            idx_a = team_names_list.index(row["team_a"]) if row["team_a"] in team_names_list else 0
            idx_b = team_names_list.index(row["team_b"]) if row["team_b"] in team_names_list else 0

            st.markdown(f"**🛡️ Trận {row['match_number']} ({row['match_label']})**")
            col1, col2, col3, col4 = st.columns([2, 0.5, 2, 1])
            with col1:
                sel_a = st.selectbox("Nhà", team_names_list, index=idx_a, key=f"ko_a_{m_id}", label_visibility="collapsed")
            with col2:
                st.markdown("<h4 style='text-align:center;margin:0;'>VS</h4>", unsafe_allow_html=True)
            with col3:
                sel_b = st.selectbox("Khách", team_names_list, index=idx_b, key=f"ko_b_{m_id}", label_visibility="collapsed")
            with col4:
                is_confirmed = st.checkbox("Xác nhận", key=f"ko_confirm_{m_id}")

            if is_confirmed:
                setup_inputs[m_id] = (sel_a, sel_b)
                preview.append(f"Trận {row['match_number']}: {sel_a} vs {sel_b}")
            st.write("---")

        if preview:
            _render_submit_preview(preview, f"📋 Sẽ cập nhật {len(preview)} cặp đấu")

        if st.form_submit_button("💾 Lưu cặp đấu", type="primary", width="stretch"):
            if not setup_inputs:
                st.warning("Chưa xác nhận cặp đấu nào!")
            else:
                st.session_state["success_msg"] = f"🏆 Đã cập nhật {len(setup_inputs)} cặp đấu Knock-out!"
                _apply_admin_updates(setup_inputs, "knockout")

elif active_tab == tab_options[3]:
    st.markdown('<div class="content-card-title">🔒 Quản lý khóa dự đoán</div>', unsafe_allow_html=True)
    to_lock_matches = to_lock_matches_sorted.copy()

    if to_lock_matches.empty:
        st.info("Tất cả trận đã có kết quả.")
    else:
        display_limit = st.slider(
            "Số trận hiển thị",
            min_value=5,
            max_value=50,
            value=15,
            step=5,
            key="lock_display_limit",
        )
        batch = to_lock_matches.head(display_limit)

        with st.form("lock_matches_form"):
            lock_inputs = {}
            preview = []
            for _, row in batch.iterrows():
                m_id = _match_id(row)
                is_currently_locked = str(row["is_locked"]).strip().upper() == "TRUE"
                col1, col2 = st.columns([3, 1])
                kickoff = _kickoff_label(row)
                kickoff_suffix = f" · {kickoff}" if kickoff else ""
                with col1:
                    st.markdown(f"**⚽ Trận {row['match_number']}: {row['team_a']} vs {row['team_b']}**{kickoff_suffix}")
                with col2:
                    lock_check = st.checkbox("Khóa", value=is_currently_locked, key=f"lock_{m_id}")
                lock_inputs[m_id] = lock_check
                if lock_check != is_currently_locked:
                    state = "Khóa" if lock_check else "Mở"
                    preview.append(f"Trận {row['match_number']}: {row['team_a']} vs {row['team_b']} → {state}")
                st.write("---")

            if preview:
                _render_submit_preview(preview, f"📋 Sẽ thay đổi {len(preview)} trận")

            if st.form_submit_button("🛡️ Cập nhật trạng thái khóa", type="primary", width="stretch"):
                changed = {}
                for _, row in batch.iterrows():
                    m_id = _match_id(row)
                    was_locked = str(row["is_locked"]).strip().upper() == "TRUE"
                    now_locked = lock_inputs.get(m_id, was_locked)
                    if now_locked != was_locked:
                        changed[m_id] = now_locked
                if not changed:
                    st.warning("Không có thay đổi nào so với trạng thái hiện tại.")
                else:
                    st.session_state["success_msg"] = f"🛡️ Đã cập nhật {len(changed)} trận!"
                    _apply_admin_updates(changed, "lock")

elif active_tab == tab_options[4]:
    st.markdown('<div class="content-card-title">📊 Ma trận dự đoán → Google Sheet</div>', unsafe_allow_html=True)
    st.caption(
        "Đẩy toàn bộ dự đoán (trận × người chơi) lên tab "
        f"`{MATRIX_SHEET_NAME}` trên spreadsheet. Xem và lọc trên Google Sheets — không hiển thị ma trận trong app."
    )

    with custom_loader("Đang tải dữ liệu ma trận..."):
        users_df, preds_df, matrix_matches_df, matrix_teams_df = load_matrix_data()

    users_df["user_id"] = users_df["user_id"].astype(str)
    matrix_teams_df["id"] = matrix_teams_df["id"].astype(str)
    name_to_fifa = build_name_to_fifa(matrix_teams_df)

    n_matches = len(matrix_matches_df)
    n_users = len(users_df)
    n_preds = len(preds_df)
    st.info(f"**{n_matches}** trận × **{n_users}** người chơi · **{n_preds}** dự đoán đã ghi")

    if "matrix_last_updated" in st.session_state:
        st.caption(f"Cập nhật lần cuối: {st.session_state['matrix_last_updated']}")

    if st.button("Cập nhật ma trận lên Google Sheet", type="primary", key="push_matrix_btn"):
        with st.spinner("Đang ghi ma trận lên Google Sheet..."):
            matrix_df = build_prediction_matrix(
                matrix_matches_df,
                preds_df,
                users_df,
                matrix_teams_df,
                name_to_fifa,
            )
            sh = init_connection()
            write_worksheet_dataframe(sh, MATRIX_SHEET_NAME, matrix_df)
            ts = vietnam_timestamp()
            st.session_state["matrix_last_updated"] = ts
            load_matrix_data.clear()
            st.session_state["success_msg"] = (
                f"✅ Đã ghi ma trận ({len(matrix_df)} hàng × {len(matrix_df.columns)} cột) "
                f"lên tab `{MATRIX_SHEET_NAME}` lúc {ts}."
            )
            st.rerun()

    spreadsheet_id = st.secrets.get("spreadsheet_id", "")
    if spreadsheet_id:
        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        st.link_button("Mở Google Spreadsheet", sheet_url)
