import contextlib
import hashlib
import hmac
import html
import os
import re

import pandas as pd
import streamlit as st

from scoring import normalize_pred_outcome
from schedule_service import (
    format_date_compact_vn,
    format_time_vn,
    group_color,
    group_label_vn,
)
from team_flags import flag_img_html, team_line_html

DISPLAY_NAME_EMOJIS = [
    "⚽", "🏆", "🔥", "⭐", "🎯", "💪", "😎", "👑",
    "🦁", "🐯", "🦅", "🍺", "🎉", "❤️", "💙", "💚",
    "🤙", "✌️", "🥇", "🎮", "🧢", "🌟", "⚡", "🍀",
]

def _html(content: str):
    st.html(content)

def apply_global_styles():
    css_path = os.path.join("assets", "style.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Không tìm thấy file assets/style.css")

    _SIDEBAR_OVERLAY_BOOT = """
<script>
(function () {
  const topWin = window.top;
  const WC_SIDEBAR_OVERLAY_VERSION = 7;
  if (topWin.__wcSidebarOverlayVersion === WC_SIDEBAR_OVERLAY_VERSION) {
    topWin.__wcSidebarOverlaySync?.();
    return;
  }
  topWin.__wcSidebarOverlayVersion = WC_SIDEBAR_OVERLAY_VERSION;
  topWin.__wcSidebarOverlayInit = false;
  topWin.__wcSidebarOverlayObserver?.disconnect();
  topWin.document.getElementById("wc-sidebar-backdrop")?.remove();
  topWin.document.getElementById("wc-sidebar-overlay-boot")?.remove();
  const boot = topWin.document.createElement("script");
  boot.id = "wc-sidebar-overlay-boot";
  boot.textContent = `
(function () {
  let syncQueued = false;

  function isSidebarOpen() {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    return !!(sidebar && sidebar.getAttribute("aria-expanded") === "true");
  }

  function scheduleBackdropSync() {
    queueSyncBackdrop();
    setTimeout(queueSyncBackdrop, 180);
  }

  function collapseSidebar() {
    const btn =
      document.querySelector('[data-testid="stSidebarCollapseButton"] button') ||
      document.querySelector('[data-testid="stSidebarCollapseButton"]');
    if (!btn) return;

    const reactKey = Object.keys(btn).find((k) => k.startsWith("__reactProps"));
    const reactOnClick = reactKey && btn[reactKey]?.onClick;
    if (typeof reactOnClick === "function") {
      reactOnClick({
        preventDefault() {},
        stopPropagation() {},
        target: btn,
        currentTarget: btn,
        type: "click",
        nativeEvent: new MouseEvent("click", {
          bubbles: true,
          cancelable: true,
          view: window,
        }),
      });
      scheduleBackdropSync();
      return;
    }

    btn.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true, view: window })
    );
    scheduleBackdropSync();
  }

  function setSidebarOpenClass(open) {
    document.documentElement.classList.toggle("wc-sidebar-open", open);
    document.body.classList.toggle("wc-sidebar-open", open);
    document.querySelector('[data-testid="stApp"]')?.classList.toggle("wc-sidebar-open", open);
  }

  function syncBackdrop() {
    syncQueued = false;
    const open = isSidebarOpen();
    setSidebarOpenClass(open);

    let backdrop = document.getElementById("wc-sidebar-backdrop");
    if (!open) {
      backdrop?.remove();
      return;
    }

    if (!backdrop) {
      backdrop = document.createElement("button");
      backdrop.id = "wc-sidebar-backdrop";
      backdrop.type = "button";
      backdrop.setAttribute("aria-label", "Đóng menu");
      Object.assign(backdrop.style, {
        position: "fixed",
        inset: "0",
        background: "rgba(7, 11, 20, 0.55)",
        zIndex: "1000000",
        cursor: "pointer",
        border: "none",
        padding: "0",
        margin: "0",
        pointerEvents: "auto",
      });
      backdrop.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        collapseSidebar();
        scheduleBackdropSync();
      });
      document.body.appendChild(backdrop);
    }
  }

  function queueSyncBackdrop() {
    if (syncQueued) return;
    syncQueued = true;
    requestAnimationFrame(syncBackdrop);
  }

  function onOutsidePointer(e) {
    if (!isSidebarOpen()) return;
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    const target = e.target;
    if (!sidebar || !target) return;
    if (target.id === "wc-sidebar-backdrop") return;
    if (sidebar.contains(target)) return;
    if (target.closest?.('[data-testid="stSidebar"]')) return;
    if (target.closest?.('[data-testid="collapsedControl"]')) return;
    if (target.closest?.('[data-testid="stExpandSidebarButton"]')) return;
    if (target.closest?.('[data-testid="stSidebarCollapseButton"]')) return;
    e.preventDefault();
    e.stopPropagation();
    collapseSidebar();
    scheduleBackdropSync();
  }

  function handlePageChange() {
    const path = location.pathname;
    const prev = window.__wcSidebarLastPath;
    window.__wcSidebarLastPath = path;
    if (prev !== undefined && prev !== path) {
      document.getElementById("wc-sidebar-backdrop")?.remove();
      setSidebarOpenClass(false);
      if (isSidebarOpen()) collapseSidebar();
      setTimeout(queueSyncBackdrop, 120);
      return;
    }
    queueSyncBackdrop();
  }

  function bindSidebarObserver() {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    if (!sidebar || sidebar === window.__wcSidebarOverlayNode) return;
    window.__wcSidebarOverlayObserver?.disconnect();
    window.__wcSidebarOverlayNode = sidebar;
    window.__wcSidebarOverlayObserver = new MutationObserver(queueSyncBackdrop);
    window.__wcSidebarOverlayObserver.observe(sidebar, {
      attributes: true,
      attributeFilter: ["aria-expanded"],
    });
  }

  window.__wcSidebarOverlaySync = queueSyncBackdrop;
  window.__wcSidebarOverlayInit = true;

  window.addEventListener("resize", queueSyncBackdrop);
  window.addEventListener("popstate", handlePageChange);
  document.addEventListener("click", onOutsidePointer, true);
  document.addEventListener("touchend", onOutsidePointer, true);
  new MutationObserver(() => {
    handlePageChange();
    bindSidebarObserver();
  }).observe(document.body, { childList: true, subtree: true });

  handlePageChange();
  bindSidebarObserver();
  queueSyncBackdrop();
})();
`;
  topWin.document.head.appendChild(boot);
})();
</script>
"""

    import streamlit.components.v1 as components

    components.html(_SIDEBAR_OVERLAY_BOOT, height=0, scrolling=False)

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

def get_auth_signature(user_id: str) -> str:
    """Tạo chữ ký bảo mật cho user_id dựa trên secret key của server."""
    secret = st.secrets.get("password_salt", "MuoiMacDinh_@123").encode("utf-8")
    return hmac.new(secret, user_id.encode("utf-8"), hashlib.sha256).hexdigest()

def sync_auth_session():
    # 1. Khởi tạo session state nếu chưa có
    if "authenticated_user_id" not in st.session_state:
        st.session_state["authenticated_user_id"] = None

    # 2. Khôi phục đăng nhập từ URL (khi user F5) NHƯNG có check bảo mật
    if st.session_state["authenticated_user_id"] is None:
        url_uid = st.query_params.get("uid")
        url_sig = st.query_params.get("sig")
        
        if url_uid and url_sig:
            # Kiểm tra chữ ký có hợp lệ không
            expected_sig = get_auth_signature(url_uid)
            if hmac.compare_digest(url_sig, expected_sig):
                st.session_state["authenticated_user_id"] = url_uid
            else:
                # Chữ ký sai (có người đang cố tình đổi URL) -> Xóa sạch params
                st.query_params.clear()

    # 3. Ghi trạng thái đăng nhập hợp lệ lên URL để giữ kết nối khi F5
    if st.session_state["authenticated_user_id"] is not None:
        uid = st.session_state["authenticated_user_id"]
        st.query_params["uid"] = uid
        st.query_params["sig"] = get_auth_signature(uid)

def render_sidebar():
    with st.sidebar:
        _html(
            '<div class="sidebar-brand">'
            '<div class="sidebar-brand-icon">🏆</div>'
            '<div class="sidebar-brand-title">WC 2026</div>'
            '<div class="sidebar-brand-sub">Predictor Platform</div>'
            "</div>"
        )
        _html('<div class="sidebar-section-label"><span>Menu chính</span></div>')
        st.page_link("app.py", label="Trang chủ", icon="🏠")
        st.page_link("pages/1_Du_Doan.py", label="Khu vực dự đoán", icon="✍️")
        st.page_link("pages/3_Bang_Xep_Hang.py", label="Bảng xếp hạng", icon="🏆")
        st.page_link("pages/4_Xem_Lich_Thi_Dau.py", label="Lịch thi đấu", icon="🗓️")
        st.page_link("pages/5_Bang_Dau.py", label="Bảng đấu", icon="📊")
        st.page_link("pages/6_Bracket_Knockout.py", label="Bracket Knock-out", icon="🏅")
        st.page_link("pages/7_Tra_Cuu_Doi_Bong.py", label="Tra cứu đội hình", icon="👕")

        _html('<div class="sidebar-section-label sidebar-section-label--admin"><span>Admin</span></div>')
        st.page_link("pages/2_Lich_Thi_Dau.py", label="Góc của Elu", icon="⚙️")

        _html(
            '<div class="sidebar-tip">'
            '<div class="sidebar-tip-icon">!</div>'
            '<div class="sidebar-tip-copy">'
            '<strong>Chốt trước giờ bóng lăn</strong>'
            '<span>Trận bị khóa sẽ không nhận dự đoán mới.</span>'
            "</div>"
            "</div>"
        )

def render_page_header(title, subtitle="", variant="default", eyebrow=""):
    variant_class = f"page-header--{variant}" if variant != "default" else ""
    eyebrow_html = f'<div class="page-header-eyebrow">{html.escape(eyebrow)}</div>' if eyebrow else ""
    subtitle_html = f'<p class="page-header-subtitle">{html.escape(subtitle)}</p>' if subtitle else ""
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
        '<p class="page-header-subtitle">Dự đoán kết quả trận đấu — cùng tranh tài, cùng vui!</p>'
        "</div></div>"
    )

def render_stat_cards(stats: list[tuple[str, str, str]], *, row_class: str = ""):
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
    extra = f" {row_class.strip()}" if row_class.strip() else ""
    _html(f'<div class="stats-row{extra}">{"".join(cards)}</div>')

def render_home_cta_cards(cards: list[dict[str, str]]):
    items = []
    for card in cards:
        href = card.get("href", "#")
        icon = card.get("icon", "")
        title = card.get("title", "")
        desc = card.get("desc", "")
        tone = card.get("tone", "blue")
        cta = card.get("cta", "Mở")
        items.append(
            f'<a class="home-cta-card home-cta-card--{html.escape(tone)}" href="{html.escape(href)}">'
            f'<span class="home-cta-icon">{html.escape(icon)}</span>'
            f'<span class="home-cta-copy">'
            f'<strong>{html.escape(title)}</strong>'
            f'<small>{html.escape(desc)}</small>'
            f"</span>"
            f'<span class="home-cta-arrow">{html.escape(cta)} →</span>'
            f"</a>"
        )
    _html(f'<div class="action-grid">{"".join(items)}</div>')

def render_match_card(
    match_number,
    group_label,
    team_a,
    team_b,
    score_a,
    score_b,
    is_finished=False,
    team_a_fifa=None,
    team_b_fifa=None,
    name_to_fifa=None,
    variant="default",
):
    status_class = "match-card-status--done" if is_finished else "match-card-status--pending"
    status_text = "✅ Kết thúc" if is_finished else "⏳ Sắp đá"
    home_line = team_line_html(team_a, "a", fifa_code=team_a_fifa, name_to_fifa=name_to_fifa)
    away_line = team_line_html(team_b, "b", fifa_code=team_b_fifa, name_to_fifa=name_to_fifa)
    variant_class = f" match-card--{html.escape(str(variant))}" if variant != "default" else ""
    _html(
        f'<div class="match-card{variant_class}">'
        f'<div class="match-card-meta">'
        f'<div class="match-card-number">Trận {html.escape(str(match_number))}</div>'
        f'<div class="match-card-group">{html.escape(str(group_label))}</div>'
        f"</div>"
        f'<div class="match-card-team match-card-team--home">{home_line}</div>'
        f'<div class="match-card-score">{score_a} – {score_b}</div>'
        f'<div class="match-card-team match-card-team--away">{away_line}</div>'
        f'<div class="match-card-status {status_class}">{status_text}</div>'
        f"</div>"
    )


def render_fixture_day_header(date_label: str, match_count: int) -> None:
    count_label = f"{match_count} trận" if match_count != 1 else "1 trận"
    _html(
        f'<div class="fixture-day-header">'
        f'<span class="fixture-day-title">{html.escape(date_label)}</span>'
        f'<span class="fixture-day-count">{html.escape(count_label)}</span>'
        f"</div>"
    )


def render_fixture_row(
    *,
    match_number: int | str,
    kickoff_vn,
    team_a: str,
    team_b: str,
    team_a_fifa=None,
    team_b_fifa=None,
    name_to_fifa=None,
    venue_line: str | None = None,
    group_round: str | None = None,
    score_a: int = 0,
    score_b: int = 0,
    is_finished: bool = False,
) -> None:
    kickoff_dt = kickoff_vn.to_pydatetime() if hasattr(kickoff_vn, "to_pydatetime") else kickoff_vn
    time_primary = format_time_vn(kickoff_dt)
    date_compact = format_date_compact_vn(kickoff_dt)

    home_line = team_line_html(team_a, "a", fifa_code=team_a_fifa, name_to_fifa=name_to_fifa)
    away_line = team_line_html(team_b, "b", fifa_code=team_b_fifa, name_to_fifa=name_to_fifa)
    code_a = str(team_a_fifa or (name_to_fifa or {}).get(team_a, "")).strip().upper()
    code_b = str(team_b_fifa or (name_to_fifa or {}).get(team_b, "")).strip().upper()
    squad_links = ""
    if code_a:
        squad_links += f'<a class="fixture-squad-link" href="/Tra_Cuu_Doi_Bong?team={html.escape(code_a)}">{html.escape(code_a)}</a>'
    if code_b:
        if squad_links:
            squad_links += '<span class="fixture-squad-sep">·</span>'
        squad_links += f'<a class="fixture-squad-link" href="/Tra_Cuu_Doi_Bong?team={html.escape(code_b)}">{html.escape(code_b)}</a>'
    squad_html = f'<div class="fixture-squad-links">{squad_links}</div>' if squad_links else ""
    venue = html.escape(str(venue_line or "—"))
    grp_label = html.escape(group_label_vn(group_round))
    grp_tone = html.escape(group_color(group_round))
    status_class = "fixture-row--finished" if is_finished else "fixture-row--upcoming"
    result_html = (
        f'<div class="fixture-result">{score_a} – {score_b}</div>'
        if is_finished
        else '<div class="fixture-status">⏳ Sắp đá</div>'
    )

    _html(
        f'<div class="fixture-row {status_class}" style="--fixture-accent:{grp_tone};">'
        f'<div class="fixture-row-accent"></div>'
        f'<div class="fixture-row-time">'
        f'<div class="fixture-time-primary">{html.escape(time_primary)}</div>'
        f'<div class="fixture-time-date">{html.escape(date_compact)}</div>'
        f"</div>"
        f'<div class="fixture-row-match">'
        f'<div class="fixture-teams">'
        f"{home_line}"
        f'<span class="fixture-vs">vs</span>'
        f"{away_line}"
        f"</div>"
        f'<div class="fixture-venue">{venue}</div>'
        f"{squad_html}"
        f"</div>"
        f'<div class="fixture-row-meta">'
        f'<div class="fixture-group" style="color:{grp_tone};">'
        f'<span class="fixture-group-dot" style="background:{grp_tone};"></span>'
        f"{grp_label}"
        f"</div>"
        f'<div class="fixture-match-no">#{html.escape(str(match_number))}</div>'
        f"{result_html}"
        f"</div>"
        f"</div>"
    )


def render_fixture_schedule_open() -> None:
    _html('<div class="fixture-schedule">')


def render_fixture_schedule_close() -> None:
    _html("</div>")


def render_podium(top3: list[tuple[str, int]]):
    if not top3:
        return
    medals, bars = ["🥇", "🥈", "🥉"], ["1", "2", "3"]
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


def render_leaderboard_insight(insight: dict) -> None:
    if not insight:
        return
    tie_note = ""
    if insight.get("top_tie_count", 0) > 3:
        tie_note = (
            f'<span class="lb-insight-chip lb-insight-chip--gold">'
            f'{insight["top_tie_count"]} người đồng hạng 1</span>'
        )
    _html(
        f'<div class="lb-insight">'
        f'<div class="lb-insight-main">'
        f'<span class="lb-insight-label">Trận mới nhất</span>'
        f'<strong class="lb-insight-match">#{html.escape(str(insight["match_number"]))} · '
        f'{html.escape(str(insight["matchup"]))}</strong>'
        f"</div>"
        f'<div class="lb-insight-stats">'
        f'<span class="lb-insight-chip lb-insight-chip--ok">✅ {insight["correct"]} đúng</span>'
        f'<span class="lb-insight-chip lb-insight-chip--bad">❌ {insight["wrong"]} sai</span>'
        f'<span class="lb-insight-chip lb-insight-chip--muted">⏭ {insight["missed"]} bỏ lỡ</span>'
        f"{tie_note}"
        f"</div></div>"
    )


def render_leaderboard_podium(entries: list[dict]) -> None:
    if not entries:
        return
    bar_map = {1: "1", 2: "2", 3: "3"}
    medal_map = {1: "🥇", 2: "🥈", 3: "🥉"}
    order = [1, 0, 2] if len(entries) >= 3 else list(range(len(entries)))
    items = []
    for slot in order:
        if slot >= len(entries):
            continue
        entry = entries[slot]
        rank = int(entry["rank"])
        bar = bar_map.get(rank, str(rank))
        medal = medal_map.get(rank, f"#{rank}")
        tie = int(entry.get("tie_count", 1))
        tie_html = f'<div class="podium-tie">+{tie - 1} đồng hạng</div>' if tie > 1 else ""
        items.append(
            f'<div class="podium-item podium-item--rank-{bar}">'
            f'<div class="podium-bar podium-bar--{bar}">{medal}</div>'
            f'<div class="podium-name">{html.escape(str(entry["name"]))}</div>'
            f'<div class="podium-pts">{int(entry["points"])} điểm</div>'
            f"{tie_html}"
            f"</div>"
        )
    _html(f'<div class="podium podium--leaderboard">{"".join(items)}</div>')


def render_leaderboard_table(rows: list[dict], highlight_user_id: str | None = None) -> None:
    body = []
    for row in rows:
        uid = str(row.get("user_id", ""))
        row_class = "lb-row lb-row--me" if highlight_user_id and uid == str(highlight_user_id) else "lb-row"
        rank = row.get("rank_label", row.get("rank", ""))
        fines = int(row.get("fines", 0))
        fine_class = "lb-cell-fine lb-cell-fine--zero" if fines == 0 else "lb-cell-fine lb-cell-fine--due"
        hit = row.get("hit_rate", 0)
        played = int(row.get("played", 0))
        correct = int(row.get("correct", 0))
        missed = int(row.get("missed", 0))
        accuracy = f"{correct}/{played}" if played else "—"
        me_badge = '<span class="lb-you">Bạn</span>' if row_class.endswith("--me") else ""
        body.append(
            f'<div class="{row_class}">'
            f'<span class="lb-cell-rank">{html.escape(str(rank))}</span>'
            f'<span class="lb-cell-name">{html.escape(str(row["name"]))}{me_badge}</span>'
            f'<span class="lb-cell-pts">{int(row["points"])}</span>'
            f'<span class="{fine_class}">{fines}k</span>'
            f'<span class="lb-cell-acc">{html.escape(str(accuracy))}</span>'
            f'<span class="lb-cell-rate">{hit:.0f}%</span>'
            f'<span class="lb-cell-miss">{missed if missed else "—"}</span>'
            f"</div>"
        )
    head = (
        '<div class="lb-list-head">'
        '<span class="lb-col-rank">Hạng</span>'
        '<span class="lb-col-name">Người chơi</span>'
        '<span class="lb-col-pts">Điểm</span>'
        '<span class="lb-col-fine">Phạt</span>'
        '<span class="lb-col-acc">Đúng</span>'
        '<span class="lb-col-rate">Tỉ lệ</span>'
        '<span class="lb-col-miss">Bỏ lỡ</span>'
        "</div>"
    )
    _html(f'<div class="lb-table-marker" aria-hidden="true"></div><div class="lb-list">{head}{"".join(body)}</div>')


def render_squad_team_header(
    team_name: str,
    fifa_code: str,
    group_letter: str,
    summary: dict,
    name_to_fifa: dict | None = None,
) -> None:
    from schedule_service import GROUP_COLORS

    flag = flag_img_html(fifa_code=fifa_code, team_name=team_name, name_to_fifa=name_to_fifa, size="md")
    group = str(group_letter or "").strip().upper()
    group_html = ""
    if group:
        tone = GROUP_COLORS.get(group, "#64748b")
        group_html = (
            f'<span class="squad-group-badge" style="--squad-group-color:{html.escape(tone)};">'
            f"BẢNG {html.escape(group)}</span>"
        )
    _html(
        f'<div class="squad-team-header">'
        f'<div class="squad-team-main">{flag}'
        f'<div class="squad-team-copy">'
        f'<div class="squad-team-name">{html.escape(team_name)}</div>'
        f'<div class="squad-team-meta">{html.escape(fifa_code)} · 26 cầu thủ {group_html}</div>'
        f"</div></div>"
        f'<div class="squad-team-stats">'
        f'<span class="squad-stat"><strong>{summary.get("count", 0)}</strong><small>Cầu thủ</small></span>'
        f'<span class="squad-stat"><strong>{summary.get("total_goals", 0)}</strong><small>Bàn (NT)</small></span>'
        f'<span class="squad-stat"><strong>{summary.get("total_caps", 0)}</strong><small>Caps</small></span>'
        f'<span class="squad-stat"><strong>{summary.get("avg_height", 0)}</strong><small>cm TB</small></span>'
        f"</div></div>"
    )


def render_squad_player_table(rows_by_position: dict[str, list[dict]]) -> None:
    from players_service import POSITION_LABELS

    if not rows_by_position:
        _html('<div class="squad-empty">Không có cầu thủ phù hợp bộ lọc.</div>')
        return

    sections = []
    for pos, rows in rows_by_position.items():
        label = POSITION_LABELS.get(pos, pos)
        body = []
        for row in rows:
            body.append(
                f'<div class="squad-row">'
                f'<span class="squad-cell-name">{html.escape(str(row.get("player_name", "")))}</span>'
                f'<span class="squad-cell-club">{html.escape(str(row.get("club", "")))}</span>'
                f'<span class="squad-cell-dob">{html.escape(str(row.get("dob", "")))}</span>'
                f'<span class="squad-cell-h">{int(row.get("height_cm", 0)) or "—"}</span>'
                f'<span class="squad-cell-caps">{int(row.get("caps", 0))}</span>'
                f'<span class="squad-cell-goals">{int(row.get("goals", 0))}</span>'
                f"</div>"
            )
        head = (
            '<div class="squad-list-head">'
            '<span class="squad-col-name">Tên</span>'
            '<span class="squad-col-club">CLB</span>'
            '<span class="squad-col-dob">Sinh</span>'
            '<span class="squad-col-h">Cao</span>'
            '<span class="squad-col-caps">Caps</span>'
            '<span class="squad-col-goals">Bàn</span>'
            "</div>"
        )
        sections.append(
            f'<div class="squad-position-block">'
            f'<div class="squad-position-title">{html.escape(label)} <span>({len(rows)})</span></div>'
            f'<div class="squad-list">{head}{"".join(body)}</div>'
            f"</div>"
        )
    _html(f'<div class="squad-page-marker" aria-hidden="true"></div><div class="squad-sections">{"".join(sections)}</div>')


def render_squad_mini_panel(
    team_name: str,
    fifa_code: str,
    top_rows: list[dict],
    name_to_fifa: dict | None = None,
) -> None:
    flag = flag_img_html(fifa_code=fifa_code, team_name=team_name, name_to_fifa=name_to_fifa, size="sm")
    squad_url = f"/Tra_Cuu_Doi_Bong?team={html.escape(fifa_code)}"
    players_html = ""
    for row in top_rows:
        players_html += (
            f'<li><span class="squad-mini-name">{html.escape(str(row.get("player_name", "")))}</span>'
            f'<span class="squad-mini-meta">{int(row.get("goals", 0))} bàn · {int(row.get("caps", 0))} caps</span></li>'
        )
    if not players_html:
        players_html = '<li class="squad-mini-empty">Chưa có dữ liệu</li>'
    _html(
        f'<div class="squad-mini-panel">'
        f'<div class="squad-mini-head">{flag}<strong>{html.escape(team_name)}</strong></div>'
        f'<ul class="squad-mini-list">{players_html}</ul>'
        f'<a class="squad-mini-link" href="{squad_url}">Xem đội hình →</a>'
        f"</div>"
    )


def render_login_branding(
    title: str = "Đăng nhập",
    subtitle: str = "Nhập tên hiển thị hoặc mã ID để tham gia dự đoán World Cup 2026",
    eyebrow: str = "Prediction Access",
    icon: str = "🔐",
):
    _html(
        f'<div class="login-shell">'
        f'<div class="login-panel-header">'
        f'<div class="login-panel-glow"></div>'
        f'<div class="login-eyebrow">{html.escape(eyebrow)}</div>'
        f'<div class="login-icon-ring">{html.escape(icon)}</div>'
        f'<h2 class="login-title">{html.escape(title)}</h2>'
        f'<p class="login-subtitle">{html.escape(subtitle)}</p>'
        f'<div class="login-chips">'
        f'<span class="login-chip">⚽ Dự đoán kết quả</span>'
        f'<span class="login-chip">🏆 Bảng xếp hạng</span>'
        f'<span class="login-chip">🗓️ 104 trận</span>'
        f"</div></div></div>"
    )

def render_login_footer():
    _html(
        '<div class="login-shell login-shell--footer">'
        '<div class="login-footer">'
        '<span class="login-footer-item">🛡️Elucidator&Bean&Envy</span>'
        '<span class="login-footer-divider">·</span>'
        '<span class="login-footer-item">Chưa có tài khoản? Liên hệ admin</span>'
        "</div></div>"
    )

def get_user_avatar_display(user_name: str, avatar_icon: str | None = None) -> str:
    if avatar_icon and str(avatar_icon).strip(): return str(avatar_icon).strip()[:2]
    match = re.match(r"^[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", user_name or "")
    if match: return match.group(0)[:2]
    clean = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", "", user_name or "").strip()
    return clean[0].upper() if clean else "?"

def init_name_draft(user_id: str, current_name: str) -> str:
    draft_key, owner_key = f"name_draft_{user_id}", f"name_draft_owner_{user_id}"
    if draft_key not in st.session_state or st.session_state.get(owner_key) != current_name:
        st.session_state[draft_key] = current_name
        st.session_state[owner_key] = current_name
    return draft_key

def _draft_name(draft_key: str, fallback: str) -> str:
    return str(st.session_state.get(draft_key, fallback) or fallback)

def _apply_name_draft_pending(draft_key: str) -> None:
    pending_key = f"{draft_key}_pending"
    if pending_key in st.session_state:
        st.session_state[draft_key] = st.session_state.pop(pending_key)

def _queue_name_draft(draft_key: str, value: str) -> None:
    st.session_state[f"{draft_key}_pending"] = value
    st.rerun()

def render_emoji_name_picker(draft_key: str, saved_name: str):
    _html(
        '<div class="emoji-picker-shell">'
        '<div class="emoji-picker-label">Chọn icon (bấm để thêm vào tên)</div>'
        '</div>'
    )
    idx_key = f"emoji_pick_idx_{draft_key}"
    pick_key = f"emoji_pick_{draft_key}_{st.session_state.get(idx_key, 0)}"
    picked = st.pills(
        "Icon",
        options=DISPLAY_NAME_EMOJIS,
        selection_mode="single",
        key=pick_key,
        label_visibility="collapsed",
    )
    if picked:
        st.session_state[idx_key] = st.session_state.get(idx_key, 0) + 1
        _queue_name_draft(draft_key, _draft_name(draft_key, saved_name) + picked)

    _html('<div class="emoji-action-marker"></div>')
    btn1, btn2, btn3 = st.columns(3, gap="small")
    with btn1:
        if st.button("⌫ Xóa", key=f"emoji_back_{draft_key}", width="stretch"):
            _queue_name_draft(draft_key, _draft_name(draft_key, saved_name)[:-1])
    with btn2:
        if st.button("↩️ Reset", key=f"emoji_reset_{draft_key}", width="stretch"):
            _queue_name_draft(draft_key, saved_name)
    with btn3:
        if st.button("🧹 Thêm", key=f"emoji_clear_{draft_key}", width="stretch"):
            cleaned = re.sub(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]+", "", _draft_name(draft_key, saved_name)).strip()
            _queue_name_draft(draft_key, cleaned or saved_name)

    _html(
        f'<div class="name-preview">'
        f'<span class="name-preview-label">Xem trước</span>'
        f'<span class="name-preview-value">{html.escape(_draft_name(draft_key, saved_name))}</span>'
        f"</div>"
    )

def _get_col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s

def _update_user_row(init_connection_fn, pd_module, user_id, col_name, new_val):
    sh = init_connection_fn()
    ws = sh.worksheet("users")
    data = ws.get_all_values()
    df = pd_module.DataFrame(data[1:], columns=data[0]) if data else pd_module.DataFrame()
    df.replace("", pd_module.NA, inplace=True)
    idx = df.index[df["user_id"].astype(str) == user_id][0]
    df.loc[idx, col_name] = new_val
    
    row_data = df.iloc[idx].fillna("").values.tolist()
    sheet_row = int(idx) + 2
    col_letter = _get_col_letter(len(row_data))
    ws.batch_update([{'range': f'A{sheet_row}:{col_letter}{sheet_row}', 'values': [row_data]}])

def render_user_account_panel(
    user_id: str, user_name: str, user_names: list[str], stored_password_hash: str,
    hash_password_fn, init_connection_fn, set_with_dataframe_fn, pd_module,
):
    avatar_char = get_user_avatar_display(user_name)
    _html(
        f'<div class="account-panel">'
        f'<div class="account-panel-header">'
        f'<div class="account-avatar" title="Icon hiển thị từ tên">{html.escape(avatar_char)}</div>'
        f'<div class="account-meta">'
        f'<div class="account-label">Đang đăng nhập</div>'
        f'<div class="account-name">{html.escape(user_name)}</div>'
        f"</div></div></div>"
    )

    draft_key = init_name_draft(user_id, user_name)

    with st.expander("📝 Đổi tên hiển thị", expanded=False):
        _apply_name_draft_pending(draft_key)
        with st.container(border=True):
            st.text_input("Tên hiển thị mới:", key=draft_key)
            render_emoji_name_picker(draft_key, user_name)

        if st.button("💾 Cập nhật tên", key=f"save_name_{user_id}", type="primary", width="stretch"):
            new_name_clean = _draft_name(draft_key, user_name).strip()
            if not new_name_clean: st.error("❌ Tên không được để trống!")
            elif new_name_clean == user_name: st.warning("⚠️ Tên mới giống hệt tên cũ.")
            elif new_name_clean in user_names: st.error("❌ Tên này đã có người sử dụng!")
            else:
                _update_user_row(init_connection_fn, pd_module, user_id, "name", new_name_clean)
                st.cache_data.clear()
                st.session_state[f"name_draft_owner_{user_id}"] = new_name_clean
                st.session_state[f"{draft_key}_pending"] = new_name_clean
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
                elif new_pass != confirm_pass: st.error("❌ Mật khẩu mới không khớp nhau!")
                elif len(new_pass) < 4: st.error("⚠️ Mật khẩu phải có ít nhất 4 ký tự.")
                else:
                    _update_user_row(init_connection_fn, pd_module, user_id, "password", hash_password_fn(new_pass))
                    st.cache_data.clear()
                    st.success("✅ Đổi mật khẩu thành công!")

    if st.button("🚪 Đăng xuất", type="primary", key="logout_btn", width="stretch"):
        st.session_state["authenticated_user_id"] = None
        st.query_params.clear()
        st.rerun()

def outcome_segment_label(outcome: str, team_a: str, team_b: str) -> str:
    """Compact labels — team names live in the card header."""
    if outcome == "A":
        return "A thắng"
    if outcome == "B":
        return "B thắng"
    return "Hòa"


def render_outcome_picker(
    team_a: str,
    team_b: str,
    default_outcome: str,
    widget_key: str,
) -> str:
    """Full-width segmented A/D/B control."""
    _html('<div class="pred-card-body"><div class="outcome-picker-shell"></div>')

    options = ["A", "D", "B"]
    default = normalize_pred_outcome(default_outcome) or "D"
    if default not in options:
        default = "D"

    if widget_key in st.session_state:
        migrated = normalize_pred_outcome(st.session_state[widget_key])
        if migrated:
            if st.session_state[widget_key] != migrated:
                st.session_state[widget_key] = migrated
        else:
            del st.session_state[widget_key]

    control_kwargs = {
        "label": "Kết quả dự đoán",
        "options": options,
        "format_func": lambda x: outcome_segment_label(x, team_a, team_b),
        "label_visibility": "collapsed",
        "width": "stretch",
        "key": widget_key,
    }
    if widget_key not in st.session_state:
        control_kwargs["default"] = default

    picked = st.segmented_control(**control_kwargs)
    return normalize_pred_outcome(picked or default) or default


def render_pred_confirm_checkbox(dynamic_key: str) -> bool:
    _html('<div class="pred-confirm-marker"></div>')
    confirmed = st.toggle("Chốt trận này", key=dynamic_key, width="stretch")
    _html('</div>')
    return confirmed


def render_pred_match_header(
    match_number,
    team_a,
    team_b,
    group_round=None,
    stage_id=None,
    is_knockout=False,
    has_saved_pred: bool = False,
    pred_badge: str | None = None,
    team_a_fifa=None,
    team_b_fifa=None,
    name_to_fifa=None,
    kickoff_vn=None,
):
    from schedule_service import match_round_color, match_round_label_vn

    round_label = match_round_label_vn(group_round=group_round, stage_id=stage_id)
    round_tone = match_round_color(group_round=group_round, stage_id=stage_id)
    ko_badge = '<span class="pred-ko-badge">KNOCK-OUT</span>' if is_knockout else ""
    if pred_badge == "saved":
        status_badge = '<span class="pred-saved-badge">Đã dự đoán</span>'
    elif pred_badge == "draft":
        status_badge = '<span class="pred-draft-badge">Chưa lưu</span>'
    elif has_saved_pred:
        status_badge = '<span class="pred-saved-badge">Đã dự đoán</span>'
    else:
        status_badge = ""
    side_a = team_line_html(team_a, "a", fifa_code=team_a_fifa, name_to_fifa=name_to_fifa)
    side_b = team_line_html(team_b, "b", fifa_code=team_b_fifa, name_to_fifa=name_to_fifa)
    kickoff_html = ""
    if kickoff_vn is not None:
        try:
            kickoff_dt = kickoff_vn.to_pydatetime() if hasattr(kickoff_vn, "to_pydatetime") else kickoff_vn
            kickoff_html = (
                f'<div class="pred-card-kickoff">'
                f'<div class="pred-kickoff-primary">'
                f'🕐 {html.escape(format_time_vn(kickoff_dt))}'
                f' · {html.escape(format_date_compact_vn(kickoff_dt))}'
                f"</div>"
                f"</div>"
            )
        except (AttributeError, TypeError, ValueError):
            kickoff_html = ""
    _html(
        f'<div class="pred-card-header">'
        f'<div class="pred-card-meta">'
        f'<span class="pred-card-number">Trận {html.escape(str(match_number))}</span>'
        f'<span class="pred-card-group" style="color:{html.escape(round_tone)};">'
        f'<span class="pred-card-group-dot" style="background:{html.escape(round_tone)};"></span>'
        f'{html.escape(round_label)}</span>'
        f"{ko_badge}{status_badge}"
        f"</div>"
        f"{kickoff_html}"
        f'<div class="pred-card-matchup">'
        f'<div class="pred-card-side pred-card-side--a">'
        f'<span class="pred-side-tag">Đội A</span>'
        f'<span class="pred-side-name">{side_a}</span>'
        f"</div>"
        f'<div class="pred-card-vs-ring"><span>VS</span></div>'
        f'<div class="pred-card-side pred-card-side--b">'
        f'<span class="pred-side-tag">Đội B</span>'
        f'<span class="pred-side-name">{side_b}</span>'
        f"</div>"
        f"</div>"
        f'<div class="pred-card-divider"></div>'
        f"</div>"
    )

_PRED_HISTORY_MOBILE_PAGE_SIZE = 20


def _pred_history_verdict_class(verdict: str) -> str:
    text = str(verdict)
    if "❌" in text:
        return "pred-hist-row-verdict pred-hist-row-verdict--bad"
    if "⏳" in text:
        return "pred-hist-row-verdict pred-hist-row-verdict--pending"
    return "pred-hist-row-verdict pred-hist-row-verdict--ok"


def _filter_pred_history_df(history_df, filt: str):
    if filt == "Chưa có kết quả":
        return history_df[history_df["Kết quả"].astype(str).str.contains("⏳", na=False)]
    if filt == "Đã chấm điểm":
        return history_df[~history_df["Kết quả"].astype(str).str.contains("⏳", na=False)]
    return history_df


def _pred_history_matchup_cell(row) -> str:
    if "Trận đấu_html" in row.index and pd.notna(row.get("Trận đấu_html")):
        return str(row["Trận đấu_html"])
    return html.escape(str(row.get("Trận đấu", "—")))


def _pred_history_pick_cell(row) -> str:
    if "Dự đoán_html" in row.index and pd.notna(row.get("Dự đoán_html")):
        return str(row["Dự đoán_html"])
    return html.escape(str(row.get("Dự đoán", "—")))


def _build_pred_history_compact_html(history_df) -> str:
    rows = []
    for _, row in history_df.iterrows():
        verdict = str(row["Kết quả"])
        rows.append(
            f'<div class="pred-hist-row">'
            f'<span class="pred-hist-row-no">{int(row["match_number"])}</span>'
            f'<span class="pred-hist-row-matchup">{_pred_history_matchup_cell(row)}</span>'
            f'<span class="pred-hist-row-pick">{_pred_history_pick_cell(row)}</span>'
            f'<span class="{_pred_history_verdict_class(verdict)}">{html.escape(verdict)}</span>'
            f"</div>"
        )
    head = (
        '<div class="pred-hist-list-head">'
        '<span class="pred-hist-col-no">Trận</span>'
        '<span class="pred-hist-col-match">Cặp đấu</span>'
        '<span class="pred-hist-col-pick">Dự đoán</span>'
        '<span class="pred-hist-col-kq">Kết quả</span>'
        "</div>"
    )
    return f'<div class="pred-hist-list">{head}{"".join(rows)}</div>'


def _build_pred_history_desktop_html(history_df) -> str:
    rows = []
    for _, row in history_df.iterrows():
        verdict = str(row["Kết quả"])
        rows.append(
            f'<div class="pred-hist-row pred-hist-row--desktop">'
            f'<span class="pred-hist-row-no">{int(row["match_number"])}</span>'
            f'<span class="pred-hist-row-group">{html.escape(str(row["Bảng"]))}</span>'
            f'<span class="pred-hist-row-matchup">{_pred_history_matchup_cell(row)}</span>'
            f'<span class="pred-hist-row-pick">{_pred_history_pick_cell(row)}</span>'
            f'<span class="{_pred_history_verdict_class(verdict)}">{html.escape(verdict)}</span>'
            f"</div>"
        )
    head = (
        '<div class="pred-hist-list-head pred-hist-list-head--desktop">'
        '<span class="pred-hist-col-no">Trận</span>'
        '<span class="pred-hist-col-group">Bảng</span>'
        '<span class="pred-hist-col-match">Trận đấu</span>'
        '<span class="pred-hist-col-pick">Dự đoán</span>'
        '<span class="pred-hist-col-kq">Kết quả</span>'
        "</div>"
    )
    return f'<div class="pred-hist-list pred-hist-list--desktop">{head}{"".join(rows)}</div>'


def slice_pred_history_page(history_df, filt: str, page: int, page_size: int = _PRED_HISTORY_MOBILE_PAGE_SIZE):
    """Filter + paginate history for mobile list."""
    filtered = _filter_pred_history_df(history_df, filt)
    total = len(filtered)
    if total == 0:
        return filtered, 0, 0
    page_count = (total + page_size - 1) // page_size
    page = max(1, min(int(page), page_count))
    start = (page - 1) * page_size
    return filtered.iloc[start : start + page_size], total, page_count


def pred_history_page_label(page: int, total: int, page_size: int = _PRED_HISTORY_MOBILE_PAGE_SIZE) -> str:
    if total <= 0:
        return "0 trận"
    return f"Trận {(page - 1) * page_size + 1}–{min(page * page_size, total)} / {total}"


def render_pred_history_mobile_list(history_df):
    """Single HTML block — must not interleave Streamlit widgets."""
    if history_df.empty:
        _html('<div class="pred-hist-empty">Không có trận nào trong bộ lọc này.</div>')
        return
    _html(_build_pred_history_compact_html(history_df))


def render_pred_history_mobile_section(history_df):
    """Mobile history: filter + safe pagination + compact list (no st.select_slider)."""
    _html('<div class="pred-history-mobile-marker" aria-hidden="true"></div>')
    filt = st.radio(
        "Lọc lịch sử",
        ["Tất cả", "Chưa có kết quả", "Đã chấm điểm"],
        horizontal=True,
        key="pred_hist_filter",
        label_visibility="collapsed",
    )
    prev_filt = st.session_state.get("_pred_hist_filter_prev")
    if prev_filt != filt:
        st.session_state["_pred_hist_filter_prev"] = filt
        st.session_state["pred_hist_page"] = 1

    page = max(1, int(st.session_state.get("pred_hist_page", 1)))
    _, total_filtered, page_count = slice_pred_history_page(history_df, filt, page)
    if page_count and page > page_count:
        page = 1
        st.session_state["pred_hist_page"] = 1

    if page_count > 1:
        nav_l, nav_m, nav_r = st.columns([1, 2.2, 1])
        with nav_l:
            if st.button("◀", key="pred_hist_prev", use_container_width=True, disabled=page <= 1):
                st.session_state["pred_hist_page"] = page - 1
                st.rerun()
        with nav_m:
            st.markdown(
                f'<div class="pred-hist-page-label">{html.escape(pred_history_page_label(page, total_filtered))}</div>',
                unsafe_allow_html=True,
            )
        with nav_r:
            if st.button("▶", key="pred_hist_next", use_container_width=True, disabled=page >= page_count):
                st.session_state["pred_hist_page"] = page + 1
                st.rerun()
    else:
        _html('<div class="pred-history-mobile-page-slot" aria-hidden="true"></div>')

    mobile_slice, _, _ = slice_pred_history_page(history_df, filt, page)
    render_pred_history_mobile_list(mobile_slice)


def render_pred_history_desktop_table(history_df):
    """Desktop HTML table with flagcdn images (hidden on mobile via CSS)."""
    _html('<div class="pred-history-desktop-marker" aria-hidden="true"></div>')
    if history_df.empty:
        _html('<div class="pred-hist-empty">Không có trận nào trong bộ lọc này.</div>')
        return
    _html(_build_pred_history_desktop_html(history_df))


def render_pred_tabs(labels: list[str]):
    """Pill-style tabs scoped to the prediction page."""
    _html('<div class="pred-tabs-marker" aria-hidden="true"></div>')
    return st.tabs(labels)


def render_pred_page_banner(user_name: str, open_count: int, saved_count: int):
    _html(
        f'<div class="pred-page-banner">'
        f'<div class="pred-banner-left">'
        f'<div class="pred-banner-title">Xin chào, {html.escape(user_name)}</div>'
        f'<div class="pred-banner-sub">Chọn <strong>A thắng / Hòa / B thắng</strong>, tích <strong>Chốt trận này</strong>, rồi bấm <strong>💾 Lưu tất cả dự đoán đã chốt.</strong> tại cuối trang</div>'
        f"</div>"
        f'<div class="pred-banner-stats">'
        f'<div class="pred-banner-stat"><span>{open_count}</span><label>Trận mở</label></div>'
        f'<div class="pred-banner-stat"><span>{saved_count}</span><label>Đã dự đoán</label></div>'
        f"</div></div>"
    )


def _truncate_team_name(name: str, max_len: int = 19) -> str:
    text = str(name).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def _build_group_team_cell(team_name: str, name_to_fifa: dict[str, str] | None) -> str:
    full_name = str(team_name).strip()
    display_name = _truncate_team_name(full_name)
    flag = flag_img_html(team_name=full_name, name_to_fifa=name_to_fifa, size="sm")
    fifa = (name_to_fifa or {}).get(full_name, "")
    name_html = f'<span class="grp-team-name" title="{html.escape(full_name)}">{html.escape(display_name)}</span>'
    if fifa:
        href = f"/Tra_Cuu_Doi_Bong?team={html.escape(str(fifa).upper())}"
        name_html = f'<a class="grp-team-link" href="{href}">{name_html}</a>'
    return f'<span class="grp-team-cell">{flag}{name_html}</span>'


def _build_group_card_html(
    group_letter: str,
    standings_df,
    color: str,
    name_to_fifa: dict[str, str] | None = None,
) -> str:
    rows_html = ""
    for _, row in standings_df.iterrows():
        gd = int(row["gd"])
        full_name = str(row["team_name"])
        rows_html += (
            f"<tr>"
            f'<td class="grp-rank">{int(row["rank"])}</td>'
            f'<td class="grp-team">{_build_group_team_cell(full_name, name_to_fifa)}</td>'
            f'<td class="grp-stat">{int(row["played"])}</td>'
            f'<td class="grp-stat grp-wdl">{int(row["won"])}-{int(row["drawn"])}-{int(row["lost"])}</td>'
            f'<td class="grp-stat">{gd:+d}</td>'
            f'<td class="grp-pts">{int(row["points"])}</td>'
            f"</tr>"
        )
    return (
        f'<div class="group-card" style="--group-color:{html.escape(color)};">'
        f'<div class="group-card-header">'
        f'<span class="group-card-dot"></span>'
        f'<span>BẢNG {html.escape(group_letter)}</span>'
        f"</div>"
        f'<table class="group-standings-table">'
        f'<thead><tr><th class="grp-rank">#</th><th>Đội</th>'
        f'<th class="grp-stat">Tr</th><th class="grp-stat grp-wdl">W-D-L</th>'
        f'<th class="grp-stat">HS</th><th class="grp-pts">Đ</th></tr></thead>'
        f"<tbody>{rows_html}</tbody></table></div>"
    )


def render_group_standings_grid(
    standings_by_letter: dict,
    group_colors: dict | None = None,
    name_to_fifa: dict[str, str] | None = None,
):
    """Render all group cards in a responsive CSS grid (3 cols desktop, 2 cols ≤900px)."""
    from schedule_service import GROUP_COLORS

    colors = group_colors or GROUP_COLORS
    cards = "".join(
        _build_group_card_html(
            letter,
            standings_by_letter[letter],
            colors.get(letter, "#64748b"),
            name_to_fifa=name_to_fifa,
        )
        for letter in sorted(standings_by_letter.keys())
    )
    _html(f'<div class="group-standings-grid">{cards}</div>')


def render_group_table(
    group_letter: str,
    standings_df,
    color: str,
    name_to_fifa: dict[str, str] | None = None,
):
    """Mini standings table for one group."""
    _html(_build_group_card_html(group_letter, standings_df, color, name_to_fifa=name_to_fifa))


def _build_ko_match_html(match, name_to_fifa: dict | None) -> str:
    def _team_row(team, side: str) -> str:
        winner_cls = " ko-team--winner" if team.is_winner else ""
        flag = flag_img_html(fifa_code=team.fifa_code, team_name=team.name, name_to_fifa=name_to_fifa, size="sm")
        return (
            f'<div class="ko-team ko-team--{side}{winner_cls}">'
            f"{flag}"
            f'<span class="ko-team-name">{html.escape(team.name)}</span>'
            f'<span class="ko-team-score">{html.escape(team.score_display)}</span>'
            f"</div>"
        )

    return (
        f'<div class="ko-match">'
        f"{_team_row(match.team_a, 'a')}"
        f"{_team_row(match.team_b, 'b')}"
        f"</div>"
    )


def _build_ko_round_column(
    rnd: dict,
    name_to_fifa: dict | None,
    *,
    mirror_vertical: bool = False,
) -> str:
    matches = list(rnd["matches"])
    if mirror_vertical:
        matches = list(reversed(matches))
    matches_html = "".join(_build_ko_match_html(m, name_to_fifa) for m in matches)
    count = max(len(rnd["matches"]), 1)
    return (
        f'<div class="ko-round" style="--round-color:{html.escape(rnd["color"])};--match-count:{count}">'
        f'<div class="ko-round-title">{html.escape(rnd["label"])}</div>'
        f'<div class="ko-round-matches">{matches_html}</div>'
        f"</div>"
    )


def render_knockout_bracket(bracket_data: dict, name_to_fifa: dict | None = None):
    """Two-sided tournament bracket — left & right halves meet at center final."""
    from schedule_service import STAGE_ID_COLORS

    left = bracket_data.get("left_rounds") or []
    right = bracket_data.get("right_rounds") or []
    final = bracket_data.get("final")
    if not left and not right and not final:
        return

    left_html = "".join(_build_ko_round_column(r, name_to_fifa) for r in left)
    # Right half: inner rounds beside final, outer R32 at far right; mirror match stack vertically.
    right_html = "".join(
        _build_ko_round_column(r, name_to_fifa, mirror_vertical=True) for r in reversed(right)
    )

    center_html = ""
    if final:
        center_html += (
            f'<div class="ko-center-final" style="--round-color:{html.escape(STAGE_ID_COLORS.get(7, "#fbbf24"))}">'
            f'<div class="ko-round-title">CHUNG KẾT</div>'
            f"{_build_ko_match_html(final, name_to_fifa)}"
            f"</div>"
        )
    tp = bracket_data.get("third_place")
    if tp:
        center_html += (
            f'<div class="ko-center-third">'
            f'<div class="ko-round-title">TRANH HẠNG 3</div>'
            f"{_build_ko_match_html(tp, name_to_fifa)}"
            f"</div>"
        )

    _html(
        f'<div class="ko-bracket-wrap">'
        f'<div class="ko-bracket-split">'
        f'<div class="ko-half ko-half--left">{left_html}</div>'
        f'<div class="ko-bracket-center">{center_html}</div>'
        f'<div class="ko-half ko-half--right">{right_html}</div>'
        f"</div></div>"
    )
