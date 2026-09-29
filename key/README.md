# Hướng Dẫn Quản Lý Quota & Tự Động Xoay Tài Khoản Token Harbor

## 1. Cơ chế tài khoản & Quota của Token Harbor
- **Guest Account**: Token Harbor **không hỗ trợ** guest/anonymous account. Mọi API Key (`thk_live_...`) bắt buộc email phải ở trạng thái **Đã xác minh (Verified)** thì Gateway `https://tokenharbor.ai/v1` mới mở quyền truy cập.
- **Cơ chế Quota**:
  - Mỗi tài khoản miễn phí được cấp hạn mức các model (`deepseek-v4-flash`, `mimo-v2.6-flash`, `qwen3.8-flash`, `th-rudder`...).
  - Dữ liệu Quota gồm: `% đã dùng (used_pct)`, `% còn lại (100 - used_pct)`, `số request đã dùng (req_used)` và `trạng thái cạn kiệt (exhausted)`.
  - Hạn mức tự động reset sau mỗi 5 tiếng.

---

## 2. Token Harbor CLI (`connect.ps1`)
CLI chính chủ đã được cài đặt tại: `C:\Users\taitestg\.tokenharbor`
- Xem trạng thái:
  ```powershell
  tokenharbor status
  ```
- Kết nối tới các AI Coding Agent (Claude Code, OpenCode, Cursor, v.v.):
  ```powershell
  tokenharbor connect
  ```
- File cấu hình trung tâm: `~/.tokenharbor/config.json`

---

## 3. Các Lệnh Quản Lý Quota (`quota_manager.py`)

### A. Kiểm tra Quota hiện tại
```powershell
python quota_manager.py --check
```
Hiển thị danh sách tài khoản trong `accounts.txt`, tài khoản nào đang dùng, tài khoản dự phòng và tình trạng API Gateway.

### B. Xoay thủ công sang tài khoản tiếp theo
```powershell
python quota_manager.py --rotate
```
Tự động chuyển sang tài khoản kế tiếp, cập nhật API key vào `~/.tokenharbor/config.json` và biến môi trường Windows `TOKENHARBOR_API_KEY`.

### C. Chạy chế độ Tự Động Giám Sát (Watchdog)
```powershell
python quota_manager.py --watch --interval 60 --threshold 20
```
- **Chu kỳ**: Kiểm tra mỗi 60 giây (tùy chỉnh qua `--interval`).
- **Tự tạo acc dự phòng**: Khi Quota tài khoản hiện tại còn **dưới 20%** (`--threshold 20`), hệ thống sẽ tự động kích hoạt tạo tài khoản mới bằng hòm thư `@smarta4.com` (EmailTick) và lưu vào `accounts.txt`.
- **Tự xoay khi hết Quota**: Khi Quota chạm 100% hoặc nhận mã 429 cạn kiệt, hệ thống sẽ tự động xoay sang tài khoản mới cho toàn bộ các AI Coding Agent.

---

## 4. Kiểm Tra Nhanh & Tự Tạo Acc Qua File .BAT (`check_quota.bat`)

File chạy nhanh 1-click đã được tạo tại thư mục:
`c:\python\test\mai\tokenhanet\check_quota.bat`

- **Cách dùng:** Double-click chuột vào file `check_quota.bat` (hoặc chạy trong cmd / terminal).
- **Cơ chế hoạt động:**
  1. Kiểm tra nhanh Quota của Key hiện tại qua Gateway.
  2. Nếu Quota còn **>= 30%**: Báo xanh, không cần tạo mới, tiếp tục dùng.
  3. Nếu Quota còn **< 30%** (hoặc key lỗi/hết quota): Tự động tạo acc mới, xác minh link email, kích hoạt gói Free models và lưu API Key mới vào hệ thống.
  4. Hiển thị báo cáo tốc độ và thời gian từng bước rõ ràng trên màn hình.
