"""Push official UTC+7 kickoff times to Google Sheets matches worksheet."""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from data_service import init_connection, read_sheet
from schedule_service import enrich_matches_with_schedule, load_wc_schedule
from ui_components import _get_col_letter


def main() -> None:
    sh = init_connection()
    matches_raw = read_sheet(sh, "matches")
    schedule_df = load_wc_schedule()
    enriched = enrich_matches_with_schedule(matches_raw, schedule_df)

    kickoff_map = dict(
        zip(
            enriched["match_number"].astype(int),
            enriched["kickoff_at"],
        )
    )

    ws = sh.worksheet("matches")
    data = ws.get_all_values()
    if not data:
        print("⚠️ Worksheet matches trống.")
        return

    headers = data[0]
    if "kickoff_at" not in headers:
        print("⚠️ Không tìm thấy cột kickoff_at.")
        return

    kickoff_col = headers.index("kickoff_at")
    match_col = headers.index("match_number") if "match_number" in headers else headers.index("id")
    updates = []

    for row_idx, row in enumerate(data[1:], start=2):
        if len(row) <= max(kickoff_col, match_col):
            continue
        try:
            match_no = int(float(row[match_col]))
        except (ValueError, TypeError):
            continue
        new_kickoff = kickoff_map.get(match_no)
        if not new_kickoff:
            continue
        col_letter = _get_col_letter(kickoff_col + 1)
        updates.append({"range": f"{col_letter}{row_idx}", "values": [[new_kickoff]]})

    if not updates:
        print("⚠️ Không có dòng nào cần cập nhật.")
        return

    ws.batch_update(updates)
    print(f"✅ Đã cập nhật kickoff_at (UTC+7) cho {len(updates)} trận trên Google Sheets.")


if __name__ == "__main__":
    main()
