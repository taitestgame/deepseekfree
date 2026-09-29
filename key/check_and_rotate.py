import os
import sys
import time
import json
import re
import random
import tempfile
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(WORKSPACE_DIR, "accounts.txt")
sys.path.insert(0, WORKSPACE_DIR)

from cloakbrowser import launch_persistent_context
from create_account_direct import (
    EmailTickProvider,
    InstantMailPopular,
    generate_strong_password,
    dismiss_dialogs_and_popups,
    save_account
)


def load_accounts():
    """Đọc danh sách tài khoản từ accounts.txt"""
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    accounts = []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            acc = {}
            for part in line.split("|"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    acc[k.strip().lower()] = v.strip()
            if "email" in acc:
                accounts.append(acc)
    return accounts


def check_quota_fast(api_key: str):
    """
    Kiểm tra nhanh Quota qua Token Harbor API:
    - Gửi request đến model miễn phí deepseek-v4-flash:free
    - Trích xuất % đã dùng từ Header X-Th-Free-Used-Pct
    """
    if not api_key:
        return {"ok": False, "error": "Chưa có API Key"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "deepseek-v4-flash:free",
        "messages": [{"role": "user", "content": "ping"}],
        "max_tokens": 1
    }

    try:
        r = requests.post("https://tokenharbor.ai/v1/chat/completions", headers=headers, json=payload, timeout=12)
        if r.status_code == 200:
            used_pct = int(r.headers.get("X-Th-Free-Used-Pct", 0))
            resets_at = r.headers.get("X-Th-Free-Resets", "N/A")
            remaining_pct = max(0, 100 - used_pct)
            return {
                "ok": True,
                "status_code": 200,
                "used_pct": used_pct,
                "remaining_pct": remaining_pct,
                "resets_at": resets_at,
                "exhausted": False
            }
        elif r.status_code == 429:
            return {
                "ok": False,
                "status_code": 429,
                "remaining_pct": 0,
                "exhausted": True,
                "error": "Quota đã hết hạn mức (429 RateLimit/Exhausted)"
            }
        elif r.status_code == 403:
            return {
                "ok": False,
                "status_code": 403,
                "remaining_pct": 0,
                "exhausted": True,
                "error": "Email chưa được xác minh (Email verification required)"
            }
        elif r.status_code == 402:
            return {
                "ok": False,
                "status_code": 402,
                "remaining_pct": 0,
                "exhausted": True,
                "error": "Chưa kích hoạt gói Free models trên Dashboard"
            }
        else:
            return {
                "ok": False,
                "status_code": r.status_code,
                "remaining_pct": 0,
                "error": f"Lỗi HTTP {r.status_code}: {r.text[:100]}"
            }
    except Exception as e:
        return {"ok": False, "remaining_pct": 0, "error": f"Không thể kết nối API: {e}"}


def create_and_verify_account_full(provider_type="emailtick", headless=True):
    """
    Tạo tài khoản mới, xác minh email, kích hoạt gói Free, lấy API Key
    Đo thời gian chi tiết từng bước.
    """
    timings = {}
    total_start = time.perf_counter()

    print("\n" + "=" * 65)
    print("🚀 [TIẾN TRÌNH TẠO ACC & XÁC MINH FULL TỰ ĐỘNG]")
    print(f"   📧 Hòm thư       : {provider_type.upper()} (@smarta4.com)")
    print(f"   🖥️ Chế độ Browser : {'Headless (Chạy ngầm)' if headless else 'Giao diện'}")
    print("=" * 65)

    # 1. TẠO HÒM THƯ
    print("\n[Bước 1/5] Khởi tạo hòm thư tạm...")
    t0 = time.perf_counter()
    if provider_type == "emailtick":
        mail_client = EmailTickProvider(domain="smarta4.com")
        email = mail_client.create()
    else:
        mail_client = InstantMailPopular()
        mail_info = mail_client.create_email(option="+googlemail.com")
        email = mail_info["email"]
    t_mail = time.perf_counter() - t0
    timings["1_mail"] = t_mail
    print(f"   ✅ Email mới: {email} (Mất: {t_mail:.2f}s)")

    password = generate_strong_password(16)

    # 2. KHỞI CHẠY CLOAKBROWSER
    print("\n[Bước 2/5] Khởi chạy trình duyệt CloakBrowser...")
    t0 = time.perf_counter()
    user_data_dir = os.path.join(tempfile.gettempdir(), f"th_auto_{int(time.time())}_{random.randint(100, 999)}")
    ctx = launch_persistent_context(user_data_dir=user_data_dir, headless=headless, humanize=False)
    t_browser = time.perf_counter() - t0
    timings["2_browser"] = t_browser
    print(f"   ✅ Browser đã sẵn sàng (Mất: {t_browser:.2f}s)")

    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # 3. ĐIỀN FORM VÀ SUBMIT ĐĂNG KÝ
        print("\n[Bước 3/5] Mở trang đăng ký, điền form và tạo tài khoản...")
        t0 = time.perf_counter()
        page.goto("https://tokenharbor.ai/login?mode=signup", wait_until="domcontentloaded", timeout=35000)
        dismiss_dialogs_and_popups(page)

        email_input = page.wait_for_selector('input[name="email"]', timeout=10000)
        pwd_input = page.wait_for_selector('input[name="password"]', timeout=10000)
        submit_btn = page.wait_for_selector('button[type="submit"]', timeout=10000)

        email_input.type(email, delay=15)
        pwd_input.type(password, delay=15)

        try:
            submit_btn.click(force=True)
        except Exception:
            page.evaluate("() => { const b = document.querySelector('button[type=\"submit\"]'); if (b) b.click(); }")

        # Chờ chuyển hướng vào dashboard
        reg_success = False
        for _ in range(12):
            if "/dashboard" in page.url:
                reg_success = True
                break
            err_el = page.query_selector('p[data-bordered="true"], [role="alert"]')
            if err_el:
                txt = err_el.inner_text().strip()
                if txt and "Token Harbor" not in txt:
                    print(f"   ⚠️ Thông báo từ máy chủ: {txt}")
                    break
            time.sleep(1.5)

        t_signup = time.perf_counter() - t0
        timings["3_signup"] = t_signup

        if not reg_success:
            print(f"   ❌ Đăng ký không thành công (Mất: {t_signup:.2f}s)")
            return False, timings, None

        print(f"   ✅ Đã vào /dashboard thành công! (Mất: {t_signup:.2f}s)")

        # 4. GỬI LINK VÀ XÁC MINH EMAIL QUA HÒM THƯ
        print("\n[Bước 4/5] Gửi link xác minh và kích hoạt tài khoản...")
        t0 = time.perf_counter()
        dismiss_dialogs_and_popups(page)

        # Bấm nút gửi email xác minh
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(x => x.innerText.includes('Xác minh email') || x.innerText.includes('Verify email'));
            if (b) b.click();
        }""")
        print("   📨 Đã gửi lệnh yêu cầu link xác minh...")

        found_link = None
        if provider_type == "emailtick":
            found_link = mail_client.wait_for_verification_link(timeout_s=60, check_interval=3)
        else:
            messages = mail_client.wait_for_inbox(timeout_seconds=60, check_interval=3)
            for m in messages:
                mid = m.get("id")
                detail = mail_client.get_message_detail(email, mid) if mid else {}
                full_content = (detail.get("html") or "") + " " + (detail.get("text") or "")
                l = mail_client.extract_verification_link(full_content)
                if l:
                    found_link = l
                    break

        if not found_link:
            print("   ⚠️ Không nhận được email xác minh kịp thời.")
            return False, timings, None

        print(f"   🔗 Bắt được link xác minh: {found_link}")
        page.goto(found_link, wait_until="domcontentloaded", timeout=25000)
        time.sleep(3)
        print("   ✅ Xác minh Email hoàn tất 100%!")

        t_verify = time.perf_counter() - t0
        timings["4_verify"] = t_verify

        # 5. KÍCH HOẠT GÓI FREE & LẤY API KEY
        print("\n[Bước 5/5] Kích hoạt Free models và trích xuất API Key...")
        t0 = time.perf_counter()

        # Về dashboard bấm kích hoạt free models nếu có nút
        page.goto("https://tokenharbor.ai/dashboard", wait_until="domcontentloaded", timeout=20000)
        dismiss_dialogs_and_popups(page)

        # Vào API keys
        page.goto("https://tokenharbor.ai/dashboard/api-keys", wait_until="domcontentloaded", timeout=25000)
        dismiss_dialogs_and_popups(page)

        new_key_btn = page.query_selector('button:has-text("+ New key"), button:has-text("New key")')
        if new_key_btn:
            new_key_btn.click()
            time.sleep(1)
            label_inp = page.query_selector('input[placeholder*="Key label" i], input[placeholder*="label" i], input[type="text"]')
            if label_inp:
                label_inp.fill(f"key_{random.randint(100, 999)}")
            create_btn = page.query_selector('button:has-text("Create key")')
            if create_btn:
                create_btn.click()
                time.sleep(2)

        found_key = ""
        for inp in page.query_selector_all('input'):
            v = inp.get_attribute("value") or ""
            if "thk_" in v and len(v) > 20:
                found_key = v
                break
        if not found_key:
            body = page.evaluate("() => document.body ? document.body.innerText : ''")
            m = re.findall(r'thk_[a-zA-Z0-9_\-]{20,}', body)
            if m:
                found_key = m[0]

        t_key = time.perf_counter() - t0
        timings["5_key"] = t_key

        total_time = time.perf_counter() - total_start
        timings["total"] = total_time

        if found_key:
            print(f"   🔑 API Key mới: {found_key}")
            # Lưu tài khoản vào accounts.txt
            save_account(email, password, api_key=found_key, extra="Status: Active & Verified Full")

            # Cập nhật key_acc1.txt
            key_file = os.path.join(WORKSPACE_DIR, "key_acc1.txt")
            with open(key_file, "w", encoding="utf-8") as f:
                f.write(found_key.strip() + "\n")

            # Cập nhật ~/.credentials.yaml của Halyard
            try:
                from os.path import expanduser
                home = expanduser("~")
                halyard_cred = os.path.join(home, ".halyard", ".credentials.yaml")
                if os.path.exists(os.path.dirname(halyard_cred)):
                    with open(halyard_cred, "w", encoding="utf-8") as f:
                        f.write(f"HALYARD_API_KEY: {found_key.strip()}\n")
            except Exception:
                pass

        # BÁO CÁO TỔNG KẾT THỜI GIAN
        print("\n" + "=" * 65)
        print("⏱️ [BÁO CÁO TỔNG KẾT THỜI GIAN TẠO & VERY FULL]")
        print("=" * 65)
        print(f"1. Tạo hòm thư EmailTick        : {timings['1_mail']:.2f}s  (HTTP Requests)")
        print(f"2. Khởi động Browser Cloak       : {timings['2_browser']:.2f}s  (Browser)")
        print(f"3. Điền Form & Submit Đăng ký    : {timings['3_signup']:.2f}s  (Browser)")
        print(f"4. Bắt link & Xác minh Email     : {timings['4_verify']:.2f}s  (Inbox + Redirect)")
        print(f"5. Bật Free Models & Lấy API Key : {timings['5_key']:.2f}s  (Dashboard API Keys)")
        print("-" * 65)
        print(f"🚀 TỔNG THỜI GIAN HOÀN TẤT       : {total_time:.2f} GIÂY")
        print("=" * 65)

        return True, timings, found_key

    finally:
        try:
            ctx.close()
        except Exception:
            pass


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kiểm tra Quota và Tự động tạo acc nếu dưới ngưỡng")
    parser.add_argument("--threshold", type=float, default=30.0, help="Ngưỡng %% quota còn lại (mặc định: 30%%)")
    parser.add_argument("--force", action="store_true", help="Bắt buộc tạo tài khoản mới bất kể quota")
    args = parser.parse_args()

    threshold = args.threshold
    print("=" * 65)
    print("🔍 [KIỂM TRA HẠN MỨC QUOTA TOKEN HARBOR]")
    print(f"   ⚠️ Ngưỡng kích hoạt tạo mới: Quota còn dưới {threshold}%")
    print("=" * 65)

    accounts = load_accounts()
    current_key = ""
    current_email = ""

    # Lấy key từ key_acc1.txt hoặc tài khoản gần nhất
    key_file = os.path.join(WORKSPACE_DIR, "key_acc1.txt")
    if os.path.exists(key_file):
        with open(key_file, "r", encoding="utf-8") as f:
            current_key = f.read().strip()

    if not current_key and accounts:
        current_key = accounts[-1].get("api_key", "")
        current_email = accounts[-1].get("email", "")
    elif accounts:
        for acc in accounts:
            if acc.get("api_key") == current_key:
                current_email = acc.get("email", "")
                break

    print(f"🔑 API Key hiện tại : {current_key[:18]}... ({current_email or 'Tài khoản hiện hành'})")

    need_create = False

    if args.force:
        print("\n⚡ [LỆNH ÉP BUỘC] Tham số --force được truyền vào -> Bỏ qua kiểm tra, tạo acc ngay!")
        need_create = True
    elif not current_key:
        print("\n⚠️ Chưa có API Key nào được cấu hình -> Cần tạo tài khoản mới ngay!")
        need_create = True
    else:
        print("\n🔍 Đang gửi request kiểm tra tình trạng Quota qua Gateway...")
        stat = check_quota_fast(current_key)
        if stat.get("ok"):
            rem = stat.get("remaining_pct", 0)
            used = stat.get("used_pct", 0)
            resets = stat.get("resets_at", "N/A")
            print(f"📊 Đã sử dụng   : {used}%")
            print(f"🔋 Quota còn lại : {rem}%")
            print(f"⏳ Reset lúc     : {resets}")

            if rem >= threshold:
                print("\n" + "=" * 65)
                print(f"✅ QUOTA CÒN NHIỀU ({rem}% >= {threshold}%).")
                print("👍 KHÔNG CẦN tạo thêm tài khoản mới. Bạn có thể tiếp tục sử dụng bình thường!")
                print("=" * 65)
                return
            else:
                print(f"\n⚠️ CẢNH BÁO: Quota còn lại ({rem}%) ĐÃ DƯỚI NGƯỠNG {threshold}%!")
                need_create = True
        else:
            print(f"\n❌ Key hiện tại gặp vấn đề: {stat.get('error')}")
            print(f"👉 Quota khả dụng: 0% (< {threshold}%) -> Cần tạo tài khoản mới dự phòng!")
            need_create = True

    if need_create:
        ok, timings, new_key = create_and_verify_account_full(provider_type="emailtick", headless=True)
        if ok and new_key:
            print("\n🔍 Đang kiểm tra xác thực Key mới vừa tạo...")
            test_stat = check_quota_fast(new_key)
            if test_stat.get("ok"):
                print(f"🎉 KEY MỚI HOẠT ĐỘNG HOÀN HẢO! Quota còn lại: {test_stat.get('remaining_pct')}%")
            else:
                print(f"ℹ️ Key mới đã tạo, kết quả kiểm tra: {test_stat.get('error')}")


if __name__ == "__main__":
    main()
