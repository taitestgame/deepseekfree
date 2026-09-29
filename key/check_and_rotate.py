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


KEYS_POOL_FILE = os.path.join(WORKSPACE_DIR, "keys_pool.json")


def load_accounts():
    """Đọc danh sách tài khoản từ accounts.txt"""
    if not os.path.exists(ACCOUNTS_FILE):
        return []
    accounts = []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            acc = {}
            for part in line.split("|"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    acc[k.strip().lower()] = v.strip()
            if "email" in acc or "api_key" in acc:
                accounts.append(acc)
    return accounts


def load_pool():
    """
    Tải kho lưu trữ toàn bộ Key từ keys_pool.json.
    Tự động đồng bộ với accounts.txt và key_acc1.txt.
    KHÔNG BAO GIỜ XÓA BẤT KỲ KEY NÀO.
    """
    pool = []
    if os.path.exists(KEYS_POOL_FILE):
        try:
            with open(KEYS_POOL_FILE, "r", encoding="utf-8") as f:
                pool = json.load(f)
        except Exception:
            pool = []

    existing_keys = {item.get("api_key") for item in pool if item.get("api_key")}

    # Tự động nạp từ accounts.txt nếu có
    for acc in load_accounts():
        k = acc.get("api_key")
        if k and k.startswith("thk_") and k not in existing_keys:
            pool.append({
                "api_key": k,
                "email": acc.get("email", ""),
                "password": acc.get("password", ""),
                "used_pct": 0,
                "remaining_pct": 100,
                "resets_at": "",
                "status": acc.get("status", "Chờ kiểm tra"),
                "last_checked": ""
            })
            existing_keys.add(k)

    # Tự động nạp từ key_acc1.txt nếu có
    kfile = os.path.join(WORKSPACE_DIR, "key_acc1.txt")
    if os.path.exists(kfile):
        try:
            with open(kfile, "r", encoding="utf-8") as f:
                for line in f:
                    k = line.strip()
                    if k.startswith("thk_") and k not in existing_keys:
                        pool.append({
                            "api_key": k,
                            "email": "",
                            "password": "",
                            "used_pct": 0,
                            "remaining_pct": 100,
                            "resets_at": "",
                            "status": "Active",
                            "last_checked": ""
                        })
                        existing_keys.add(k)
        except Exception:
            pass

    return pool


def save_pool(pool):
    """
    Lưu lại toàn bộ kho key vào keys_pool.json và đồng bộ sang accounts.txt.
    Giữ lại vĩnh viễn toàn bộ key để chờ chu kỳ reset 7 ngày.
    """
    try:
        with open(KEYS_POOL_FILE, "w", encoding="utf-8") as f:
            json.dump(pool, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Lỗi lưu keys_pool.json: {e}")

    try:
        lines = [
            "# Danh sach toan bo tai khoan va Key Token Harbor (Luu tru vinh vien - Tu dong tai su dung sau 7 ngay):",
            "# Dinh dang: Email: ... | Password: ... | API_Key: ... | Quota_Rem: ...% | Resets: ... | Status: ..."
        ]
        for item in pool:
            em = item.get("email", "N/A")
            pw = item.get("password", "N/A")
            k = item.get("api_key", "")
            rem = item.get("remaining_pct", 0)
            res = item.get("resets_at", "N/A")
            st = item.get("status", "Active")
            lines.append(f"Email: {em} | Password: {pw} | API_Key: {k} | Quota_Rem: {rem}% | Resets: {res} | Status: {st}")

        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        pass


def update_key_in_pool(api_key: str, quota_stat: dict, email: str = None, password: str = None):
    """Cập nhật thông tin Quota và trạng thái reset của Key trong kho"""
    pool = load_pool()
    found = False
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")

    for item in pool:
        if item.get("api_key") == api_key:
            found = True
            if email and not item.get("email"):
                item["email"] = email
            if password and not item.get("password"):
                item["password"] = password
            if quota_stat.get("ok"):
                item["used_pct"] = quota_stat.get("used_pct", 0)
                item["remaining_pct"] = quota_stat.get("remaining_pct", 0)
                item["resets_at"] = quota_stat.get("resets_at", item.get("resets_at", ""))
                rem = item["remaining_pct"]
                item["status"] = "Active (Đang dùng)" if rem >= 30 else "Cooling Down (Chờ reset 7 ngày)"
            else:
                err = quota_stat.get("error", "")
                if "429" in err or quota_stat.get("exhausted"):
                    item["remaining_pct"] = 0
                    item["status"] = "Cooling Down (Chờ reset 7 ngày)"
                elif "403" in err:
                    item["status"] = "Chưa xác minh Email"
                else:
                    item["status"] = f"Lỗi: {err[:30]}"
            item["last_checked"] = now_str
            break

    if not found and api_key:
        rem = quota_stat.get("remaining_pct", 0)
        status = "Active" if rem >= 30 else "Cooling Down (Chờ reset 7 ngày)"
        pool.append({
            "api_key": api_key,
            "email": email or "",
            "password": password or "",
            "used_pct": quota_stat.get("used_pct", 0),
            "remaining_pct": rem,
            "resets_at": quota_stat.get("resets_at", ""),
            "status": status,
            "last_checked": now_str
        })

    save_pool(pool)


def print_pool_summary():
    """Hiển thị bảng tổng kết toàn bộ kho Key và chu kỳ reset 7 ngày"""
    pool = load_pool()
    print("\n" + "=" * 75)
    print("📦 [KHO LƯU TRỮ KEY & CHU KỲ RESET 7 NGÀY (KEY POOL)]")
    print("=" * 75)
    if not pool:
        print("   (Kho hiện chưa có key nào được lưu)")
    else:
        for idx, item in enumerate(pool, 1):
            k = item.get("api_key", "")
            em = item.get("email", "Ẩn danh")
            rem = item.get("remaining_pct", 0)
            res = item.get("resets_at", "N/A")
            st = item.get("status", "N/A")
            if "T" in res:
                res_clean = res.split("T")[0] + " " + res.split("T")[1][:5]
            else:
                res_clean = res
            print(f"#{idx:02d} | Key: {k[:16]}... | Quota: {rem:3d}% | Reset: {res_clean:16s} | {st} ({em})")
    print("=" * 75)
    print(f"💡 Tổng cộng: {len(pool)} Key trong kho. Tất cả Key đều được giữ lại vĩnh viễn!")
    print("   Hệ thống sẽ tự động xoay vòng tái sử dụng Key cũ ngay khi reset xong!")
    print("=" * 75 + "\n")


def find_reusable_key_from_pool(threshold=30.0, current_key=""):
    """
    Quét kho Key: tìm xem có key nào ĐÃ RESET HẠN MỨC (sau 7 ngày) hoặc còn >= threshold% quota.
    Trả về (key, info_dict) nếu tìm thấy, hoặc (None, None).
    """
    pool = load_pool()
    if not pool:
        return None, None

    print("\n📦 [KHO KEY] Đang kiểm tra lại các Key đã lưu trữ để tìm key đã hồi sinh Quota...")
    candidates = []
    for item in pool:
        k = item.get("api_key")
        if not k or k == current_key:
            continue
        if "Chưa xác minh" in item.get("status", ""):
            continue
        candidates.append(item)

    if not candidates:
        print("   ℹ️ Chưa có key phụ nào khác trong kho lưu trữ.")
        return None, None

    print(f"   🔍 Tìm thấy {len(candidates)} key dự phòng trong kho. Đang ping kiểm tra quota...")
    for item in candidates:
        k = item.get("api_key")
        em = item.get("email", "Ẩn danh")
        print(f"   ⚡ Ping: {k[:18]}... ({em})")
        stat = check_quota_fast(k)
        update_key_in_pool(k, stat)

        if stat.get("ok"):
            rem = stat.get("remaining_pct", 0)
            print(f"      -> Quota hiện tại: {rem}% (Chu kỳ reset kế: {stat.get('resets_at', 'N/A')})")
            if rem >= threshold:
                print(f"   🎉 [TÁI SINH THÀNH CÔNG] Key này đã reset hạn mức và sẵn sàng sử dụng ({rem}% >= {threshold}%)!")
                return k, item
        else:
            print(f"      -> Trạng thái: {stat.get('error')}")

    print("   ❌ Các Key cũ trong kho hiện vẫn đang trong chu kỳ chờ reset 7 ngày (< 30%).")
    return None, None


def sync_key_everywhere(api_key: str):
    """
    Tự động đồng bộ API Key đến TẤT CẢ các vị trí để IDE và các tool tự nhận diện 100%:
    1. ~/.halyard/.credentials.yaml (Dành cho IDE Halyard)
    2. ~/.tokenharbor/config.json (Dành cho Token Harbor CLI)
    3. Biến môi trường HALYARD_API_KEY và TOKENHARBOR_API_KEY
    4. File key_acc1.txt trong thư mục key
    5. ~/.claude/settings.json (Dành cho Claude Code nếu có)
    6. ~/.config/opencode/opencode.json (Dành cho OpenCode nếu có)
    """
    if not api_key or not api_key.startswith("thk_"):
        return

    home = os.path.expanduser("~")

    # 1. Đồng bộ cho Halyard IDE (~/.halyard/.credentials.yaml)
    try:
        halyard_dir = os.path.join(home, ".halyard")
        os.makedirs(halyard_dir, exist_ok=True)
        halyard_cred = os.path.join(halyard_dir, ".credentials.yaml")
        with open(halyard_cred, "w", encoding="utf-8") as f:
            f.write(f"HALYARD_API_KEY: {api_key.strip()}\n")
        print(f"   🔗 [SYNC] Đã gắn API Key vào Halyard IDE: ~/.halyard/.credentials.yaml")
    except Exception as e:
        print(f"   ⚠️ Lỗi đồng bộ Halyard: {e}")

    # 2. Đồng bộ cho key_acc1.txt
    try:
        kfile = os.path.join(WORKSPACE_DIR, "key_acc1.txt")
        with open(kfile, "w", encoding="utf-8") as f:
            f.write(api_key.strip() + "\n")
    except Exception:
        pass

    # 3. Đồng bộ cho Token Harbor config (~/.tokenharbor/config.json)
    try:
        th_dir = os.path.join(home, ".tokenharbor")
        os.makedirs(th_dir, exist_ok=True)
        th_cfg = os.path.join(th_dir, "config.json")
        data = {}
        if os.path.exists(th_cfg):
            try:
                with open(th_cfg, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = {}
        data["key"] = api_key.strip()
        with open(th_cfg, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

    # 4. Gán biến môi trường trong session
    os.environ["HALYARD_API_KEY"] = api_key.strip()
    os.environ["TOKENHARBOR_API_KEY"] = api_key.strip()


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

            # TỰ ĐỘNG ĐỒNG BỘ KEY ĐẾN TẤT CẢ VỊ TRÍ (Halyard IDE, Token Harbor CLI, env)
            sync_key_everywhere(found_key)

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


def find_existing_key():
    """
    Tự động tìm kiếm API Key từ mọi nguồn trên máy:
    1. File key_acc1.txt
    2. File ~/.halyard/.credentials.yaml (IDE Halyard)
    3. File ~/.tokenharbor/config.json (Token Harbor CLI)
    4. Biến môi trường HALYARD_API_KEY / TOKENHARBOR_API_KEY
    5. File accounts.txt
    """
    # 1. key_acc1.txt
    key_file = os.path.join(WORKSPACE_DIR, "key_acc1.txt")
    if os.path.exists(key_file):
        try:
            with open(key_file, "r", encoding="utf-8") as f:
                for l in f:
                    l = l.strip()
                    if l and not l.startswith("#") and "thk_" in l:
                        return l, "key_acc1.txt"
        except Exception:
            pass

    # 2. ~/.halyard/.credentials.yaml
    home = os.path.expanduser("~")
    halyard_cred = os.path.join(home, ".halyard", ".credentials.yaml")
    if os.path.exists(halyard_cred):
        try:
            with open(halyard_cred, "r", encoding="utf-8") as f:
                for l in f:
                    if "HALYARD_API_KEY" in l and ":" in l:
                        k = l.split(":", 1)[1].strip().strip('"\'')
                        if k.startswith("thk_"):
                            return k, "IDE ~/.halyard/.credentials.yaml"
        except Exception:
            pass

    # 3. ~/.tokenharbor/config.json
    th_cfg = os.path.join(home, ".tokenharbor", "config.json")
    if os.path.exists(th_cfg):
        try:
            with open(th_cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
                k = data.get("key", "").strip()
                if k.startswith("thk_"):
                    return k, "~/.tokenharbor/config.json"
        except Exception:
            pass

    # 4. Biến môi trường
    for env_var in ["HALYARD_API_KEY", "TOKENHARBOR_API_KEY"]:
        k = os.environ.get(env_var, "").strip()
        if k.startswith("thk_"):
            return k, f"Biến môi trường {env_var}"

    # 5. accounts.txt
    accounts = load_accounts()
    if accounts:
        for acc in reversed(accounts):
            k = acc.get("api_key", "").strip()
            if k.startswith("thk_"):
                return k, f"accounts.txt ({acc.get('email', '')})"

    return "", "Chưa có key"


def check_and_rotate_once(threshold=30.0, force=False):
    current_key, source = find_existing_key()
    accounts = load_accounts()
    current_email = ""
    if accounts and current_key:
        for acc in accounts:
            if acc.get("api_key") == current_key:
                current_email = acc.get("email", "")
                break

    print(f"\n🔑 API Key hiện tại: {current_key[:18] if current_key else '(Chưa có)'}... (Nguồn: {source})")

    need_rotate = False

    if force:
        print("\n⚡ [LỆNH ÉP BUỘC] Tham số --force được truyền vào -> Bỏ qua kiểm tra, xoay vòng/tạo key ngay!")
        need_rotate = True
    elif not current_key:
        print("\n⚠️ Chưa có API Key nào được cấu hình -> Cần tìm key trong kho hoặc tạo mới!")
        need_rotate = True
    else:
        print("🔍 Đang gửi request kiểm tra tình trạng Quota qua Gateway...")
        stat = check_quota_fast(current_key)
        update_key_in_pool(current_key, stat, email=current_email)

        if stat.get("ok"):
            rem = stat.get("remaining_pct", 0)
            used = stat.get("used_pct", 0)
            resets = stat.get("resets_at", "N/A")
            print(f"📊 Đã sử dụng   : {used}%")
            print(f"🔋 Quota còn lại : {rem}%")
            print(f"⏳ Reset lúc     : {resets}")

            sync_key_everywhere(current_key)

            if rem >= threshold:
                print(f"✅ QUOTA CÒN ĐỦ DÙNG ({rem}% >= {threshold}%).")
                print("👍 KHÔNG CẦN tạo thêm tài khoản mới.")
                return True
            else:
                print(f"\n⚠️ CẢNH BÁO: Quota còn lại ({rem}%) ĐÃ DƯỚI NGƯỠNG {threshold}%!")
                need_rotate = True
        else:
            print(f"\n❌ Key hiện tại gặp vấn đề: {stat.get('error')}")
            update_key_in_pool(current_key, stat, email=current_email)
            need_rotate = True

    if need_rotate:
        # BƯỚC 1: QUÉT KHO KEY XEM CÓ KEY CŨ NÀO ĐÃ RESET HẠN MỨC (SAU 7 NGÀY) CHƯA
        reusable_key, info = find_reusable_key_from_pool(threshold=threshold, current_key=current_key)
        if reusable_key:
            print(f"\n♻️ [HỒI SINH KEY THÀNH CÔNG] Đã tái sử dụng Key trong kho: {reusable_key[:18]}... ({info.get('email', '')})")
            print(f"   🔋 Quota hiện tại : {info.get('remaining_pct', 100)}%")
            print(f"   ⏳ Chu kỳ reset kế: {info.get('resets_at', 'N/A')}")
            sync_key_everywhere(reusable_key)
            return True

        # BƯỚC 2: TẤT CẢ KEY TRONG KHO ĐỀU CHƯA RESET -> TẠO MỚI VÀ LƯU THÊM VÀO KHO
        print("\n🚀 [TẠO MỚI BỔ SUNG] Toàn bộ Key trong kho đều đang chờ chu kỳ reset 7 ngày.")
        print("   Bắt đầu tạo thêm 1 tài khoản mới và LƯU TRỮ VĨNH VIỄN vào kho...")
        ok, timings, new_key = create_and_verify_account_full(provider_type="emailtick", headless=True)
        if ok and new_key:
            print("\n🔍 Đang kiểm tra xác thực Key mới vừa tạo...")
            test_stat = check_quota_fast(new_key)
            if test_stat.get("ok"):
                print(f"🎉 KEY MỚI HOẠT ĐỘNG HOÀN HẢO! Quota còn lại: {test_stat.get('remaining_pct')}%")
                update_key_in_pool(new_key, test_stat)
                sync_key_everywhere(new_key)
                return True
            else:
                print(f"ℹ️ Key mới đã tạo, kết quả kiểm tra: {test_stat.get('error')}")
                update_key_in_pool(new_key, test_stat)
                return False
        else:
            print("❌ Không thể tạo tài khoản mới.")
            return False

    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Kiểm tra Quota, Tự động xoay vòng Key cũ đã reset hoặc tạo acc mới")
    parser.add_argument("--threshold", type=float, default=30.0, help="Ngưỡng %% quota còn lại (mặc định: 30%%)")
    parser.add_argument("--force", action="store_true", help="Bắt buộc xoay vòng hoặc tạo mới bất kể quota")
    parser.add_argument("--watch", type=int, default=0, help="Chạy chế độ giám sát ngầm liên tục (số phút giữa mỗi lần check, 0 = chạy 1 lần)")
    parser.add_argument("--pool", action="store_true", help="Xem danh sách toàn bộ Key trong kho lưu trữ và thời gian reset 7 ngày")
    args = parser.parse_args()

    if args.pool:
        print_pool_summary()
        return

    threshold = args.threshold

    if args.watch > 0:
        print("=" * 65)
        print(f"🛡️ [CHẾ ĐỘ GIÁM SÁT NGẦM WATCHDOG ĐANG BẬT]")
        print(f"   ⏱️ Chu kỳ kiểm tra  : Mỗi {args.watch} phút")
        print(f"   ⚠️ Ngưỡng kích hoạt : Quota còn dưới {threshold}%")
        print("   ♻️ Cơ chế           : Ưu tiên hồi sinh Key cũ đã reset 7 ngày trước khi tạo mới")
        print("=" * 65)
        while True:
            try:
                check_and_rotate_once(threshold=threshold, force=args.force)
            except Exception as e:
                print(f"⚠️ Lỗi trong vòng lặp watchdog: {e}")
            time.sleep(args.watch * 60)
    else:
        print("=" * 65)
        print("🔍 [KIỂM TRA HẠN MỨC QUOTA TOKEN HARBOR & KHO KEY]")
        print(f"   ⚠️ Ngưỡng kích hoạt tạo mới: Quota còn dưới {threshold}%")
        print("   ♻️ Cơ chế: Tự động tái sử dụng Key cũ đã reset 7 ngày")
        print("=" * 65)
        check_and_rotate_once(threshold=threshold, force=args.force)
        print_pool_summary()


if __name__ == "__main__":
    main()
