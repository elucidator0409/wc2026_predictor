"""Verify sidebar click-outside-to-close at all viewport widths."""
from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright not installed; run: pip install playwright && playwright install chromium")
    sys.exit(1)

URL = "http://localhost:8501/"
WIDTHS = [767, 768, 1100, 1280, 1331, 1440, 1920]


def verify_width(width: int) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(URL, wait_until="networkidle", timeout=90000)
        page.wait_for_selector('[data-testid="stSidebar"]', timeout=60000)
        page.wait_for_timeout(600)

        # Sidebar may start open at wide widths — collapse first so expand FAB is available.
        page.evaluate(
            """() => {
              const sidebar = document.querySelector('[data-testid="stSidebar"]');
              if (sidebar?.getAttribute('aria-expanded') !== 'true') return;
              const btn =
                document.querySelector('[data-testid="stSidebarCollapseButton"] button') ||
                document.querySelector('[data-testid="stSidebarCollapseButton"]');
              btn?.click();
            }"""
        )
        page.wait_for_timeout(900)
        page.wait_for_selector('[data-testid="stExpandSidebarButton"]', timeout=60000)

        overlay = page.evaluate(
            """() => ({
              version: window.top.__wcSidebarOverlayVersion ?? window.__wcSidebarOverlayVersion,
            })"""
        )

        expand_style = page.evaluate(
            """() => {
              const expand = document.querySelector('[data-testid="stExpandSidebarButton"]');
              if (!expand) return null;
              const cs = getComputedStyle(expand);
              const after = getComputedStyle(expand, '::after');
              return {
                width: cs.width,
                border: cs.borderWidth,
                bg: cs.backgroundImage !== 'none',
                menuLabel: after.content,
              };
            }"""
        )

        expand = page.locator('[data-testid="stExpandSidebarButton"]')
        expand.first.click(force=True)
        page.wait_for_timeout(900)

        opened = page.evaluate(
            """() => {
              const sidebar = document.querySelector('[data-testid="stSidebar"]');
              const backdrop = document.getElementById('wc-sidebar-backdrop');
              const bdStyle = backdrop ? getComputedStyle(backdrop) : null;
              const sidebarStyle = sidebar ? getComputedStyle(sidebar) : null;
              const expand = document.querySelector('[data-testid="stExpandSidebarButton"]');
              const expandStyle = expand ? getComputedStyle(expand) : null;
              const collapse = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
              const collapseStyle = collapse ? getComputedStyle(collapse) : null;
              const expandHidden = !expand
                || expandStyle?.visibility === 'hidden'
                || expandStyle?.opacity === '0';
              return {
                ariaExpanded: sidebar?.getAttribute('aria-expanded'),
                backdrop: !!backdrop,
                backdropZ: bdStyle?.zIndex,
                backdropPos: bdStyle?.position,
                sidebarPos: sidebarStyle?.position,
                wcOpen: document.body.classList.contains('wc-sidebar-open'),
                expandHidden,
                expandGone: !expand,
                collapseBorder: collapseStyle?.borderWidth,
              };
            }"""
        )

        if not opened.get("backdrop"):
            browser.close()
            return {
                "width": width,
                "opened": opened,
                "expandFab": expand_style,
                "clickOutsideWorks": False,
                "overlay": overlay,
                "note": "backdrop expected at all widths",
            }

        page.locator("#wc-sidebar-backdrop").click(force=True)
        page.wait_for_timeout(900)

        closed = page.evaluate(
            """() => {
              const expand = document.querySelector('[data-testid="stExpandSidebarButton"]');
              const expandStyle = expand ? getComputedStyle(expand) : null;
              return {
                ariaExpanded: document.querySelector('[data-testid="stSidebar"]')?.getAttribute('aria-expanded'),
                backdrop: !!document.getElementById('wc-sidebar-backdrop'),
                expandWidth: expandStyle?.width,
                expandBorder: expandStyle?.borderWidth,
              };
            }"""
        )
        browser.close()

        return {
            "width": width,
            "overlay": overlay,
            "expandFab": expand_style,
            "opened": opened,
            "closed": closed,
            "clickOutsideWorks": closed.get("ariaExpanded") == "false" and not closed.get("backdrop"),
        }


def main() -> None:
    results = [verify_width(w) for w in WIDTHS]
    print(json.dumps(results, indent=2))
    failures = [
        r
        for r in results
        if r.get("error")
        or not r.get("clickOutsideWorks")
        or (
            r.get("opened", {}).get("wcOpen")
            and not r.get("opened", {}).get("expandHidden")
        )
        or (
            r.get("overlay", {}).get("version") is not None
            and r.get("overlay", {}).get("version") < 6
        )
        or (
            r.get("expandFab")
            and r.get("expandFab", {}).get("width") == "28px"
        )
        or (
            r.get("expandFab", {}).get("menuLabel")
            and r.get("expandFab", {}).get("menuLabel") not in ('""', "none", "")
        )
        or r.get("opened", {}).get("sidebarPos") != "fixed"
    ]
    if failures:
        print(f"\nFAILED at widths: {[f['width'] for f in failures]}")
        sys.exit(1)
    print("\nOK — click-outside works at all tested viewport widths")


if __name__ == "__main__":
    main()
