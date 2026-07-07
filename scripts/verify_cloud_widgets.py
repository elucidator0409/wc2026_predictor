"""Verify tab pill bar + prediction segmented control styling on local Streamlit."""
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
SALT = "Wc2026_elucidator"
UID = "U01"


def auth_sig(user_id: str) -> str:
    return hmac.new(SALT.encode(), user_id.encode(), hashlib.sha256).hexdigest()


def _tab_list_styles(page) -> dict | None:
    return page.evaluate(
        """() => {
          const markers = ['.lb-main-tabs-marker', '.pred-tabs-marker'];
          for (const m of markers) {
            const root = document.querySelector(m)?.closest('[data-testid="stVerticalBlock"], [data-testid="stVerticalBlockBorderWrapper"]');
            const tabList = root?.querySelector('[data-baseweb="tab-list"]');
            if (!tabList) continue;
            const cs = getComputedStyle(tabList);
            return {
              marker: m,
              borderWidth: cs.borderWidth,
              backgroundColor: cs.backgroundColor,
              borderRadius: cs.borderRadius,
            };
          }
          return null;
        }"""
    )


def _segmented_active_diff(page) -> dict | None:
    return page.evaluate(
        """() => {
          const shell = document.querySelector('.outcome-picker-shell');
          if (!shell) return null;
          const block = shell.closest('[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stVerticalBlock"]');
          const group = block?.querySelector('[data-testid="stButtonGroup"] [role="radiogroup"]');
          if (!group) return { error: 'no radiogroup' };
          const buttons = [...group.querySelectorAll('button')];
          if (buttons.length < 3) return { error: 'expected 3 buttons' };
          const activeIdx = buttons.findIndex(
            (b) => b.getAttribute('data-testid') === 'stBaseButton-segmented_controlActive'
              || b.getAttribute('aria-checked') === 'true'
          );
          if (activeIdx < 0) return { error: 'no active button' };
          const inactiveIdx = buttons.findIndex(
            (b, i) => i !== activeIdx
              && b.getAttribute('data-testid') !== 'stBaseButton-segmented_controlActive'
              && b.getAttribute('aria-checked') !== 'true'
          );
          const activeCs = getComputedStyle(buttons[activeIdx]);
          const inactiveCs = getComputedStyle(buttons[inactiveIdx >= 0 ? inactiveIdx : 0]);
          const groupCs = getComputedStyle(group);
          return {
            activeIdx,
            activeShadow: activeCs.boxShadow,
            inactiveShadow: inactiveCs.boxShadow,
            activeBorder: activeCs.borderColor,
            inactiveBorder: inactiveCs.borderColor,
            groupDisplay: groupCs.display,
            groupColumns: groupCs.gridTemplateColumns,
            buttonWidths: buttons.map((b) => Math.round(b.getBoundingClientRect().width)),
          };
        }"""
    )


def main() -> None:
    checks = [
        ("BXH tabs", f"http://localhost:8501/Bang_Xep_Hang"),
        ("Pred tabs + cards", f"http://localhost:8501/Du_Doan?uid={UID}&sig={auth_sig(UID)}"),
    ]
    failures: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        for label, url in checks:
            page = browser.new_page(viewport={"width": 1280, "height": 900})
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(2000)
                tab_info = _tab_list_styles(page)
                print(f"{label} tab-list:", tab_info)
                if not tab_info:
                    failures.append(f"{label}: no styled tab-list found")
                elif tab_info.get("borderWidth", "0px") in ("0px", "0"):
                    failures.append(f"{label}: tab-list border missing")

                if "Pred" in label:
                    seg = _segmented_active_diff(page)
                    print(f"{label} segmented:", seg)
                    if not seg:
                        failures.append(f"{label}: no outcome picker")
                    elif seg.get("error"):
                        failures.append(f"{label}: {seg['error']}")
                    elif seg.get("activeShadow") == seg.get("inactiveShadow"):
                        failures.append(f"{label}: active/inactive buttons same box-shadow")
                    elif seg.get("groupDisplay") != "grid":
                        failures.append(f"{label}: radiogroup not display:grid ({seg.get('groupDisplay')})")
                    else:
                        widths = seg.get("buttonWidths") or []
                        if len(widths) == 3 and max(widths) - min(widths) > 40:
                            failures.append(f"{label}: uneven button widths {widths}")
            except Exception as exc:
                failures.append(f"{label}: {exc}")
            finally:
                page.close()
        browser.close()

    if failures:
        print("\nFAILED:")
        for f in failures:
            print(" -", f)
        sys.exit(1)
    print("\nOK: tab-list + segmented checks passed")


if __name__ == "__main__":
    main()
