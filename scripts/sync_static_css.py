#!/usr/bin/env python3
"""Rebuild static/style.css and assets/style-critical.css from source CSS files."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"


def main() -> None:
    style = (ASSETS / "style.css").read_text(encoding="utf-8")
    cloud = (ASSETS / "style-cloud-bridge.css").read_text(encoding="utf-8")
    segmented = (ASSETS / "style-pred-segmented-bridge.css").read_text(encoding="utf-8")
    lb_responsive = (ASSETS / "style-lb-responsive-bridge.css").read_text(encoding="utf-8")
    tabs_layout = (ASSETS / "style-tabs-layout-bridge.css").read_text(encoding="utf-8")

    root_snip = style.split(":root {", 1)[1]
    root_block = ":root {" + root_snip.split("}\n", 1)[0] + "}\n"

    critical = (
        "/* Critical widget-bridge CSS for Streamlit Cloud */\n"
        + root_block
        + "\n"
        + cloud
        + "\n"
        + segmented
        + "\n"
        + lb_responsive
        + "\n"
        + tabs_layout
    )
    (ASSETS / "style-critical.css").write_text(critical, encoding="utf-8")

    bundle = style + "\n\n/* Cloud bridges */\n" + cloud + "\n" + segmented + "\n" + lb_responsive + "\n" + tabs_layout
    static_dir = ROOT / "static"
    static_dir.mkdir(exist_ok=True)
    (static_dir / "style.css").write_text(bundle, encoding="utf-8")

    print(f"Updated {ASSETS / 'style-critical.css'} ({len(critical)} bytes)")
    print(f"Updated {static_dir / 'style.css'} ({len(bundle)} bytes)")


if __name__ == "__main__":
    main()
