#!/usr/bin/env python3
"""Audit and safely repair the predictions worksheet header."""

from __future__ import annotations

import sys
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from google.oauth2.service_account import Credentials
import gspread

from data_service import (
    PREDICTIONS_COLUMNS,
    _predictions_header_offset,
    _row_looks_like_prediction,
    read_predictions_sheet,
    repair_predictions_sheet_header,
)


def main() -> int:
    secrets_path = ROOT / ".streamlit" / "secrets.toml"
    with secrets_path.open("rb") as f:
        secrets = tomllib.load(f)

    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sh = client.open_by_key(secrets["spreadsheet_id"])
    ws = sh.worksheet("predictions")

    raw = ws.get_all_values()
    offset = _predictions_header_offset(raw)
    data_rows = sum(1 for row in raw[offset:] if _row_looks_like_prediction(row))
    preds_df = read_predictions_sheet(sh)

    print("=== Predictions sheet audit ===")
    print(f"Total rows in sheet (incl. header): {len(raw)}")
    print(f"Header offset: {offset} ({'has header' if offset else 'NO header — data starts row 1'})")
    print(f"Data rows (heuristic): {data_rows}")
    print(f"Rows loaded by app: {len(preds_df)}")
    if raw:
        print(f"Row 1: {raw[0]}")
    if len(raw) > 1:
        print(f"Row 2: {raw[1]}")

    if len(sys.argv) > 1 and sys.argv[1] == "--repair":
        action = repair_predictions_sheet_header(ws)
        preds_after = read_predictions_sheet(sh)
        print(f"\nRepair action: {action}")
        print(f"Rows loaded after repair: {len(preds_after)}")
    else:
        print("\nRun with --repair to insert/fix header without deleting data rows.")
        print("If rows in sheet >> rows loaded, repair may help.")
        print("If sheet is empty, restore from Google Sheets Version history first.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
