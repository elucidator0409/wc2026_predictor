"""Capture prediction page at 768px for iPad mini verification."""
from __future__ import annotations

import hmac
import hashlib
import sys
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright not installed; run: pip install playwright && playwright install chromium")
    sys.exit(1)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

SALT = "Wc2026_elucidator"
UID = "U01"


def auth_sig(user_id: str) -> str:
    return hmac.new(SALT.encode(), user_id.encode(), hashlib.sha256).hexdigest()


def main() -> None:
    url = f"http://localhost:8501/Du_Doan?uid={UID}&sig={auth_sig(UID)}"
    widths = [768, 769, 1100, 1200]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for w in widths:
            page = browser.new_page(viewport={"width": w, "height": 1024})
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_selector(".pred-card-header", timeout=60000)
            page.wait_for_timeout(1500)
            shot = OUT / f"pred-{w}px.png"
            page.screenshot(path=str(shot), full_page=True)
            cols = page.evaluate(
                """() => {
                  const form = document.querySelector('[data-testid="stForm"]');
                  const bc = document.querySelector('.block-container');
                  const card = document.querySelector('[data-testid="stVerticalBlockBorderWrapper"]:has(.pred-card-header), [data-testid="stVerticalBlockBorderWrapper"]');
                  const cardHeader = document.querySelector('.pred-card-header');
                  const sidebar = document.querySelector('[data-testid="stSidebar"]');
                  const chain = [];
                  let el = form;
                  while (el && el !== document.body) {
                    const r = el.getBoundingClientRect();
                    chain.push({ tag: el.tagName, testid: el.getAttribute('data-testid'), className: el.className?.slice?.(0,40), width: Math.round(r.width) });
                    el = el.parentElement;
                  }
                  return {
                    cards: document.querySelectorAll('.pred-card-header').length,
                    formWidth: form ? form.getBoundingClientRect().width : 0,
                    cardWidth: cardHeader ? cardHeader.getBoundingClientRect().width : 0,
                    containerWidth: bc ? bc.getBoundingClientRect().width : 0,
                    sidebarWidth: sidebar ? sidebar.getBoundingClientRect().width : 0,
                    viewport: window.innerWidth,
                    chain,
                  };
                }"""
            )
            print(f"{w}px: {cols}")
            page.close()
        browser.close()

    print(f"Screenshots saved to {OUT}")


if __name__ == "__main__":
    main()
