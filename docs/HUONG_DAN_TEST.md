# Hướng dẫn test & sử dụng sau khi build feature mới

Tài liệu dành cho **developer / admin (Elu)** — quy trình bắt buộc sau mỗi lần ship tính năng, trước khi push `main` hoặc báo nhóm dùng production.

**Production:** [wc2026-elu.streamlit.app](https://wc2026-elu.streamlit.app)

---

## 1. Quy trình nhanh (checklist)

| Bước | Việc | Pass khi |
|------|------|----------|
| 1 | Chạy `pytest` local | 100% pass, không skip test cũ |
| 2 | Smoke test local (`streamlit run app.py`) | Trang/feature mới hoạt động, không traceback |
| 3 | Regression 2–3 trang lõi | Dự đoán, BXH, Admin vẫn load được |
| 4 | Push `main` → chờ CI xanh | GitHub Actions pass |
| 5 | Reboot / đợi deploy Streamlit Cloud | Trang production khớp local |
| 6 | Smoke test production | 1 luồng end-to-end thật (login → thao tác → kiểm tra Sheet nếu có) |
| 7 | Cập nhật docs (nếu cần) | README / HUONG_DAN / scorecard |

Copy checklist này vào PR hoặc commit message khi feature lớn.

---

## 2. Test tự động (local)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

PYTHONPATH=. pytest -q          # toàn bộ
PYTHONPATH=. pytest tests/test_leaderboard_service.py -q   # module cụ thể
```

**Khi thêm feature mới — nên có test cho:**
- Logic thuần (service / `scoring.py`) — không cần Google Sheet thật
- Edge case: dữ liệu rỗng, đồng hạng, thiếu cột sheet
- Không mock Sheet trừ khi CI đã có pattern sẵn

**CI** (`.github/workflows/ci.yml`): `pytest` + verify sidebar overlay. Push lên `main` = CI chạy tự động.

---

## 3. Smoke test thủ công theo trang

### Trang chủ `/`
- [ ] Sidebar mở/đóng (desktop + mobile ≤768px)
- [ ] Link CTA tới các trang con

### Dự đoán `/Du_Doan`
- [ ] Đăng nhập U01 (hoặc tài khoản test)
- [ ] Chọn kết quả → Chốt → Lưu → thông báo thành công
- [ ] Tab **Lịch sử**: cờ hiện (Win + Mac), filter, phân trang mobile
- [ ] Trận đã khóa / đã có KQ: không sửa được

### Bảng xếp hạng `/Bang_Xep_Hang`
- [ ] Có ít nhất 1 trận đã đá → BXH hiện (không blank)
- [ ] Insight strip trận mới nhất (đúng/sai/bỏ lỡ)
- [ ] Đồng hạng: podium ghi `+N đồng hạng`, hạng competition (vd. 10 người hạng 1 → nhóm sau hạng 11)
- [ ] Cột Phạt: sai = 10k, bỏ lỡ trận = 10k
- [ ] Đăng nhập trước → vào BXH: hàng **Bạn** highlight vàng
- [ ] Expander chi tiết từng trận khớp điểm/phạt

### Lịch thi đấu `/Xem_Lich_Thi_Dau`
- [ ] Filter vòng bảng / knock-out
- [ ] KQ trận đã đá hiển thị đúng
- [ ] Link mã FIFA (MEX, ARG…) → mở `/Tra_Cuu_Doi_Bong?team=`

### Tra cứu đội hình `/Tra_Cuu_Doi_Bong`
- [ ] Chọn đội → 26 cầu thủ, nhóm GK/DF/MF/FW
- [ ] `?team=MEX` deep link chọn đúng đội
- [ ] Tìm kiếm tên / CLB lọc đúng
- [ ] Tab sheet `wc2026_full_players_1200` đồng bộ (hoặc fallback CSV local)

### Dự đoán — expander đội hình
- [ ] Mở **Đội hình 2 đội** trên thẻ trận → top 3 ghi bàn + link xem full

### Bảng đấu `/Bang_Dau` · Bracket `/Bracket_Knockout`
- [ ] Bảng đấu: click tên đội → squad page
- [ ] Cập nhật sau khi admin nhập KQ (cache ~5 phút hoặc rerun)

### Admin `/Lich_Thi_Dau`
- [ ] Đăng nhập admin password
- [ ] Cập nhật tỉ số trận chờ → success → Sheet `matches` đổi
- [ ] Tab **Ma trận → Sheet** → bấm Cập nhật → tab `prediction_matrix` trên Google Sheet có dữ liệu (xem [HUONG_DAN_ADMIN_SHEET.md](HUONG_DAN_ADMIN_SHEET.md) — file local)

---

## 4. Template test cho feature mới

Điền vào PR / ghi chú sprint:

```markdown
## Feature: [tên ngắn]

### Phạm vi
- File chính: ...
- Trang / tab: ...

### Test tự động
- [ ] `tests/test_xxx.py` — mô tả case
- [ ] `PYTHONPATH=. pytest -q` pass

### Test thủ công (local)
- [ ] Happy path: ...
- [ ] Edge: không có dữ liệu / user chưa login / mobile 375px
- [ ] Regression: không ảnh hưởng [trang X]

### Test production (sau deploy)
- [ ] URL: https://wc2026-elu.streamlit.app/...
- [ ] Kết quả quan sát: ...

### Docs
- [ ] README / HUONG_DAN / scorecard (nếu user-facing)
```

---

## 5. Sau khi push — production

1. **GitHub → Actions** — job `test` phải xanh.
2. **Streamlit Cloud** — deploy từ `main`; nếu UI “cũ” sau khi đổi Python module: **Reboot app** trên dashboard.
3. **Cache** — `@st.cache_data(ttl=300)`: đợi tối đa 5 phút hoặc reboot để thấy dữ liệu sheet mới.
4. **Google Sheet** — feature ghi sheet: mở spreadsheet → refresh tab → đối chiếu với app.

---

## 6. Ví dụ: feature đã ship gần đây

### Sprint 5 — Ma trận → Google Sheet
| Kiểm tra | Cách |
|----------|------|
| Unit test | `pytest tests/test_prediction_matrix.py` |
| Admin tab | Login admin → **Ma trận → Sheet** → Cập nhật |
| Sheet | Tab `prediction_matrix`: cột Trận, Cặp đấu, 14 user; ô `A thắng` / `—` |
| Không regression | 4 tab admin cũ vẫn cập nhật KQ được |

### Sprint 6 — Tra cứu đội hình
| Kiểm tra | Cách |
|----------|------|
| Unit test | `pytest tests/test_players_service.py` |
| Trang 7 | 48 đội, filter vị trí, search |
| Du_Doan | Expander đội hình 2 đội |
| Deep link | Lịch thi đấu + Bảng đấu → `?team=` |

### BXH nâng cấp (leaderboard_service)
| Kiểm tra | Cách |
|----------|------|
| Unit test | `pytest tests/test_leaderboard_service.py` |
| Sau trận 1 | 10 người 3đ → cùng hạng 1; 4 người sai → hạng 11, phạt 10k |
| UI | Insight strip, bảng HTML, highlight **Bạn** khi đã login |
| Phân bố điểm | Chart chỉ hiện khi có ≥2 mức điểm khác nhau |

---

## 7. Khi nào không cần test production đầy đủ

- Chỉ sửa CSS thuần, không đổi logic → pytest (nếu có) + xem 1 trang local là đủ.
- Chỉ sửa docs → không cần reboot Cloud.

## Khi nào bắt buộc test production

- Đổi `data_service`, secrets, ghi Google Sheet
- Đổi auth / session
- Feature admin hoặc chấm điểm

---

## Liên kết

- [README — Chạy local](../README.md)
- [Hướng dẫn người chơi](HUONG_DAN_DU_DOAN.md)
- [UI Scorecard / roadmap](UI_SCORECARD.md)
