"""Sidebar overlay breakpoint alignment (Sprint 1.8 / 1.85)."""
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

    def test_overlay_breakpoint_is_1330px_in_js_and_css(self) -> None:
        self.assertIn('matchMedia("(max-width: 1330px)")', self.ui)
        self.assertRegex(self.css, r"@media\s*\(\s*max-width:\s*1330px\s*\)")

    def test_backdrop_styles_not_scoped_to_mobile_only(self) -> None:
        """Regression: backdrop used to live only under max-width:768px."""
        self.assertIn("#wc-sidebar-backdrop", self.css)
        self.assertNotRegex(self.css, r"@media\s*\(\s*max-width:\s*768px\s*\)[^{]*#wc-sidebar-backdrop")

        # Global backdrop block must exist outside the 1330px overlay block.
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
        self.assertIn("WC_SIDEBAR_OVERLAY_VERSION = 5", self.ui)
        self.assertIn("scheduleBackdropSync", self.ui)

    def test_menu_fab_sprint_22_styles(self) -> None:
        self.assertIn("--menu-fab-bg", self.css)
        self.assertIn("wc-sidebar-open [data-testid=\"stExpandSidebarButton\"]", self.css)
        self.assertIn("stSidebarCollapseButton", self.css)
        self.assertIn("::before", self.css)
        self.assertIn('[data-testid="stExpandSidebarButton"],', self.css)
        self.assertIn('content: "Menu"', self.css)
        self.assertIn("::after", self.css)
        self.assertIn("@media (min-width: 901px)", self.css)

    def test_expand_sidebar_button_supported(self) -> None:
        self.assertIn("stExpandSidebarButton", self.css)
        self.assertIn("stExpandSidebarButton", self.ui)


if __name__ == "__main__":
    unittest.main()
