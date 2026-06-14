# Google Sheets migration (predictions tab)

Update the header row on the `predictions` worksheet to:

```
user_id,match_id,pred_outcome,pred_advanced_team_id,timestamp
```

Remove legacy columns: `pred_score_a`, `pred_score_b`.

## Khôi phục khi mất / lệch dữ liệu

1. **Google Sheets → File → Version history** → chọn bản trước khi lỗi → **Restore**
2. Hoặc chạy audit (không ghi):
   ```bash
   python scripts/repair_predictions_sheet.py
   ```
3. Sửa header an toàn (chèn header nếu thiếu, không xóa dòng dữ liệu):
   ```bash
   python scripts/repair_predictions_sheet.py --repair
   ```
4. Trong app: **Góc của Elu → Thêm người chơi → Sửa header predictions (an toàn)**

**Không** dùng hàm ghi đè header cũ khi row 1 đang là dữ liệu — app mới đã thay bằng `repair_predictions_sheet_header` (insert row).

## pred_outcome values

| Code | Meaning |
|------|---------|
| `A` | Team A wins |
| `D` | Draw |
| `B` | Team B wins |

Legacy rows using `W` / `L` are still read correctly (`W`→`A`, `L`→`B`). New saves write `A` / `D` / `B`.

Clear old test rows if any. The app writes only the new schema when users save predictions.
