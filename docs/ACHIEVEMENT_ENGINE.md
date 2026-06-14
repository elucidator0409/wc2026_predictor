# HP Bar + Achievement Engine — Ghi nhận triển khai

> Tài liệu nội bộ mô tả ý tưởng, thiết kế, triển khai và các lần chỉnh sửa sau go-live của tính năng **Sinh lực (HP bar)**, **Danh hiệu ẩn (Achievements)** và **Bộ sưu tập danh hiệu** trên Bảng Xếp Hạng WC 2026 Predictor.  
> Dùng làm nguồn cho báo cáo cuối kì / demo sau này.

**Cập nhật lần cuối:** 14/06/2026

---

## 1. Bối cảnh & mục tiêu

### Vấn đề ban đầu
- Cột **Phạt** trên BXH chỉ hiển thị số khô (`30k`) — khó cảm nhận “còn bao nhiêu ngân sách phạt”.
- Nhóm chơi muốn thêm lớp **gamification ẩn**: danh hiệu kiếm được khi đạt điều kiện thống kê, **không** ảnh hưởng thứ hạng.

### Mục tiêu đã chốt
1. Thay cột Phạt bằng thanh **Sinh lực** kiểu RPG (HTML/CSS, không dùng `st.column_config.ProgressColumn`).
2. Rule engine đọc quy tắc từ tab Google Sheet **`Achievements`** — admin thêm/sửa rule qua UI, không hard-code JSON local.
3. Đánh giá rule an toàn: **không** dùng `eval()`; whitelist metric + operator.
4. HP **không** đổi thứ tự BXH; `fines` vẫn là tie-break như cũ.
5. Tab **Bộ sưu tập** — gallery danh hiệu từng user (đã từng đạt + chưa mở), có mô tả và lọc theo loại metric.

---

## 2. Lịch sử phát triển (timeline)

| Giai đoạn | Nội dung |
|-----------|----------|
| **Ý tưởng** | Gamify BXH: “máu” = ngân sách phạt 1.400.000 VNĐ; danh hiệu ẩn theo chỉ số (phạt nhiều, chuỗi thắng, v.v.). |
| **Thiết kế (plan)** | Plan `HP Bar + Hidden Achievements`: tách `achievement_service.py`, sheet I/O trong `data_service.py`, admin tab trong `pages/2_Lich_Thi_Dau.py`, wire BXH trong `pages/3_Bang_Xep_Hang.py`. |
| **Triển khai v1** | HP bar desktop/mobile, rule engine, tab **🏅 Danh hiệu ẩn**, badges dưới tên, tests `test_achievement_service.py`. |
| **Fix HP logic** | Ban đầu `remaining_hp = 140 - fines` (sai). Sửa: `fines` lưu đơn vị 10k (`10` = 10.000 VNĐ) → **1 HP = 10k** → `hp_lost = fines // 10`. |
| **UX Sinh lực** | Đổi nhãn Máu → Sinh lực; căn trái thanh HP; mobile stats band có border như desktop. |
| **UX mobile** | Phong độ 3 trận; nhãn thống nhất **Sinh lực** (desktop + mobile). |
| **Fix UI vỡ** | Cột Danh hiệu + Tỉ lệ làm grid quá chật → bỏ cột Tỉ lệ; danh hiệu chuyển **dưới tên**; stats band `min-width` + nowrap. |
| **Fix operator `==`** | Google Sheets coi `==` là công thức → ghi `eq`, đọc map về `==`. |
| **Badge chips** | `badges` là `list[str]`; mỗi chip màu hash HSL deterministic (`badge_chip_style`). |
| **Tier phạt độc quyền** | `total_penalties`: chỉ **một** badge `>=` (tier cao nhất) và **một** badge `<=` (tier thấp nhất) — tránh mọi người nhận hết tier. |
| **Streak achievement** | Đổi từ max-ever sang **chuỗi gần nhất** (`build_per_user_streak_recent`) — khớp sidebar + rule. |
| **Admin sửa rule** | `update_achievement_row()` + form chỉnh sửa theo `id` trên tab Danh hiệu ẩn. |
| **Tab Bộ sưu tập** | Tab giữa Leaderboard ↔ Phân tích: replay lịch sử trận → union badge từng đạt (`build_per_user_badge_history`). |
| **Rarity** | Cột sheet `rarity`: Common / Rare / Legend — overlay holo/shine trên chip & gallery; nhãn VN: Thường / Hiếm / Huyền thoại. |
| **Description** | Cột sheet `description` — hiển thị trực tiếp trong thẻ gallery (không tooltip). |
| **Gallery UX** | Trophy room: thẻ ngang slim, grid `st.columns(2)`, lọc metric (`st.radio` horizontal), chọn phòng từng user. |
| **Sidebar streak fix** | Card Chuỗi Thắng/Thua: đổi `_max_streak_window` → `_trailing_streak_window` — số trận khớp lịch sử pick gần nhất. |

---

## 3. Kiến trúc tổng quan

```
Google Sheets — tab Achievements
├── id, badge_name, metric, operator, threshold_value, rarity, description
└── data_service.read_achievements_sheet() / append / update

leaderboard_service.build_leaderboard_with_dynamics()
        ↓ enrich_leaderboard_dynamics()
        ↓ enrich_leaderboard_hp()

pages/3_Bang_Xep_Hang.py
├── Tab 🏆 Leaderboard
│     ↓ apply_achievements_to_leaderboard() → badges
│     ↓ render_leaderboard_dataframe(badge_rarity_map)
├── Tab 🏅 Bộ sưu tập
│     ↓ build_badge_collection_bundle()
│     ↓ render_badge_collection_board() — filter metric + grid 2 cột
└── Tab 📊 Phân tích dữ liệu hành vi

pages/2_Lich_Thi_Dau.py — tab 🏅 Danh hiệu ẩn
        ↓ append_achievement_row() / update_achievement_row()

leaderboard_gamification_service.compute_streak_milestones()
        ↓ _trailing_streak_window() — sidebar Chuỗi Thắng/Thua
```

---

## 4. Sinh lực (HP Bar)

### Công thức

| Hằng số | Giá trị | Ý nghĩa |
|---------|---------|---------|
| `MAX_HP` | 140 | Ngân sách 1.400.000 VNĐ |
| `FINE_UNIT_HP` | 10 | Mỗi `10` trong cột `fines` = 10.000 VNĐ = **1 HP** |

```python
hp_lost = fines // 10
remaining_hp = max(0, 140 - hp_lost)
remaining_hp_pct = round(remaining_hp / 140 * 100, 1)
```

**Ví dụ:** 3 trận sai → `fines = 30` (30k VNĐ) → mất 3 HP → **137/140**.

### Hiển thị UI
- **Desktop / Mobile:** cột **Sinh lực** trong stats band (cùng Phong độ, Đúng, Bỏ lỡ desktop).
- Màu thanh: xanh >50%, vàng 20–50%, đỏ <20%.
- File: `ui_components._lb_hp_bar_html()`, `assets/style.css` (`.lb-hp-bar*`).

---

## 5. Achievement Rule Engine

### Schema Google Sheet — tab `Achievements`

| Cột | Kiểu | Mô tả |
|-----|------|-------|
| `id` | text | `A001`, `A002`, … (auto khi append) |
| `badge_name` | text | Tên hiển thị, có emoji (vd. `🔮 Pháp Sư Mù`) |
| `metric` | text | Khóa metric — phải thuộc `ALLOWED_METRICS` |
| `operator` | text | `>`, `>=`, `==`, `<`, `<=` (trên sheet: `==` → `eq`) |
| `threshold_value` | number/text | Ngưỡng so sánh |
| `rarity` | text | `Common` / `Rare` / `Legend` — để trống = Common |
| `description` | text | Mô tả hiển thị trong Bộ sưu tập |

### Metrics — `build_user_stats_dict()`

| Metric | Nguồn | Ghi chú |
|--------|-------|---------|
| `total_penalties` | `lb_row["fines"]` | Đơn vị 10k VNĐ — ngưỡng sheet: 50 = 50k |
| `points` | `lb_row["points"]` | Tổng điểm |
| `hit_rate` | `hit_rate` hoặc `correct/played*100` | % |
| `correct` / `missed` / `played` | BXH row | |
| `remaining_hp` | `compute_hp_fields(fines)` | Sinh lực còn lại |
| `win_streak` / `lose_streak` | `build_per_user_streak_recent()` | Chuỗi **gần nhất** (trailing) |

### Tier độc quyền `total_penalties`
- Nhiều rule `>=` cùng đạt → chỉ badge **ngưỡng cao nhất**.
- Nhiều rule `<=` cùng đạt → chỉ badge **ngưỡng thấp nhất**.
- Metric khác: cộng dồn badge như cũ.

### Lịch sử “từng đạt” (`build_per_user_badge_history`)
- Replay stats sau **mỗi trận đã đá** (timeline `long_df`).
- Union mọi badge từng trigger — dùng cho tab Bộ sưu tập (khác với badge đang mang trên BXH).

### Rarity overlay
| Tier | BXH chip | Gallery |
|------|----------|---------|
| **Common (Thường)** | Màu hash cơ bản | Không overlay đặc biệt |
| **Rare (Hiếm)** | Shine + spark cyan | Viền glow |
| **Legend (Huyền thoại)** | Holo gradient + prism border | Holo foil animated |

---

## 6. Tích hợp trang

### Bảng Xếp Hạng — 3 tab chính

| Tab | Nội dung |
|-----|----------|
| 🏆 Leaderboard | BXH + HP + badge chips dưới tên + sidebar activity/streak |
| 🏅 Bộ sưu tập | Gallery per-user, filter metric, thẻ ngang 2 cột |
| 📊 Phân tích | Analytics 4 sub-tabs (Sprint 7) |

### Bộ sưu tập — UX
- Hero Achievement Hall + legend (Đang mang / Đã từng đạt / Chưa mở + rarity).
- `st.selectbox` chọn phòng danh hiệu từng người chơi.
- `st.radio` horizontal lọc theo `metric` (`ACHIEVEMENT_GALLERY_METRIC_MAP`).
- Thẻ: emoji trái + title + **description** phải; locked = grayscale + 🔒.
- Mini-stats tóm tắt tất cả người chơi cuối trang.

### Admin — tab **🏅 Danh hiệu ẩn**
- Xem bảng rule; form **thêm** + **sửa** (id, tên, metric, toán tử, ngưỡng, rarity, description).
- Submit → `st.cache_data.clear()` → rerun.

### Sidebar streak cards (desktop + mobile)
- **Chuỗi Thắng** / **Chuỗi Thua**: user có trailing streak dài nhất; lịch sử pick = đúng các trận tạo chuỗi.
- **Vua Bịp**: upset hero (không đổi logic).

---

## 7. Files liên quan

| File | Vai trò |
|------|---------|
| `achievement_service.py` | HP, evaluator, rarity, catalog meta, badge history, collection bundle |
| `data_service.py` | `read/append/update_achievements_sheet`, operator + rarity normalize |
| `leaderboard_service.py` | `enrich_leaderboard_hp` trong pipeline |
| `leaderboard_gamification_service.py` | Trailing streak sidebar, activity feed |
| `pages/3_Bang_Xep_Hang.py` | 3 tab BXH + achievements + collection |
| `pages/2_Lich_Thi_Dau.py` | Admin danh hiệu |
| `ui_components.py` | HP bar, badge chips, collection board, streak cards |
| `assets/style.css` | HP, badges, collection, trophy cards, main tabs |
| `tests/test_achievement_service.py` | HP, rules, tier, rarity, history, filter |
| `tests/test_leaderboard_gamification_service.py` | Trailing streak window |

---

## 8. Kiểm thử

```bash
.venv/bin/python -m pytest tests/test_achievement_service.py tests/test_leaderboard_gamification_service.py -q
```

| Nhóm test | Nội dung |
|-----------|----------|
| HP | 140/140, clamp, 30 fines → 137 HP |
| Rules | `total_penalties`, `win_streak`, `eq` alias, invalid skip |
| Tier exclusive | Chỉ một badge `>=` / `<=` penalty |
| Rarity + description | `catalog_meta`, `description_map` |
| Badge history | Replay streak cũ vẫn counted ever |
| Gallery filter | `_filter_catalog_by_metric` giữ thứ tự |
| Trailing streak | `_trailing_streak_window` vs `_max_streak_window` |

---

## 9. Rủi ro & giới hạn

| Mục | Chi tiết |
|-----|----------|
| Cache | Thêm/sửa rule → `st.cache_data.clear()` (admin đã làm). |
| Sheet migrate | Thêm cột `rarity` (F), `description` (G); header đủ 7 cột. |
| `==` trên sheet | Phải ghi `eq`. |
| Ranking | HP và badges **không** ảnh hưởng sort. |
| Metric lạ trong filter | Fallback `metric.capitalize()`. |
| `underdog_picks` / `late_picks` | Có label trong gallery map; chưa có trong `ALLOWED_METRICS` cho rule engine. |

---

## 10. Gợi ý mở rộng (chưa làm)

- Metric mới: `underdog_picks`, `late_picks` trong engine.
- Rule AND/OR phức tạp.
- Export/share ảnh bộ sưu tập.
- Push notification khi mở khóa Legend.

---

## 11. Ví dụ rule mẫu

| id | badge_name | metric | operator | threshold | rarity | description |
|----|------------|--------|----------|-----------|--------|-------------|
| A001 | 🔮 Pháp Sư Mù | total_penalties | >= | 50 | Rare | Đóng góp quỹ phạt từ 50k trở lên |
| A002 | 🔥 Chuỗi Vàng | win_streak | >= | 3 | Legend | 3 trận gần nhất đều thắng |
| A003 | 💀 Tụt mood | remaining_hp | <= | 50 | Common | Sinh lực còn dưới 50 HP |

*(Operator `==` trên sheet ghi `eq`.)*

---

## 12. Tóm tắt một dòng

> BXH WC 2026 có **sinh lực** (140 HP = 1,4 triệu quỹ phạt), **danh hiệu ẩn** cấu hình Google Sheets (metric/rarity/mô tả), hiển thị chip trên BXH, gallery **Bộ sưu tập** lọc theo loại, và sidebar streak **trailing** — không đổi thứ hạng.
