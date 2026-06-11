"""Sidebar overlay breakpoint alignment (Sprint 1.8 / 1.85 / 2.25)."""
from __future__ import annotations

import os
import re
import unittest


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class SidebarOverlayBreakpointsTest(unittest.TestCase):
    def setUp(self) -> None:
        with open(os.path.join(ROOT, "assets", "style.css"), encoding="utf-8") as f:
            self.css = f.read()
        with open(os.path.join(ROOT, "ui_components.py"), encoding="utf-8") as f:
            self.ui = f.read()

    def test_overlay_applies_at_all_viewports(self) -> None:
        """Sidebar fixed overlay + full-width main are global, not breakpoint-scoped."""
        self.assertNotIn('matchMedia("(max-width: 1330px)")', self.ui)
        self.assertNotRegex(
            self.css,
            r"@media\s*\(\s*max-width:\s*1330px\s*\)[^{]*\[data-testid=\"stSidebar\"\]",
        )
        self.assertRegex(
            self.css,
            r"/\* Sidebar overlay.*?\*/\s*\[data-testid=\"stSidebar\"\]\s*\{[^}]*position:\s*fixed",
            re.DOTALL,
        )

    def test_backdrop_styles_not_scoped_to_mobile_only(self) -> None:
        """Regression: backdrop used to live only under max-width:768px."""
        self.assertIn("#wc-sidebar-backdrop", self.css)
        self.assertNotRegex(self.css, r"@media\s*\(\s*max-width:\s*768px\s*\)[^{]*#wc-sidebar-backdrop")

        global_backdrop = re.search(
            r"/\* Backdrop base.*?\*/\s*#wc-sidebar-backdrop\s*\{",
            self.css,
            re.DOTALL,
        )
        self.assertIsNotNone(global_backdrop)

    def test_boot_script_injects_into_top_document(self) -> None:
        self.assertIn("window.top", self.ui)
        self.assertIn("collapseSidebar", self.ui)
        self.assertIn("__reactProps", self.ui)
        self.assertIn("WC_SIDEBAR_OVERLAY_VERSION = 6", self.ui)
        self.assertIn("scheduleBackdropSync", self.ui)

    def test_menu_fab_icon_only_at_all_breakpoints(self) -> None:
        self.assertIn("--menu-fab-bg", self.css)
        self.assertIn("wc-sidebar-open [data-testid=\"stExpandSidebarButton\"]", self.css)
        self.assertIn("stSidebarCollapseButton", self.css)
        self.assertIn("::before", self.css)
        self.assertIn('[data-testid="stExpandSidebarButton"],', self.css)
        self.assertNotIn('content: "Menu"', self.css)
        self.assertNotRegex(
            self.css,
            r"@media\s*\(\s*min-width:\s*901px\s*\)[^{]*stExpandSidebarButton[^}]*::after",
            re.DOTALL,
        )

    def test_expand_sidebar_button_supported(self) -> None:
        self.assertIn("stExpandSidebarButton", self.css)
        self.assertIn("stExpandSidebarButton", self.ui)

    def test_menu_fab_fixed_not_overridden_by_relative(self) -> None:
        """Regression: a later rule set position:relative on expand FAB, causing left gutter."""
        expand_block = re.search(
            r"\[data-testid=\"stExpandSidebarButton\"\],\s*"
            r"\[data-testid=\"stExpandSidebarButton\"\] button,\s*"
            r"\[data-testid=\"collapsedControl\"\],\s*"
            r"\[data-testid=\"collapsedControl\"\] button\s*\{([^}]+)\}",
            self.css,
            re.DOTALL,
        )
        self.assertIsNotNone(expand_block)
        body = expand_block.group(1)
        self.assertIn("position: fixed", body)
        self.assertNotIn("position: relative", body)
        self.assertIn("stToolbar", self.css)
        self.assertIn("margin-left: 0", self.css)

    def test_sidebar_boot_uses_components_html(self) -> None:
        """Streamlit 1.58: components.html injects boot script; iframe(srcdoc=) is unsupported."""
        self.assertIn("components.html", self.ui)
        self.assertNotIn("components.iframe", self.ui)


if __name__ == "__main__":
    unittest.main()
