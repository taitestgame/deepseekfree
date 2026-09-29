import os
import sys
import time
import json
import re
import random
import tempfile

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cloakbrowser import launch_persistent_context
from create_account_direct import (
    EmailTickProvider,
    InstantMailPopular,
    generate_strong_password,
    dismiss_dialogs_and_popups,
    save_account
)

def benchmark_account_creation(provider_type="emailtick", headless=True):
    timings = {}
    total_start = time.perf_counter()

    print("=" * 65)
    print("⏱️ [BẮT ĐẦU ĐO TỐC ĐỘ TẠO TÀI KHOẢN TOKEN HARBOR]")
    print(f"   ⚙️ Chế độ trình duyệt : {'Headless (Ẩn)' if headless else 'Giao diện'}")
    print(f"   📧 Hòm thư sử dụng    : {provider_type.upper()}")
    print("=" * 65)

    # BƯỚC 1: TẠO HÒM THƯ (Chạy qua HTTP Requests)
    print("\n[Bước 1] Khởi tạo hòm thư tạm (Chạy bằng HTTP Requests)...")
    t0 = time.perf_counter()
    if provider_type == "emailtick":
        mail_client = EmailTickProvider(domain="smarta4.com")
        email = mail_client.create()
    else:
        mail_client = InstantMailPopular()
        mail_info = mail_client.create_email(option="+googlemail.com")
        email = mail_info["email"]
    t_mail = time.perf_counter() - t0
    timings["1_mail_creation"] = t_mail
    print(f"   ✅ Hòm thư sẵn sàng: {email} (Mất: {t_mail:.2f}s)")

    password = generate_strong_password(16)

    # BƯỚC 2: KHỞI CHẠY BROWSER (cloakbrowser)
    print("\n[Bước 2] Khởi chạy trình duyệt CloakBrowser chống phát hiện...")
    t0 = time.perf_counter()
    user_data_dir = os.path.join(tempfile.gettempdir(), f"th_bench_{int(time.time())}")
    ctx = launch_persistent_context(user_data_dir=user_data_dir, headless=headless, humanize=False)
    t_browser = time.perf_counter() - t0
    timings["2_browser_launch"] = t_browser
    print(f"   ✅ Trình duyệt đã khởi động (Mất: {t_browser:.2f}s)")

    try:
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        # BƯỚC 3: ĐIỀN FORM VÀ SUBMIT ĐĂNG KÝ
        print("\n[Bước 3] Mở form đăng ký, điền thông tin và Submit...")
        t0 = time.perf_counter()
        page.goto("https://tokenharbor.ai/login?mode=signup", wait_until="domcontentloaded", timeout=35000)
        dismiss_dialogs_and_popups(page)

        email_input = page.wait_for_selector('input[name="email"]', timeout=10000)
        pwd_input = page.wait_for_selector('input[name="password"]', timeout=10000)
        submit_btn = page.wait_for_selector('button[type="submit"]', timeout=10000)

        email_input.type(email, delay=20)
        pwd_input.type(password, delay=20)

        # Nhấn đăng ký
        try:
            submit_btn.click(force=True)
        except Exception:
            page.evaluate("() => { const b = document.querySelector('button[type=\"submit\"]'); if (b) b.click(); }")

        # Chờ chuyển hướng vào dashboard
        reg_success = False
        server_msg = ""
        for i in range(12):
            cur_url = page.url
            if "/dashboard" in cur_url:
                reg_success = True
                break
            err_el = page.query_selector('p[data-bordered="true"], [role="alert"]')
            if err_el:
                txt = err_el.inner_text().strip()
                if txt and "Token Harbor" not in txt:
                    server_msg = txt
                    break
            time.sleep(1.5)

        t_signup = time.perf_counter() - t0
        timings["3_signup_submit"] = t_signup

        if not reg_success:
            print(f"   ❌ Đăng ký thất bại hoặc bị giới hạn IP: {server_msg}")
            print(f"   (Thời gian xử lý: {t_signup:.2f}s)")
            return False, timings

        print(f"   ✅ Đăng ký thành công và đã vào /dashboard! (Mất: {t_signup:.2f}s)")

        # BƯỚC 4: GỬI VÀ XÁC MINH EMAIL TẠI TỔNG QUAN
        print("\n[Bước 4] Xác minh email tại Tổng quan...")
        t0 = time.perf_counter()
        dismiss_dialogs_and_popups(page)

        # Click nút gửi email xác minh
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(x => x.innerText.includes('Xác minh email') || x.innerText.includes('Verify email'));
            if (b) b.click();
        }""")
        print("   👉 Đã bấm nút gửi link xác minh...")

        found_link = None
        if provider_type == "emailtick":
            found_link = mail_client.wait_for_verification_link(timeout_s=60, check_interval=4)
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

        if found_link:
            print(f"   🔗 Bắt được link xác minh: {found_link}")
            page.goto(found_link, wait_until="domcontentloaded", timeout=25000)
            time.sleep(3)
            print("   ✅ Xác minh email hoàn tất!")
        else:
            print("   ⚠️ Không nhận được link trong thời gian chờ.")

        t_verify = time.perf_counter() - t0
        timings["4_email_verification"] = t_verify

        # BƯỚC 5: TẠO & LẤY API KEY
        print("\n[Bước 5] Tạo và trích xuất API Key...")
        t0 = time.perf_counter()
        page.goto("https://tokenharbor.ai/dashboard/api-keys", wait_until="domcontentloaded", timeout=25000)
        dismiss_dialogs_and_popups(page)

        # Bấm + New key
        new_key_btn = page.query_selector('button:has-text("+ New key"), button:has-text("New key")')
        if new_key_btn:
            new_key_btn.click()
            time.sleep(1)
            label_inp = page.query_selector('input[placeholder*="Key label" i], input[placeholder*="label" i], input[type="text"]')
            if label_inp:
                label_inp.fill(f"bench_key_{random.randint(100, 999)}")
            create_btn = page.query_selector('button:has-text("Create key")')
            if create_btn:
                create_btn.click()
                time.sleep(2)

        # Lấy key
        found_key = ""
        inputs = page.query_selector_all('input')
        for inp in inputs:
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
        timings["5_key_extraction"] = t_key
        print(f"   🔑 Key trích xuất: {found_key[:18]}... (Mất: {t_key:.2f}s)")

        total_time = time.perf_counter() - total_start
        timings["total"] = total_time

        # Lưu tài khoản
        save_account(email, password, api_key=found_key, extra="Status: Benchmark Tested")

        # BÁO CÁO TỔNG KẾT
        print("\n" + "=" * 65)
        print("📊 [BÁO CÁO TỔNG KẾT THỜI GIAN TẠO TÀI KHOẢN]")
        print("=" * 65)
        print(f"1. Tạo hòm thư ({provider_type})  : {timings['1_mail_creation']:.2f} giây  (HTTP Requests)")
        print(f"2. Khởi động Browser (Cloak)    : {timings['2_browser_launch']:.2f} giây  (Browser)")
        print(f"3. Điền Form & Submit Đăng ký   : {timings['3_signup_submit']:.2f} giây  (Browser)")
        print(f"4. Xác minh Email               : {timings['4_email_verification']:.2f} giây  (Poll Mail + Browser)")
        print(f"5. Tạo & Trích xuất API Key     : {timings['5_key_extraction']:.2f} giây  (Browser)")
        print("-" * 65)
        print(f"🚀 TỔNG THỜI GIAN HOÀN TẤT      : {total_time:.2f} GIÂY")
        print("=" * 65)
        return True, timings

    finally:
        try:
            ctx.close()
        except Exception:
            pass

if __name__ == "__main__":
    provider = sys.argv[1] if len(sys.argv) > 1 else "emailtick"
    benchmark_account_creation(provider_type=provider, headless=True)
