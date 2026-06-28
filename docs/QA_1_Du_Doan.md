# QA — Trang Dự đoán (`pages/1_Du_Doan.py`)

Manual test matrix (senior QA). Automated coverage: `tests/test_pred_submit.py`, `tests/test_lineup_service.py`.

## Precondition

- User đã login (`authenticated_user_id` set)
- Trận test: 1 vòng bảng (`stage_id=1`) + 1 knock-out (`stage_id>1`, đội không TBD)
- Trận chưa `is_locked`, chưa có `real_score_a/b`
- Tab Sheet `lineups` có thể nhập qua Admin → **Đội hình**

---

## P — Outcome picker (A / Hòa / B)

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| P01 | Chọn A thắng | segmented_control → A | Badge draft; không PEN |
| P02 | Chọn B thắng | → B | Không PEN picker |
| P03 | Hòa vòng bảng | → D, stage_id=1 | Không PEN |
| P04 | Hòa knock-out | → D, stage_id>1 | Hiện `pen-picker-shell` + selectbox ngay (rerun) |
| P05 | KO: Hòa → A | D rồi A | PEN ẩn; session `adv_*` pop |
| P06 | KO: A → Hòa | A rồi D | PEN hiện lại |
| P07 | Hydrate pred cũ | Reload sau khi đã lưu B | Default B; badge "Đã dự đoán" |

Code: `outcome` L176–182; `show_pen_picker` L216–230.

---

## K — PEN knock-out

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| K01 | Lưu Hòa + PEN A | D + team_a + Chốt + Lưu | `pred_outcome=D`, `pred_advanced_team_id=id(A)` |
| K02 | Lưu Hòa + PEN B | D + team_b + Lưu | `adv_id` = id(B) |
| K03 | Đổi PEN | PEN A → B → Lưu | Upsert adv mới |
| K04 | Hòa → A | Đã lưu D+PEN → A → Lưu | `pred_outcome=A`, `adv_id=""` |
| K05 | Không chốt | D+PEN, không Chốt | Warning chưa chốt |
| K06 | TBD | team TBD + D | Không PEN |

Code: submit `build_pred_adv_fields` L311+; `adv_for_save` L232–236.

---

## S — Batch save & re-bet

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| S01 | Lưu 1 trận | Chốt + Lưu | Toast; tab Lịch sử có pred |
| S02 | Lưu nhiều trận | Chốt 3 + Lưu | 3 upsert; toggle reset |
| S03 | Re-bet | Lưu A → đổi B → Lưu | Một row `(user_id, match_id)` |
| S04 | Draft | Đổi outcome, không Chốt | Sheet không đổi |
| S05 | Lock race | Admin khóa trước Lưu | Skip + toast cảnh báo |
| S06 | Sau save | Lưu OK | pop session keys; rerun |

Code: L289–335; `upsert_user_predictions`.

---

## L — Đội hình Sheet

| ID | Scenario | Steps | Expected |
|----|----------|-------|----------|
| L01 | Trước T-60 | kickoff > 60 phút | Info chưa công bố; không pitch |
| L02 | Trong T-60, Sheet đủ | Admin nhập 11×2 | Pitch 2 đội; tên từ Sheet |
| L03 | Trong T-60, thiếu | lineups trống | Warning chưa có đội hình |
| L04 | Sau kickoff | Trận đã đá | Không còn trong upcoming |

Code: `lineups_window_open`, `get_match_lineups`, expander L184+.

---

## R — Regression

| ID | Scenario | Expected |
|----|----------|----------|
| R01 | F5 sau login | Session + uid/sig URL |
| R02 | Layout 2 cột | >= 3 trận: 2 cột; keys unique |
| R03 | Tab Lịch sử | KO Hòa hiện đội PEN |
| R04 | Expander đội hình | Không block picker/PEN/Chốt |

---

## Automated run

```bash
.venv/bin/python -m pytest tests/test_pred_submit.py tests/test_lineup_service.py -q
```
