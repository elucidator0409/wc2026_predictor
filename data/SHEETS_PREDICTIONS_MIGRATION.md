# Google Sheets migration (predictions tab)

Update the header row on the `predictions` worksheet to:

```
user_id,match_id,pred_outcome,pred_advanced_team_id,timestamp
```

Remove legacy columns: `pred_score_a`, `pred_score_b`.

## pred_outcome values

| Code | Meaning |
|------|---------|
| `A` | Team A wins |
| `D` | Draw |
| `B` | Team B wins |

Legacy rows using `W` / `L` are still read correctly (`W`→`A`, `L`→`B`). New saves write `A` / `D` / `B`.

Clear old test rows if any. The app writes only the new schema when users save predictions.
