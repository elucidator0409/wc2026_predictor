"""Sync kickoff_at in data/matches.csv from official FIFA schedule (UTC+7)."""

import pandas as pd

from schedule_service import enrich_matches_with_schedule, load_wc_schedule

matches_df = pd.read_csv("data/matches.csv")
schedule_df = load_wc_schedule()
enriched = enrich_matches_with_schedule(matches_df, schedule_df)
matches_df["kickoff_at"] = enriched["kickoff_at"]
matches_df.to_csv("data/matches.csv", index=False)

print(f"✅ Đã cập nhật kickoff_at (UTC+7) cho {len(matches_df)} trận trong data/matches.csv")
