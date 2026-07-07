import contextlib
import hashlib
import hmac
import html
import os
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

import pandas as pd
import streamlit as st

from achievement_service import (
    BADGE_RARITIES,
    RARITY_LABELS_VN,
    badge_chip_style,
    badge_rarity_slug,
    normalize_badge_rarity,
    parse_badge_list,
)
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

_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))


def _html_inline(content: str) -> None:
    """CSS :has() anchors + HTML that must sit in the same DOM as Streamlit widgets."""
    st.markdown(content, unsafe_allow_html=True)


_html_marker = _html_inline


def _html(content: str) -> None:
    """Self-contained HTML panels only — never place CSS bridge markers here."""
    st.html(content)

def _read_asset_text(*filenames: str) -> str:
    parts: list[str] = []
    for name in filenames:
        path = os.path.join(_PROJECT_ROOT, "assets", name)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                parts.append(f.read())
    return "\n\n".join(parts)


_CSS_BUNDLE_VERSION = "20260707e"


def apply_global_styles():
    full_css = _read_asset_text(
        "style.css",
        "style-cloud-bridge.css",
        "style-pred-segmented-bridge.css",
        "style-lb-responsive-bridge.css",
        "style-tabs-layout-bridge.css",
    )
    if full_css:
        st.markdown(f"<style>{full_css}</style>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ Không tìm thấy file assets/style.css")

    st.markdown(
        f'<link rel="stylesheet" href="app/static/style.css?v={_CSS_BUNDLE_VERSION}">',
        unsafe_allow_html=True,
    )

    _SIDEBAR_OVERLAY_BOOT = """
<script>
(function () {
  function canUseDocument(win) {
    try {
      return !!(win && win.document && win.document.body && win.document.head);
    } catch (e) {
      return false;
    }
  }

  function hasStreamlitApp(win) {
    if (!canUseDocument(win)) return false;
    return !!(
      win.document.querySelector('[data-testid="stApp"]') ||
      win.document.querySelector('[data-testid="stSidebar"]') ||
      win.document.querySelector('[data-testid="stAppViewContainer"]')
    );
  }

  function resolveHostWindow() {
    let current = window;
    let best = canUseDocument(current) ? current : null;
    for (let i = 0; i < 8 && current; i += 1) {
      if (hasStreamlitApp(current)) best = current;
      try {
        if (!current.parent || current.parent === current) break;
        current = current.parent;
      } catch (e) {
        break;
      }
    }
    if (hasStreamlitApp(current)) best = current;
    return best || window;
  }

  const hostWin = resolveHostWindow();
  const hostDoc = hostWin.document;
  const WC_SIDEBAR_OVERLAY_VERSION = 8;
  if (hostWin.__wcSidebarOverlayVersion === WC_SIDEBAR_OVERLAY_VERSION) {
    hostWin.__wcSidebarOverlaySync?.();
    return;
  }
  hostWin.__wcSidebarOverlayVersion = WC_SIDEBAR_OVERLAY_VERSION;
  hostWin.__wcSidebarOverlayInit = false;
  hostWin.__wcSidebarOverlayObserver?.disconnect();
  hostDoc.getElementById("wc-sidebar-backdrop")?.remove();
  hostDoc.getElementById("wc-sidebar-overlay-boot")?.remove();
  const boot = hostDoc.createElement("script");
  boot.id = "wc-sidebar-overlay-boot";
  boot.textContent = `
(function () {
  let syncQueued = false;
  let domObserver = null;

  function isSidebarOpen() {
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    return !!(sidebar && sidebar.getAttribute("aria-expanded") === "true");
  }

  function scheduleBackdropSync() {
    queueSyncBackdrop();
    setTimeout(queueSyncBackdrop, 180);
    setTimeout(queueSyncBackdrop, 480);
  }

  function reactClickTarget(node) {
    if (!node) return null;
    const candidates = [
      node,
      ...Array.from(node.querySelectorAll?.("*") || []),
      node.parentElement,
      node.parentElement?.parentElement,
    ].filter(Boolean);

    for (const candidate of candidates) {
      const reactKey = Object.keys(candidate).find((k) => k.startsWith("__reactProps"));
      const reactOnClick = reactKey && candidate[reactKey]?.onClick;
      if (typeof reactOnClick === "function") {
        return { node: candidate, onClick: reactOnClick };
      }
    }
    return null;
  }

  function invokeReactClick(target) {
    const reactTarget = reactClickTarget(target);
    if (!reactTarget) return false;
    reactTarget.onClick({
        preventDefault() {},
        stopPropagation() {},
      target: reactTarget.node,
      currentTarget: reactTarget.node,
        type: "click",
        nativeEvent: new MouseEvent("click", {
          bubbles: true,
          cancelable: true,
          view: window,
        }),
      });
    return true;
  }

  function collapseSidebar() {
    const root = document.querySelector('[data-testid="stSidebarCollapseButton"]');
    const btn =
      document.querySelector('[data-testid="stSidebarCollapseButton"] button') ||
      document.querySelector('[data-testid="stSidebarCollapseButton"] [role="button"]') ||
      root;
    if (!btn) return;

    if (invokeReactClick(btn) || invokeReactClick(root)) {
      scheduleBackdropSync();
      return;
    }

    if (typeof btn.click === "function") {
      btn.click();
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

  window.__wcSidebarOverlayDomObserver?.disconnect();
  window.addEventListener("resize", queueSyncBackdrop);
  window.addEventListener("popstate", handlePageChange);
  document.addEventListener("click", onOutsidePointer, true);
  document.addEventListener("touchend", onOutsidePointer, true);
  domObserver = new MutationObserver(() => {
    handlePageChange();
    bindSidebarObserver();
  });
  window.__wcSidebarOverlayDomObserver = domObserver;
  domObserver.observe(document.body, { childList: true, subtree: true });

  handlePageChange();
  bindSidebarObserver();
  queueSyncBackdrop();
  setTimeout(queueSyncBackdrop, 250);
  setTimeout(queueSyncBackdrop, 750);
})();
`;
  hostDoc.head.appendChild(boot);
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

def _auth_query_params(params: dict[str, str] | None = None) -> dict[str, str]:
    query = {str(k): str(v) for k, v in (params or {}).items() if v is not None}
    uid = st.session_state.get("authenticated_user_id")
    if uid is not None:
        uid = str(uid)
        query["uid"] = uid
        query["sig"] = get_auth_signature(uid)
    return query

def internal_nav_url(href: str, params: dict[str, str] | None = None) -> str:
    """Build an internal URL without dropping the signed auth query params."""
    href = str(href or "#").strip()
    if not href or href == "#" or href.startswith(("http://", "https://", "mailto:", "tel:")):
        return href or "#"

    parsed = urlsplit(href)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({str(k): str(v) for k, v in (params or {}).items() if v is not None})
    signed_query = _auth_query_params(query)
    suffix = f"?{urlencode(signed_query)}" if signed_query else ""
    return f"{parsed.path or href}{suffix}"

_INTERNAL_PAGE_MAP = {
    "/": "app.py",
    "/Du_Doan": "pages/1_Du_Doan.py",
    "/Lich_Thi_Dau": "pages/2_Lich_Thi_Dau.py",
    "/Bang_Xep_Hang": "pages/3_Bang_Xep_Hang.py",
    "/Xem_Lich_Thi_Dau": "pages/4_Xem_Lich_Thi_Dau.py",
    "/Bang_Dau": "pages/5_Bang_Dau.py",
    "/Bracket_Knockout": "pages/6_Bracket_Knockout.py",
    "/Tra_Cuu_Doi_Bong": "pages/7_Tra_Cuu_Doi_Bong.py",
}

def _internal_page_link_target(href: str) -> tuple[str | None, dict[str, str]]:
    parsed = urlsplit(str(href or "").strip())
    page = _INTERNAL_PAGE_MAP.get(parsed.path)
    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    return page, _auth_query_params(params)

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
        st.caption(f"UI bundle v{_CSS_BUNDLE_VERSION} · Streamlit {st.__version__}")

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
    for start in range(0, len(cards), 5):
        row_cards = cards[start : start + 5]
        cols = st.columns(len(row_cards), gap="medium")
        for idx, (col, card) in enumerate(zip(cols, row_cards), start=start + 1):
            href = card.get("href", "#")
            icon = card.get("icon", "")
            title = card.get("title", "")
            desc = card.get("desc", "")
            cta = card.get("cta", "Mở")
            tone = card.get("tone", "blue")
            page, query_params = _internal_page_link_target(href)
            label = f"{icon}  \n**{title}**  \n{desc}  \n**{cta} →**"
            with col:
                _html_inline(
                    f'<span class="home-cta-native-marker home-cta-native-marker--{html.escape(tone)}" aria-hidden="true"></span>'
                )
                if page:
                    st.page_link(page, label=label, width="stretch", query_params=query_params)
                else:
                    st.link_button(label, internal_nav_url(href), width="stretch")

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
        href_a = internal_nav_url("/Tra_Cuu_Doi_Bong", {"team": code_a})
        squad_links += f'<a class="fixture-squad-link" href="{html.escape(href_a)}">{html.escape(code_a)}</a>'
    if code_b:
        if squad_links:
            squad_links += '<span class="fixture-squad-sep">·</span>'
        href_b = internal_nav_url("/Tra_Cuu_Doi_Bong", {"team": code_b})
        squad_links += f'<a class="fixture-squad-link" href="{html.escape(href_b)}">{html.escape(code_b)}</a>'
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


def render_analytics_guide(*, icon: str, title: str, summary: str, tips: list[str]) -> None:
    tips_html = "".join(
        f'<li class="analytics-guide-tip">{html.escape(tip)}</li>' for tip in tips if tip
    )
    _html(
        f'<div class="analytics-guide">'
        f'<div class="analytics-guide-icon">{html.escape(icon)}</div>'
        f'<div class="analytics-guide-body">'
        f'<div class="analytics-guide-title">{html.escape(title)}</div>'
        f'<p class="analytics-guide-summary">{html.escape(summary)}</p>'
        f'<ul class="analytics-guide-tips">{tips_html}</ul>'
        f"</div></div>"
    )


def render_analytics_insight_chips(chips: list[tuple[str, str, str]]) -> None:
    """Render metric chips: (value, label, tone) where tone = ok|bad|gold|muted|info."""
    items = []
    for value, label, tone in chips:
        tone_class = f" analytics-chip--{tone}" if tone else ""
        items.append(
            f'<div class="analytics-chip{tone_class}">'
            f'<span class="analytics-chip-value">{html.escape(str(value))}</span>'
            f'<span class="analytics-chip-label">{html.escape(label)}</span>'
            f"</div>"
        )
    _html(f'<div class="analytics-chip-row">{"".join(items)}</div>')


def render_analytics_takeaway(text: str) -> None:
    if not text:
        return
    _html(
        f'<div class="analytics-takeaway">'
        f'<span class="analytics-takeaway-label">💡 Kết luận nhanh</span>'
        f'<p class="analytics-takeaway-text">{html.escape(text)}</p>'
        f"</div>"
    )


def render_lb_main_tabs(labels: list[str]):
    """Premium pill switcher for leaderboard page main tabs."""
    with st.container():
        _html_inline('<div class="lb-main-tabs-marker" aria-hidden="true"></div>')
        return st.tabs(labels)


def render_analytics_section_header(*, eyebrow: str, title: str, subtitle: str) -> None:
    _html(
        f'<div class="analytics-section-head">'
        f'<div class="analytics-section-head-glow" aria-hidden="true"></div>'
        f'<div class="analytics-section-head-inner">'
        f'<span class="analytics-section-eyebrow">{html.escape(eyebrow)}</span>'
        f'<h2 class="analytics-section-title">{html.escape(title)}</h2>'
        f'<p class="analytics-section-subtitle">{html.escape(subtitle)}</p>'
        f"</div></div>"
    )


def render_analytics_sub_tabs(labels: list[str]):
    """Segmented control for analytics sub-views."""
    with st.container():
        _html_inline('<div class="lb-analytics-tabs-marker" aria-hidden="true"></div>')
        return st.tabs(labels)


def render_leaderboard_podium(entries: list[dict]) -> None:
    if not entries:
        return
        
    medal_map = {1: "🥇", 2: "🥈", 3: "🥉"}
    
    # ÉP CỨNG: Dù có bao nhiêu người gửi vào, bục chỉ lấy ĐÚNG 3 người đầu tiên
    top_3_entries = entries[:3]
    
    # Sắp xếp DOM theo Flexbox: [Trái (Hạng 2), Giữa (Hạng 1), Phải (Hạng 3)]
    if len(top_3_entries) >= 3:
        order = [1, 0, 2]
    elif len(top_3_entries) == 2:
        order = [1, 0]
    else:
        order = [0]
        
    items = []
    for slot in order:
        entry = top_3_entries[slot]
        
        # NGẮT KẾT NỐI ĐIỂM SỐ: 
        # Hạng được quyết định 100% bằng vị trí trong mảng (slot 0 -> Hạng 1, slot 1 -> Hạng 2...)
        math_rank = slot + 1
        visual_bar = str(math_rank)
        medal = medal_map.get(math_rank, f"#{math_rank}")
        
        # Xóa bỏ hoàn toàn HTML của "Đồng hạng"
        items.append(
            f'<div class="podium-item podium-item--rank-{visual_bar}">'
            f'<div class="podium-bar podium-bar--{visual_bar}">{medal}</div>'
            f'<div class="podium-name">{html.escape(str(entry.get("name", "")))}</div>'
            f'<div class="podium-pts">{int(entry.get("points", 0))} điểm</div>'
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


def _pick_hero_king(lb: pd.DataFrame) -> pd.Series | None:
    if lb.empty:
        return None
    return lb.sort_values(["points", "fines", "name"], ascending=[False, True, True]).iloc[0]


def _pick_hero_sniper(lb: pd.DataFrame) -> pd.Series | None:
    candidates = lb[lb["played"] > 0]
    if candidates.empty:
        return None
    return candidates.sort_values(
        ["hit_rate", "correct", "name"],
        ascending=[False, False, True],
    ).iloc[0]


def _pick_hero_shame(lb: pd.DataFrame) -> pd.Series | None:
    if lb.empty:
        return None
    return lb.sort_values(["fines", "points", "name"], ascending=[False, False, True]).iloc[0]


def _lb_hero_cards_payload(lb: pd.DataFrame) -> list[dict]:
    """Three hero highlights: king, overthinker (phút 90), shame."""
    king = _pick_hero_king(lb)
    shame = _pick_hero_shame(lb)

    # =========================================================
    # LOGIC MỚI: TÍNH TOÁN "CHÚA TỂ PHÚT 90" THAY TAY SĂN BÀN
    # =========================================================
    panic_name = "—"
    panic_metric = "Chưa có dữ liệu"
    
    # Sử dụng biến 'scored_df' toàn cục từ session state hoặc luồng chạy nếu có
    # Trong trường hợp hàm này chỉ nhận đầu vào là 'lb' (leaderboard), ta tận dụng dữ liệu phong độ/hit rate thấp để mô phỏng
    # Hoặc nếu sếp muốn lấy chuẩn từ timestamp, ta quét nhanh qua dataframe:
    import streamlit as st
    if "scored_df" in st.session_state and not st.session_state["scored_df"].empty:
        df_panic = st.session_state["scored_df"].copy()
        if "timestamp" in df_panic.columns and "kickoff_vn" in df_panic.columns:
            df_panic["kickoff_vn"] = pd.to_datetime(df_panic["kickoff_vn"], format="mixed", errors="coerce", utc=True)
            df_panic["timestamp"] = pd.to_datetime(df_panic["timestamp"], format="mixed", errors="coerce", utc=True)
            df_panic = df_panic.dropna(subset=["kickoff_vn", "timestamp"])
            
            if not df_panic.empty:
                df_panic["delta_mins"] = (df_panic["kickoff_vn"] - df_panic["timestamp"]).dt.total_seconds() / 60.0
                if "match_pts" not in df_panic.columns:
                    df_panic["match_pts"] = 0
                df_panic["match_pts"] = pd.to_numeric(df_panic["match_pts"], errors="coerce").fillna(0)
                
                # Chốt kèo <= 60 phút và điểm = 0 (đoán sai bét)
                fail_sps = df_panic[(df_panic["delta_mins"] > 0) & (df_panic["delta_mins"] <= 60) & (df_panic["match_pts"] == 0)]
                if not fail_sps.empty:
                    counts = fail_sps.groupby("name").size().reset_index(name="fails")
                    top_overthinker = counts.sort_values(by=["fails", "name"], ascending=[False, True]).iloc[0]
                    panic_name = str(top_overthinker["name"])
                    panic_metric = f"Có {int(top_overthinker['fails'])} trận tự hủy sát giờ"

    # Nếu session_state chưa kịp lưu, giải pháp fallback lấy người có hit_rate thấp nhất trong Top chơi đủ trận
    if panic_name == "—" and not lb.empty:
        eligible_players = lb[lb["played"] >= 5]
        if not eligible_players.empty:
            bot_sniper = eligible_players.sort_values(by=["hit_rate", "points"], ascending=[True, True]).iloc[0]
            panic_name = str(bot_sniper["name"])
            panic_metric = f"📉 Hit Rate chỉ {float(bot_sniper['hit_rate']):.1f}%"

    cards = [
        {
            "icon": "🇵🇹🐐🇵🇹",
            "title": "SIUUUU",
            "name": str(king["name"]) if king is not None else "—",
            "metric": f"{int(king['points'])} điểm - với tỉ lệ trúng {float(king['hit_rate']):.1f}%" if king is not None else "Chưa có dữ liệu",
            "extra_class": "",
        },
        {
            "icon": "⏱️",
            "title": "Nghĩ như Pep , bet như sh!t",  # Sửa đổi tiêu đề hiển thị động cứng
            "name": panic_name,
            "metric": panic_metric,
            "extra_class": "",
        },
    ]
    
    if shame is not None:
        cards.append(
            {
                "icon": "💸",
                "title": "Khổ qua dĩa lớn",
                "name": str(shame["name"]),
                "metric": f"{int(shame['fines'])}k phạt",
                "extra_class": "lb-hero-card--shame",
            }
        )
    else:
        cards.append(
            {
                "icon": "💸",
                "title": "Thánh Cống Hiến",
                "name": "—",
                "metric": "Chưa có dữ liệu",
                "extra_class": "lb-hero-card--shame",
            }
        )
    return cards


def _render_lb_hero_card_html(
    *,
    icon: str,
    title: str,
    name: str,
    metric: str,
    extra_class: str = "",
) -> str:
    cls = f"lb-hero-card {extra_class}".strip()
    return (
        f'<div class="{cls}">'
        f'<div class="lb-hero-card-icon">{html.escape(icon)}</div>'
        f'<div class="lb-hero-card-title">{html.escape(title)}</div>'
        f'<div class="lb-hero-card-name">{html.escape(name)}</div>'
        f'<div class="lb-hero-card-metric">{html.escape(metric)}</div>'
        f"</div>"
    )


def _render_lb_hero_cards_desktop_html(lb: pd.DataFrame) -> str:
    cards = "".join(
        _render_lb_hero_card_html(**card) for card in _lb_hero_cards_payload(lb)
    )
    return f'<div class="lb-hero-grid lb-hero-grid--desktop">{cards}</div>'


def _render_lb_hero_cards_mobile_compact_html(lb: pd.DataFrame) -> str:
    chips = []
    for card in _lb_hero_cards_payload(lb):
        shame_cls = " lb-hero-chip--shame" if "shame" in card["extra_class"] else ""
        chips.append(
            f'<div class="lb-hero-chip{shame_cls}">'
            f'<span class="lb-hero-chip-icon">{html.escape(card["icon"])}</span>'
            f'<span class="lb-hero-chip-title">{html.escape(card["title"])}</span>'
            f'<span class="lb-hero-chip-name">{html.escape(card["name"])}</span>'
            f'<span class="lb-hero-chip-metric">{html.escape(card["metric"])}</span>'
            f"</div>"
        )
    return f'<div class="lb-hero-strip">{"".join(chips)}</div>'


def render_lb_hero_cards(lb: pd.DataFrame) -> None:
    """Desktop hero cards — full size above leaderboard."""
    if lb.empty:
        return
    _html_inline('<div class="lb-hero-desktop-marker" aria-hidden="true"></div>')
    _html(_render_lb_hero_cards_desktop_html(lb))


def render_lb_hero_cards_mobile_compact(lb: pd.DataFrame) -> None:
    """Mobile-only compact hero strip below leaderboard table."""
    if lb.empty:
        return
    _html_inline('<div class="lb-hero-mobile-compact-marker" aria-hidden="true"></div>')
    _html(_render_lb_hero_cards_mobile_compact_html(lb))


def _lb_player_name(row: pd.Series, highlight: str | None) -> str:
    name = str(row["name"])
    if highlight and str(row["user_id"]) == highlight:
        return f"{name} (Bạn)"
    return name


def _lb_accuracy(row: pd.Series) -> str:
    played = int(row["played"])
    if played <= 0:
        return "—"
    return f"{int(row['correct'])}/{played}"


_FORM_EMOJI = {"W": "✅", "L": "❌", "D": "➖"}
_LB_FORM_LIMIT = 3


def _lb_rank_delta_html(delta: int) -> str:
    if delta > 0:
        return (
            f'<span class="lb-rank-delta lb-rank-delta--up" title="Lên {delta} hạng">'
            f'<span class="lb-rank-delta-icon" aria-hidden="true">↑</span>'
            f'<span class="lb-rank-delta-val">{delta}</span>'
            f"</span>"
        )
    if delta < 0:
        steps = abs(delta)
        return (
            f'<span class="lb-rank-delta lb-rank-delta--down" title="Tụt {steps} hạng">'
            f'<span class="lb-rank-delta-icon" aria-hidden="true">↓</span>'
            f'<span class="lb-rank-delta-val">{steps}</span>'
            f"</span>"
        )
    return '<span class="lb-rank-delta lb-rank-delta--flat" title="Giữ hạng" aria-label="Giữ hạng">—</span>'


def _lb_rank_cell_html(rank_label: str, delta: int, *, inline: bool = False) -> str:
    label = html.escape(str(rank_label))
    layout = " lb-rank-cell--inline" if inline else ""
    return (
        f'<span class="lb-rank-cell{layout}">'
        f'<span class="lb-rank-label">{label}</span>'
        f"{_lb_rank_delta_html(delta)}"
        f"</span>"
    )


def _lb_hp_tier_class(remaining_hp_pct: float) -> str:
    if remaining_hp_pct > 50:
        return "lb-hp-bar-fill--high"
    if remaining_hp_pct >= 20:
        return "lb-hp-bar-fill--mid"
    return "lb-hp-bar-fill--low"


def _lb_hp_bar_html(remaining_hp: int, remaining_hp_pct: float, *, compact: bool = False) -> str:
    pct = max(0.0, min(100.0, float(remaining_hp_pct)))
    tier = _lb_hp_tier_class(pct)
    compact_cls = " lb-hp-bar--compact" if compact else ""
    return (
        f'<span class="lb-hp-bar{compact_cls}">'
        f'<span class="lb-hp-bar-track">'
        f'<span class="lb-hp-bar-fill {tier}" style="width:{pct:.1f}%"></span>'
        f"</span>"
        f'<span class="lb-hp-bar-label">{int(remaining_hp)}/104</span>'
        f"</span>"
    )


def _lb_badge_chip_html(name: str, rarity_map: dict[str, str] | None = None) -> str:
    badge_name = str(name).strip()
    rarity = normalize_badge_rarity((rarity_map or {}).get(badge_name, "Common"))
    slug = badge_rarity_slug(rarity)
    style = badge_chip_style(badge_name)
    rarity_label = RARITY_LABELS_VN.get(rarity, rarity)
    title = f"{badge_name} · {rarity_label}"
    overlays = ""
    if rarity == "Rare":
        overlays = (
            '<span class="lb-badge-chip-shine" aria-hidden="true"></span>'
            '<span class="lb-badge-chip-spark" aria-hidden="true"></span>'
        )
    elif rarity == "Legend":
        overlays = (
            '<span class="lb-badge-chip-holo" aria-hidden="true"></span>'
            '<span class="lb-badge-chip-prism" aria-hidden="true"></span>'
            '<span class="lb-badge-chip-shine lb-badge-chip-shine--legend" aria-hidden="true"></span>'
        )
    return (
        f'<span class="lb-badge-chip lb-badge-chip--{slug}" style="{style}" '
        f'title="{html.escape(title)}">'
        f"{overlays}"
        f'<span class="lb-badge-chip-text">{html.escape(badge_name)}</span>'
        "</span>"
    )


def _lb_badges_html(badges, rarity_map: dict[str, str] | None = None) -> str:
    items = parse_badge_list(badges)
    if not items:
        return '<span class="lb-cell-badges lb-cell-badges--empty">—</span>'
    chips = [_lb_badge_chip_html(name, rarity_map) for name in items]
    return f'<span class="lb-cell-badges">{"".join(chips)}</span>'


def _render_leaderboard_desktop_html(
    lb: pd.DataFrame,
    highlight_user_id: str | None = None,
    sidebar_bundle: dict | None = None,
    badge_rarity_map: dict[str, str] | None = None,
) -> None:
    """Full HTML leaderboard for desktop — styled rank pills + optional sidebar."""
    highlight = str(highlight_user_id) if highlight_user_id else None
    body = []
    for _, row in lb.iterrows():
        uid = str(row["user_id"])
        is_me = highlight and uid == highlight
        row_class = "lb-row lb-row--me" if is_me else "lb-row"
        rank = _lb_rank_cell_html(row["rank_label"], int(row.get("rank_movement_delta", 0)), inline=True)
        name = html.escape(str(row["name"]))
        me_badge = '<span class="lb-you">Bạn</span>' if is_me else ""
        form = html.escape(_lb_form_html(row.get("recent_form", []), limit=_LB_FORM_LIMIT))
        remaining_hp = int(row.get("remaining_hp", 140))
        remaining_hp_pct = float(row.get("remaining_hp_pct", 100))
        hp_html = _lb_hp_bar_html(remaining_hp, remaining_hp_pct)
        badges_html = _lb_badges_html(row.get("badges", []), badge_rarity_map)
        played = int(row["played"])
        correct = int(row["correct"])
        accuracy = f"{correct}/{played}" if played else "—"
        missed = int(row["missed"])
        body.append(
            f'<div class="{row_class}">'
            f'<span class="lb-cell-rank">{rank}</span>'
            f'<span class="lb-cell-name">'
            f'<span class="lb-cell-name-line">{name}{me_badge}</span>'
            f'{badges_html}'
            f"</span>"
            f'<span class="lb-cell-pts">{int(row["points"])}</span>'
            f'<div class="lb-stats-band">'
            f'<span class="lb-cell-form lb-stat-col">{form}</span>'
            f'<span class="lb-cell-hp lb-stat-col">{hp_html}</span>'
            f'<span class="lb-cell-acc lb-stat-col">{html.escape(accuracy)}</span>'
            f'<span class="lb-cell-miss lb-stat-col">{missed if missed else "—"}</span>'
            f"</div>"
            f"</div>"
        )

    head = (
        '<div class="lb-list-head">'
        '<span class="lb-col-rank">Hạng</span>'
        '<span class="lb-col-name">Người chơi</span>'
        '<span class="lb-col-pts">Điểm</span>'
        '<div class="lb-stats-band lb-stats-band--head">'
        '<span class="lb-col-form lb-stat-col">Phong độ</span>'
        '<span class="lb-col-hp lb-stat-col">Sinh lực</span>'
        '<span class="lb-col-acc lb-stat-col">Đúng</span>'
        '<span class="lb-col-miss lb-stat-col">Bỏ lỡ</span>'
        "</div>"
        "</div>"
    )
    _html_inline('<div class="lb-dataframe-desktop-marker" aria-hidden="true"></div>')
    _html_inline('<div class="lb-desktop-layout-marker" aria-hidden="true"></div>')
    _html(
        '<div class="lb-desktop-layout">'
        f'<div class="lb-desktop-main">'
        f'<div class="lb-list lb-list--gamified-desktop">{head}{"".join(body)}</div>'
        '</div>'
        f'<aside class="lb-desktop-sidebar">{_render_lb_sidebar_html(sidebar_bundle)}</aside>'
        '</div>'
    )


def _render_lb_sidebar_html(sidebar_bundle: dict | None) -> str:
    if not sidebar_bundle:
        return (
            f'{_render_lb_activity_stream_html([])}'
            f'{_render_lb_streak_cards_html({})}'
        )
    activity = sidebar_bundle.get("activity") or []
    streaks = sidebar_bundle.get("streaks") or {}
    return (
        f'{_render_lb_activity_stream_html(activity)}'
        f'{_render_lb_streak_cards_html(streaks)}'
    )


def _render_lb_activity_stream_html(events: list) -> str:
    title = "Hoạt động mới nhất"
    if not events:
        items = (
            '<div class="lb-activity-item lb-activity-item--empty">'
            "Chưa có hoạt động"
            "</div>"
        )
    else:
        parts = []
        for ev in events:
            tone = html.escape(str(ev.get("tone", "good")))
            icon = html.escape(str(ev.get("icon", "•")))
            text = html.escape(str(ev.get("text", "")))
            parts.append(
                f'<div class="lb-activity-item lb-activity-item--{tone}">'
                f'<span class="lb-activity-icon">{icon}</span>'
                f'<span class="lb-activity-text">{text}</span>'
                f"</div>"
            )
        items = "".join(parts)
    return (
        '<section class="lb-sidebar-section lb-activity-section">'
        f'<h3 class="lb-sidebar-title">{title}</h3>'
        f'<div class="lb-activity-feed">{items}</div>'
        "</section>"
    )


def _render_lb_streak_cards_html(streaks: dict, *, mobile: bool = False) -> str:
    win = streaks.get("win_streak")
    lose = streaks.get("lose_streak")
    upset = streaks.get("upset_hero")

    def _history(entry: dict | None) -> str:
        if not entry:
            return ""
        if mobile:
            return entry.get("history_stack_html") or entry.get("history_html", "")
        return entry.get("history_html", "")

    def _card(
        icon: str,
        title: str,
        name: str,
        metric: str,
        extra: str = "",
        history_html: str = "",
    ) -> str:
        cls = f"lb-streak-card {extra}".strip()
        history_block = ""
        if history_html:
            if mobile and "lb-streak-card-history--stack" in history_html:
                history_block = history_html
            else:
                history_block = f'<div class="lb-streak-card-history">{history_html}</div>'
        return (
            f'<div class="{cls}">'
            f'<div class="lb-streak-card-icon">{html.escape(icon)}</div>'
            f'<div class="lb-streak-card-title">{html.escape(title)}</div>'
            f'<div class="lb-streak-card-name">{html.escape(name)}</div>'
            f'<div class="lb-streak-card-metric">{html.escape(metric)}</div>'
            f"{history_block}"
            f"</div>"
        )

    cards = []
    if win:
        cards.append(
            _card(
                "🔥",
                "Chuỗi Thắng",
                f"{win.get('user_id', '')} {win.get('name', '')}".strip(),
                f"{win.get('streak', 0)} trận liên tiếp",
                history_html=_history(win),
            )
        )
    else:
        cards.append(_card("🔥", "Chuỗi Thắng", "—", "Chưa có kỷ lục", "lb-streak-card--empty"))

    if lose:
        cards.append(
            _card(
                "💀",
                "Chuỗi Thua",
                f"{lose.get('user_id', '')} {lose.get('name', '')}".strip(),
                f"{lose.get('streak', 0)} trận liên tiếp",
                extra="lb-streak-card--shame",
                history_html=_history(lose),
            )
        )
    else:
        cards.append(
            _card("💀", "Chuỗi Thua", "—", "Chưa có kỷ lục", "lb-streak-card--empty lb-streak-card--shame")
        )

    if upset:
        cards.append(
            _card(
                "🎯",
                "Vua Bịp",
                f"{upset.get('user_id', '')} {upset.get('name', '')}".strip(),
                upset.get("detail", upset.get("match_label", "")),
            )
        )
    else:
        cards.append(_card("🎯", "Vua Bịp", "—", "Chưa có kỷ lục", "lb-streak-card--empty"))

    return (
        '<section class="lb-sidebar-section lb-streak-section">'
        f'{"".join(cards)}'
        "</section>"
    )


def render_lb_activity_stream(events: list) -> None:
    """Desktop sidebar activity feed."""
    _html(_render_lb_activity_stream_html(events))


def render_lb_streak_cards(streaks: dict) -> None:
    """Desktop sidebar streak milestone cards."""
    _html(_render_lb_streak_cards_html(streaks))


def render_lb_streak_cards_mobile(streaks: dict) -> None:
    """Mobile top streak cards — replaces hero cards on small screens."""
    body = _render_lb_streak_cards_html(streaks or {}, mobile=True)
    _html_inline('<div class="lb-streak-mobile-marker" aria-hidden="true"></div>')
    _html(f'<div class="lb-streak-mobile-top">{body}</div>')


def _lb_form_html(codes, *, limit: int | None = None) -> str:
    if not isinstance(codes, list):
        return ""
    items = codes[-limit:] if limit else codes
    emojis = [_FORM_EMOJI.get(c, "") for c in items if c]
    return "\u00a0".join(emojis)


def _render_leaderboard_mobile_html(
    lb: pd.DataFrame,
    highlight_user_id: str | None = None,
    badge_rarity_map: dict[str, str] | None = None,
) -> None:
    """Compact HTML leaderboard for mobile — full CSS control over column spacing."""
    highlight = str(highlight_user_id) if highlight_user_id else None

    body = []
    for _, row in lb.iterrows():
        uid = str(row["user_id"])
        is_me = highlight and uid == highlight
        row_class = "lb-row lb-row--me" if is_me else "lb-row"
        rank = _lb_rank_cell_html(row["rank_label"], int(row.get("rank_movement_delta", 0)))
        name = html.escape(str(row["name"]))
        me_badge = '<span class="lb-you">Bạn</span>' if is_me else ""
        form = html.escape(_lb_form_html(row.get("recent_form", []), limit=_LB_FORM_LIMIT))
        remaining_hp = int(row.get("remaining_hp", 104))
        remaining_hp_pct = float(row.get("remaining_hp_pct", 100))
        hp_html = _lb_hp_bar_html(remaining_hp, remaining_hp_pct, compact=True)
        badges_html = _lb_badges_html(row.get("badges", []), badge_rarity_map)
        played = int(row["played"])
        correct = int(row["correct"])
        accuracy = f"{correct}/{played}" if played else "—"
        body.append(
            f'<div class="{row_class}">'
            f'<span class="lb-cell-rank">{rank}</span>'
            f'<span class="lb-cell-name">'
            f'<span class="lb-cell-name-line">{name}{me_badge}</span>'
            f'{badges_html}'
            f"</span>"
            f'<span class="lb-cell-pts">{int(row["points"])}</span>'
            f'<div class="lb-stats-band lb-stats-band--mobile">'
            f'<span class="lb-cell-form lb-stat-col">{form}</span>'
            f'<span class="lb-cell-hp lb-stat-col">{hp_html}</span>'
            f'<span class="lb-cell-acc lb-stat-col">{html.escape(accuracy)}</span>'
            f"</div>"
            f"</div>"
        )

    head = (
        '<div class="lb-list-head">'
        '<span class="lb-col-rank">Hạng</span>'
        '<span class="lb-col-name">Người chơi</span>'
        '<span class="lb-col-pts">Điểm</span>'
        '<div class="lb-stats-band lb-stats-band--head lb-stats-band--mobile">'
        '<span class="lb-col-form lb-stat-col">Phong độ</span>'
        '<span class="lb-col-hp lb-stat-col">Sinh lực</span>'
        '<span class="lb-col-acc lb-stat-col">Đúng</span>'
        "</div>"
        "</div>"
    )
    _html_inline('<div class="lb-dataframe-mobile-marker" aria-hidden="true"></div>')
    _html(f'<div class="lb-list lb-list--gamified-mobile">{head}{"".join(body)}</div>')


def render_leaderboard_dataframe(
    lb: pd.DataFrame,
    highlight_user_id: str | None = None,
    sidebar_bundle: dict | None = None,
    badge_rarity_map: dict[str, str] | None = None,
) -> None:
    """HTML leaderboard: desktop full columns + sidebar, mobile compact."""
    if lb.empty:
        st.info("Chưa có dữ liệu bảng xếp hạng.")
        return

    _render_leaderboard_desktop_html(lb, highlight_user_id, sidebar_bundle=sidebar_bundle, badge_rarity_map=badge_rarity_map)
    _render_leaderboard_mobile_html(lb, highlight_user_id, badge_rarity_map=badge_rarity_map)


def _badge_collection_slot_icon(badge_name: str) -> str:
    text = str(badge_name).strip()
    if not text:
        return "🏅"
    first = text.split(maxsplit=1)[0] if text else "🏅"
    if len(first) <= 2:
        return first
    return "🏅"


def _badge_collection_progress_pct(unlocked: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(unlocked / total * 100, 1)


def _badge_collection_rarity_sample_html(rarity: str) -> str:
    slug = badge_rarity_slug(rarity)
    sample_name = {"Common": "Common", "Rare": "Rare ✦", "Legend": "Legend ★"}.get(rarity, rarity)
    style = badge_chip_style(sample_name)
    overlays = ""
    if rarity == "Rare":
        overlays = (
            '<span class="lb-badge-chip-shine" aria-hidden="true"></span>'
            '<span class="lb-badge-chip-spark" aria-hidden="true"></span>'
        )
    elif rarity == "Legend":
        overlays = (
            '<span class="lb-badge-chip-holo" aria-hidden="true"></span>'
            '<span class="lb-badge-chip-prism" aria-hidden="true"></span>'
            '<span class="lb-badge-chip-shine lb-badge-chip-shine--legend" aria-hidden="true"></span>'
        )
    label = RARITY_LABELS_VN.get(rarity, rarity)
    return (
        f'<span class="badge-collection-rarity-sample lb-badge-chip lb-badge-chip--{slug}" style="{style}">'
        f"{overlays}"
        f'<span class="lb-badge-chip-text">{html.escape(label)}</span>'
        "</span>"
    )


_TROPHY_GRID_COLS = 2
_TROPHY_DESC_FALLBACK = "Chưa có mô tả cho danh hiệu này."
_TROPHY_LOCKED_DESC_FALLBACK = "Chưa mở khóa — hoàn thành điều kiện để nhận danh hiệu."
_TROPHY_METRIC_FILTER_ALL = "all"

ACHIEVEMENT_GALLERY_METRIC_MAP: dict[str, str] = {
    "all": "🌟 Tất cả",
    "total_penalties": "💸 Đóng Góp Quỹ Phạt",
    "win_streak": "🔥 Chuỗi Thắng",
    "lose_streak": "🤡 Chuỗi Thua",
    "underdog_picks": "💣 Nằm Cửa Dưới",
    "late_picks": "⏳ Chốt Kèo Sát Giờ",
    "points": "🏆 Điểm Số",
    "hit_rate": "🎯 Tỉ Lệ Trúng",
    "correct": "✅ Trận Đúng",
    "missed": "😴 Bỏ Lỡ",
    "played": "📋 Số Trận Đã Dự Đoán",
    "remaining_hp": "❤️ Sinh Lực",
}


def format_gallery_metric(metric: str) -> str:
    """Human-readable gallery filter label with fallback."""
    key = str(metric or "").strip()
    if not key:
        return "Khác"
    if key in ACHIEVEMENT_GALLERY_METRIC_MAP:
        return ACHIEVEMENT_GALLERY_METRIC_MAP[key]
    return key.replace("_", " ").capitalize()


def _gallery_metric_filter_options(catalog_meta: list[dict]) -> list[str]:
    """Unique metrics in sheet order, prefixed with 'all'."""
    options = [_TROPHY_METRIC_FILTER_ALL]
    seen: set[str] = set()
    for item in catalog_meta:
        metric = str(item.get("metric", "")).strip()
        if metric and metric not in seen:
            options.append(metric)
            seen.add(metric)
    return options


def _filter_catalog_by_metric(catalog: list[str], catalog_meta: list[dict], metric: str) -> list[str]:
    """Filter badge catalog by metric using pandas (preserves catalog order)."""
    if metric == _TROPHY_METRIC_FILTER_ALL:
        return catalog
    if not catalog_meta:
        return []
    meta_df = pd.DataFrame(catalog_meta)
    if meta_df.empty or "metric" not in meta_df.columns:
        return []
    metric_key = str(metric).strip()
    matched = meta_df.loc[meta_df["metric"].astype(str).str.strip() == metric_key, "name"].astype(str).tolist()
    matched_set = set(matched)
    return [badge for badge in catalog if badge in matched_set]


def _inject_trophy_room_styles() -> None:
    """Scoped layout helpers — main trophy styles live in assets/style.css."""
    st.markdown(
        """
<style>
.trophy-room-marker { display: none; }
[data-testid="column"] .trophy-card { width: 100%; box-sizing: border-box; }
[data-testid="stVerticalBlock"]:has(.trophy-room-marker) [data-testid="column"] {
    padding-top: 0.3rem;
    padding-bottom: 0.3rem;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def _trophy_card_description_text(description: str, *, state: str) -> str:
    text = str(description or "").strip()
    if state == "locked":
        return f"🔒 {text or _TROPHY_LOCKED_DESC_FALLBACK}"
    return text or _TROPHY_DESC_FALLBACK


def _trophy_card_html(
    badge: str,
    *,
    rarity: str,
    state: str,
    state_title: str,
    description: str = "",
) -> str:
    """Slim horizontal trophy row card for the 2-column gallery."""
    slug = badge_rarity_slug(rarity)
    icon = html.escape(_badge_collection_slot_icon(badge))
    label = html.escape(badge)
    if state == "locked":
        label = f"🔒 {label}"
    desc_text = html.escape(_trophy_card_description_text(description, state=state))
    rarity_label = html.escape(RARITY_LABELS_VN.get(rarity, rarity))

    overlays = ""
    status_html = ""
    if state == "active":
        status_html = '<span class="trophy-card-ribbon">Đang mang</span>'
    elif state == "archived":
        status_html = '<span class="trophy-card-ribbon trophy-card-ribbon--archived">Đã đạt</span>'

    if state != "locked" and rarity == "Rare":
        overlays = '<span class="trophy-card-shine" aria-hidden="true"></span>'
    elif state != "locked" and rarity == "Legend":
        overlays = (
            '<span class="trophy-card-holo" aria-hidden="true"></span>'
            '<span class="trophy-card-prism" aria-hidden="true"></span>'
            '<span class="trophy-card-shine" aria-hidden="true"></span>'
        )

    return (
        f'<div class="trophy-card trophy-card--horizontal trophy-card--{state} '
        f'trophy-card--rarity-{slug}">'
        f'<span class="trophy-card-rarity trophy-card-rarity--{slug}">{rarity_label}</span>'
        f"{status_html}"
        f'<span class="trophy-card-icon" aria-hidden="true">{icon}</span>'
        '<div class="trophy-card-body">'
        f'<span class="trophy-card-title">{label}</span>'
        f'<span class="trophy-card-desc">{desc_text}</span>'
        "</div>"
        f"{overlays}"
        "</div>"
    )


def _render_trophy_gallery_grid(
    catalog: list[str],
    *,
    ever_set: set[str],
    current_set: set[str],
    rarity_map: dict[str, str],
    description_map: dict[str, str] | None = None,
    cols: int = _TROPHY_GRID_COLS,
) -> None:
    """Place horizontal trophy cards into a 2-column Streamlit grid."""
    desc_lookup = description_map or {}
    entries: list[tuple[str, str, str, str, str]] = []
    for badge in catalog:
        rarity = normalize_badge_rarity(rarity_map.get(badge))
        description = str(desc_lookup.get(badge, "")).strip()
        if badge in ever_set:
            if badge in current_set:
                state, state_title = "active", "Đang mang"
            else:
                state, state_title = "archived", "Đã từng đạt"
        else:
            state, state_title = "locked", "Chưa mở khóa"
        entries.append((badge, rarity, state, state_title, description))

    _html_inline('<div class="trophy-room-marker" aria-hidden="true"></div>')
    st.markdown('<div class="trophy-room-grid-wrap">', unsafe_allow_html=True)

    for row_start in range(0, len(entries), cols):
        row_entries = entries[row_start : row_start + cols]
        columns = st.columns(cols)
        for col_idx, column in enumerate(columns):
            if col_idx >= len(row_entries):
                break
            badge, rarity, state, state_title, description = row_entries[col_idx]
            card_html = _trophy_card_html(
                badge,
                rarity=rarity,
                state=state,
                state_title=state_title,
                description=description,
            )
            with column:
                st.markdown(card_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)


def render_badge_collection_board(
    bundle: dict,
    highlight_user_id: str | None = None,
) -> None:
    """Trophy Room gallery — grid of custom HTML trophy cards per player."""
    catalog = bundle.get("catalog") or []
    catalog_meta = bundle.get("catalog_meta") or [{"name": n, "rarity": "Common"} for n in catalog]
    rarity_map = bundle.get("rarity_map") or {item["name"]: item.get("rarity", "Common") for item in catalog_meta}
    description_map = bundle.get("description_map") or {
        item["name"]: item.get("description", "") for item in catalog_meta
    }
    rarity_totals = bundle.get("rarity_totals") or {}
    players = bundle.get("players") or []
    total_badges = int(bundle.get("total_badges", 0) or 0)
    total_unlocked = int(bundle.get("total_unlocked", 0) or 0)
    total_slots = int(bundle.get("total_slots", 0) or 0)
    highlight = str(highlight_user_id) if highlight_user_id else None

    if not catalog:
        st.info("Chưa có danh hiệu nào trong hệ thống. Thêm rule tại tab Danh hiệu ẩn trên Lịch thi đấu.")
        return

    if not players:
        st.info("Chưa có người chơi để hiển thị bộ sưu tập.")
        return

    _inject_trophy_room_styles()
    global_pct = _badge_collection_progress_pct(total_unlocked, total_slots)

    rarity_meta_pills = []
    for rarity in BADGE_RARITIES:
        count = int(rarity_totals.get(rarity, 0) or 0)
        if count <= 0:
            continue
        slug = badge_rarity_slug(rarity)
        label = RARITY_LABELS_VN.get(rarity, rarity)
        rarity_meta_pills.append(
            f'<span class="badge-collection-meta-pill badge-collection-meta-pill--{slug}">'
            f"<strong>{count}</strong> {html.escape(label)}"
            "</span>"
        )

    rarity_legend_items = []
    for rarity in BADGE_RARITIES:
        label = RARITY_LABELS_VN.get(rarity, rarity)
        slug = badge_rarity_slug(rarity)
        rarity_legend_items.append(
            f'<span class="badge-collection-rarity-legend-item badge-collection-rarity-legend-item--{slug}">'
            f"{_badge_collection_rarity_sample_html(rarity)}"
            f'<span class="badge-collection-rarity-legend-copy">'
            f"<strong>{html.escape(label)}</strong>"
            f"<span>{html.escape(rarity)}</span>"
            "</span></span>"
        )

    hero = (
        '<div class="badge-collection-hero">'
        '<div class="badge-collection-hero-glow" aria-hidden="true"></div>'
        '<div class="badge-collection-hero-inner">'
        '<span class="badge-collection-eyebrow">Achievement Hall</span>'
        '<h2 class="badge-collection-title">🏅 Bộ sưu tập danh hiệu</h2>'
        '<p class="badge-collection-subtitle">'
        "Toàn bộ huy hiệu từng mở khóa — kể cả danh hiệu không còn đang mang."
        "</p>"
        '<div class="badge-collection-meta">'
        f'<span class="badge-collection-meta-pill"><strong>{total_badges}</strong> danh hiệu trong game</span>'
        f'<span class="badge-collection-meta-pill"><strong>{total_unlocked}</strong> lần mở khóa</span>'
        f'<span class="badge-collection-meta-pill"><strong>{len(players)}</strong> người chơi</span>'
        f'{"".join(rarity_meta_pills)}'
        "</div>"
        '<div class="badge-collection-global-bar">'
        '<div class="badge-collection-global-bar-track">'
        f'<div class="badge-collection-global-bar-fill" style="width:{global_pct}%"></div>'
        "</div>"
        f'<span class="badge-collection-global-bar-label">{global_pct}% tổng tiến độ</span>'
        "</div>"
        '<div class="badge-collection-legend">'
        '<span class="badge-collection-legend-item badge-collection-legend-item--active">'
        '<span class="badge-collection-legend-dot"></span>Đang mang</span>'
        '<span class="badge-collection-legend-item badge-collection-legend-item--archived">'
        '<span class="badge-collection-legend-dot"></span>Đã từng đạt</span>'
        '<span class="badge-collection-legend-item badge-collection-legend-item--locked">'
        '<span class="badge-collection-legend-dot"></span>Chưa mở</span>'
        "</div>"
        '<div class="badge-collection-rarity-legend">'
        f'{"".join(rarity_legend_items)}'
        "</div>"
        "</div></div>"
    )

    _html_inline('<div class="badge-collection-marker" aria-hidden="true"></div>')
    _html(hero)

    player_ids = [str(p.get("user_id", "")) for p in players]
    default_uid = highlight if highlight in player_ids else player_ids[0]

    def _player_label(uid: str) -> str:
        player = next(p for p in players if str(p.get("user_id")) == uid)
        rank = int(player.get("rank", 0) or 0)
        rank_txt = f"#{rank} " if rank > 0 else ""
        name = str(player.get("name", ""))
        unlocked = int(player.get("unlocked_count", 0) or 0)
        you = " (Bạn)" if highlight and uid == highlight else ""
        return f"{rank_txt}{name}{you} — {unlocked}/{total_badges}"

    selected_uid = st.selectbox(
        "🏛️ Chọn phòng danh hiệu",
        player_ids,
        index=player_ids.index(default_uid),
        format_func=_player_label,
        key="trophy_room_player_pick",
    )
    selected = next(p for p in players if str(p.get("user_id")) == str(selected_uid))
    is_me = highlight and str(selected_uid) == highlight
    unlocked = int(selected.get("unlocked_count", 0) or 0)
    pct = _badge_collection_progress_pct(unlocked, total_badges)
    ever_set = set(selected.get("ever_badges") or [])
    current_set = set(selected.get("current_badges") or [])
    rank = int(selected.get("rank", 0) or 0)
    rank_label = f"Hạng #{rank}" if rank > 0 else "Chưa xếp hạng"
    player_name = html.escape(str(selected.get("name", "")))
    you_tag = ' <span class="badge-collection-you">Bạn</span>' if is_me else ""

    panel_head = (
        '<section class="trophy-room-panel">'
        '<div class="trophy-room-panel-head">'
        "<div>"
        f'<h3 class="trophy-room-player-title">{player_name}{you_tag}</h3>'
        f'<p class="trophy-room-player-sub">{html.escape(rank_label)} · '
        f"{unlocked}/{total_badges} danh hiệu đã mở · {pct}% hoàn thành</p>"
        "</div>"
        '<div class="trophy-room-progress">'
        '<div class="trophy-room-progress-track">'
        f'<div class="trophy-room-progress-fill" style="width:{pct}%"></div>'
        "</div>"
        "</div>"
        "</div>"
    )
    st.markdown(panel_head, unsafe_allow_html=True)

    metric_options = _gallery_metric_filter_options(catalog_meta)
    selected_metric = st.radio(
        "Lọc theo loại danh hiệu",
        metric_options,
        horizontal=True,
        format_func=format_gallery_metric,
        key="trophy_room_metric_filter",
        label_visibility="collapsed",
    )
    filtered_catalog = _filter_catalog_by_metric(catalog, catalog_meta, selected_metric)
    filter_label = format_gallery_metric(selected_metric)
    st.caption(f"{len(filtered_catalog)} danh hiệu · {filter_label}")

    if not filtered_catalog:
        st.info(f"Không có danh hiệu nào trong nhóm «{filter_label}».")
    else:
        _render_trophy_gallery_grid(
            filtered_catalog,
            ever_set=ever_set,
            current_set=current_set,
            rarity_map=rarity_map,
            description_map=description_map,
        )

    st.markdown("</section>", unsafe_allow_html=True)

    mini_stats = []
    for player in players:
        uid = str(player.get("user_id", ""))
        stat_class = "trophy-room-mini-stat trophy-room-mini-stat--me" if highlight and uid == highlight else "trophy-room-mini-stat"
        p_name = html.escape(str(player.get("name", "")))
        p_unlocked = int(player.get("unlocked_count", 0) or 0)
        p_pct = _badge_collection_progress_pct(p_unlocked, total_badges)
        mini_stats.append(
            f'<div class="{stat_class}">'
            f"<strong>{p_name}</strong>"
            f"{p_unlocked}/{total_badges} · {p_pct}%"
            "</div>"
        )

    _html(
        '<div class="trophy-room-all-players">'
        f'{"".join(mini_stats)}'
        "</div>"
    )


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
    squad_url = internal_nav_url("/Tra_Cuu_Doi_Bong", {"team": str(fifa_code).strip().upper()})
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


def render_squad_pitch_panel(
    team_name: str,
    fifa_code: str,
    xi_entries: list[dict],
    name_to_fifa: dict | None = None,
    lineup_source: str = "official",
) -> None:
    """Render one team's XI on a CSS pitch (4-2-3-1 layout)."""
    from players_service import short_player_label

    flag = flag_img_html(fifa_code=fifa_code, team_name=team_name, name_to_fifa=name_to_fifa, size="sm")
    squad_url = internal_nav_url("/Tra_Cuu_Doi_Bong", {"team": str(fifa_code).strip().upper()})
    formation = xi_entries[0].get("formation", "4-2-3-1") if xi_entries else "4-2-3-1"
    caption = "Đội hình chính thức" if lineup_source == "official" else "Đội hình dự kiến (theo caps)"

    players_html = ""
    for entry in xi_entries:
        player = entry.get("player") or {}
        media = entry.get("media") or {}
        search_name = entry.get("search_name") or str(player.get("player_name", ""))
        shirt = media.get("shirt_number") or player.get("shirt_number")
        label = short_player_label(search_name, shirt)
        photo = str(media.get("photo_url") or "").strip()
        badge = str(media.get("club_badge_url") or "").strip()
        initials = str(media.get("initials") or "?")
        x = float(entry.get("x_pct", 50))
        y = float(entry.get("y_pct", 50))

        if photo:
            photo_inner = f'<img class="squad-pitch-photo-img" src="{html.escape(photo)}" alt="" loading="lazy" />'
        else:
            photo_inner = f'<span class="squad-pitch-initials">{html.escape(initials)}</span>'

        badge_html = ""
        if badge:
            badge_html = f'<img class="squad-pitch-club-badge" src="{html.escape(badge)}" alt="" loading="lazy" />'

        players_html += (
            f'<div class="squad-pitch-player" style="left:{x}%;top:{y}%;">'
            f'<div class="squad-pitch-photo">{photo_inner}{badge_html}</div>'
            f'<div class="squad-pitch-label">{html.escape(label)}</div>'
            f"</div>"
        )

    if not players_html:
        players_html = '<div class="squad-pitch-empty">Chưa có dữ liệu đội hình</div>'

    _html(
        f'<div class="squad-pitch-wrap">'
        f'<div class="squad-pitch-field">'
        f'<div class="squad-pitch-markings" aria-hidden="true"></div>'
        f"{players_html}"
        f"</div>"
        f'<div class="squad-pitch-footer">'
        f'<div class="squad-pitch-footer-team">{flag}<span>{html.escape(team_name)}</span></div>'
        f'<span class="squad-pitch-formation-badge">{html.escape(formation)}</span>'
        f"</div>"
        f'<div class="squad-pitch-caption">{html.escape(caption)}</div>'
        f'<a class="squad-mini-link squad-pitch-full-link" href="{html.escape(squad_url)}">Xem đội hình đầy đủ →</a>'
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
    _html_inline(
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

    _html_inline('<div class="emoji-action-marker"><div class="emoji-action-title">Sửa nhanh</div></div>')
    with st.container():
        if st.button("⌫ Xóa", key=f"emoji_back_{draft_key}", width="stretch"):
            _queue_name_draft(draft_key, _draft_name(draft_key, saved_name)[:-1])
        if st.button("↩️ Reset", key=f"emoji_reset_{draft_key}", width="stretch"):
            _queue_name_draft(draft_key, saved_name)
        if st.button("🧹 Bỏ icon", key=f"emoji_clear_{draft_key}", width="stretch"):
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
    _html_inline(
        '<div class="pred-card-body"><div class="outcome-picker-shell" aria-hidden="true"></div></div>'
    )

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
    _html_inline('<div class="pred-confirm-marker"></div>')
    confirmed = st.toggle("Chốt trận này", key=dynamic_key, width="stretch")
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
    _html_inline(
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
    _html_inline('<div class="pred-history-mobile-marker" aria-hidden="true"></div>')
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
            if st.button("◀", key="pred_hist_prev", width="stretch", disabled=page <= 1):
                st.session_state["pred_hist_page"] = page - 1
                st.rerun()
        with nav_m:
            st.markdown(
                f'<div class="pred-hist-page-label">{html.escape(pred_history_page_label(page, total_filtered))}</div>',
                unsafe_allow_html=True,
            )
        with nav_r:
            if st.button("▶", key="pred_hist_next", width="stretch", disabled=page >= page_count):
                st.session_state["pred_hist_page"] = page + 1
                st.rerun()
    else:
        _html('<div class="pred-history-mobile-page-slot" aria-hidden="true"></div>')

    mobile_slice, _, _ = slice_pred_history_page(history_df, filt, page)
    render_pred_history_mobile_list(mobile_slice)


def render_pred_history_desktop_table(history_df):
    """Desktop HTML table with flagcdn images (hidden on mobile via CSS)."""
    _html_inline('<div class="pred-history-desktop-marker" aria-hidden="true"></div>')
    if history_df.empty:
        _html('<div class="pred-hist-empty">Không có trận nào trong bộ lọc này.</div>')
        return
    _html(_build_pred_history_desktop_html(history_df))


def render_pred_tabs(labels: list[str]):
    """Pill-style tabs scoped to the prediction page."""
    with st.container():
        _html_inline('<div class="pred-tabs-marker" aria-hidden="true"></div>')
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
        href = internal_nav_url("/Tra_Cuu_Doi_Bong", {"team": str(fifa).upper()})
        name_html = f'<a class="grp-team-link" href="{html.escape(href)}">{name_html}</a>'
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


def render_home_knockout_bracket(
    matches_df: pd.DataFrame,
    teams_df: pd.DataFrame,
    *,
    stop_on_empty: bool = False,
) -> None:
    """Embed knockout bracket (caption + split layout) — shared by Home and Bracket page."""
    from knockout_bracket_service import build_knockout_bracket
    from team_flags import build_name_to_fifa

    _html_inline('<div class="home-knockout-embed" aria-hidden="true"></div>')
    name_to_fifa = build_name_to_fifa(teams_df)
    bracket = build_knockout_bracket(matches_df)

    if not bracket.get("has_data"):
        st.info("Chưa có trận knock-out. Admin cài đặt cặp đấu tại **Góc của Elu → Vòng Knock-out**.")
        if stop_on_empty:
            st.stop()
        return

    ko_matches = matches_df[matches_df["stage_id"].apply(lambda x: int(float(x)) > 1 if pd.notna(x) else False)]
    assigned = ko_matches[
        ((ko_matches["team_a"].notna()) & (ko_matches["team_a"] != "TBD"))
        | ((ko_matches["team_b"].notna()) & (ko_matches["team_b"] != "TBD"))
    ]
    finished = ko_matches[ko_matches["real_score_a"].notna() & ko_matches["real_score_b"].notna()]

    st.caption(
        f"**{len(assigned)}** trận đã gán đội · **{len(finished)}** trận đã có kết quả · "
        "Vuốt ngang trên mobile để xem toàn bộ nhánh."
    )

    _html_inline('<div class="ko-bracket-page-marker" data-layout="split"></div>')
    render_knockout_bracket(bracket, name_to_fifa)
    _html_inline('<div class="home-knockout-spacer" aria-hidden="true"></div>')
