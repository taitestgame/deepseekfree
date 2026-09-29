import os
import sys
import time
import random
import string
import tempfile
import re
import argparse
import requests
from cloakbrowser import launch_persistent_context
from temp_mail import InstantMailPopular
from proxy_service import ProxyService

try:
    from curl_cffi import requests as cffi_requests
except ImportError:
    cffi_requests = None

# Thiết lập encoding utf-8 cho console Windows
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.txt")


# =====================================================================
# Provider 1: EmailTick (@smarta4.com) - MẶC ĐỊNH
# =====================================================================
class EmailTickProvider:
    """emailtick.com - temp mail với domain @smarta4.com"""
    name = "emailtick"
    BASE = "https://www.emailtick.com"

    def __init__(self, domain: str = "smarta4.com"):
        self._session = None
        self._email = None
        self._code = None
        self._seen_ids = set()
        self.target_domain = domain

    def _new_session(self):
        if cffi_requests:
            s = cffi_requests.Session(impersonate="chrome131")
        else:
            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
            })
        s.headers.update({
            "Referer": self.BASE + "/",
            "Origin": self.BASE,
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "X-Requested-With": "XMLHttpRequest",
        })
        return s

    def _parse_home(self, html):
        code = (re.search(r'id="code"[^>]*value="([^"]+)"', html)
                or re.search(r'name="code"[^>]*value="([^"]+)"', html))
        email = (re.search(r'id="mailbox"[^>]*value="([^"]+)"', html)
                 or re.search(r'name="mailbox"[^>]*value="([^"]+)"', html))
        return (email.group(1) if email else None), (code.group(1) if code else None)

    def create(self) -> str:
        self._session = self._new_session()
        last_err = ""
        for attempt in range(8):
            try:
                r = self._session.get(self.BASE + "/", timeout=25)
                if r.status_code == 429 or "captcha" in r.text[:2000].lower() or "captcha" in r.url:
                    time.sleep(6 * (attempt + 1))
                    continue
                email, code = self._parse_home(r.text)
                if not code:
                    time.sleep(3)
                    continue
                rr = self._session.post(self.BASE + "/change-mailbox",
                                        json={"email": email, "code": code, "domain": self.target_domain},
                                        timeout=25)
                if rr.status_code == 429:
                    time.sleep(6 * (attempt + 1))
                    continue
                j = rr.json()
                if j.get("success") and j.get("email"):
                    self._email = j["email"]
                    self._code = j.get("code") or code
                    print(f"📧 [EmailTick] Đã tạo hòm thư: {self._email}")
                    return self._email
                if email:
                    self._email, self._code = email, code
                    print(f"📧 [EmailTick] Đã tạo hòm thư: {self._email}")
                    return self._email
            except Exception as e:
                last_err = str(e)
            time.sleep(3)

        if self._email:
            return self._email
        raise RuntimeError(f"EmailTick: không tạo được hòm thư ({last_err})")

    def list_mails(self) -> list:
        for attempt in range(4):
            try:
                r = self._session.post(self.BASE + "/get-emails",
                                       json={"email": self._email, "code": self._code}, timeout=20)
                if r.status_code == 429:
                    time.sleep(8 * (attempt + 1))
                    continue
                if r.status_code != 200:
                    time.sleep(4)
                    continue
                j = r.json()
                if j.get("success"):
                    return j.get("emails") or []
                return []
            except Exception:
                time.sleep(4)
        return []

    def get_mail_content(self, mail_id: str) -> str:
        for attempt in range(4):
            try:
                r = self._session.get(f"{self.BASE}/mail/gmail-content/{mail_id}", timeout=20)
                if r.status_code == 429:
                    time.sleep(8 * (attempt + 1))
                    continue
                j = r.json()
                if isinstance(j, dict) and j.get("status"):
                    return str((j.get("msg") or {}).get("content") or "")
            except Exception:
                time.sleep(4)
        return ""

    def wait_for_verification_link(self, timeout_s: int = 90, check_interval: int = 5) -> str:
        start = time.time()
        print(f"⏳ Đang chờ thư xác minh EmailTick ({self._email}) tối đa {timeout_s}s...")
        while time.time() - start < timeout_s:
            try:
                mails = self.list_mails()
                for m in mails:
                    mid = m.get("code")
                    if not mid or mid in self._seen_ids:
                        continue
                    self._seen_ids.add(mid)
                    subj = str(m.get("subject") or "")
                    sender = str(m.get("fromName") or "")
                    print(f"   📨 Nhận thư mới: [{sender}] {subj}")
                    content = self.get_mail_content(mid)
                    import html
                    content_clean = html.unescape(content)
                    links = re.findall(r'https?://[^\s<>"\'\)]+', content_clean)
                    for l in links:
                        l_clean = l.rstrip(".")
                        if any(k in l_clean.lower() for k in ["verify", "confirm", "auth", "magic", "token", "callback"]):
                            return l_clean
            except Exception as e:
                print(f"   [poll err] {e}")
            time.sleep(check_interval)
        return ""


# =====================================================================
# Tiện ích tạo mật khẩu và lưu file
# =====================================================================
def generate_strong_password(length: int = 16) -> str:
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*"
    chars = [
        random.choice(lower),
        random.choice(upper),
        random.choice(digits),
        random.choice(special)
    ]
    pool = lower + upper + digits + special
    chars += random.choices(pool, k=length - 4)
    random.shuffle(chars)
    return "".join(chars)

def save_account(email: str, password: str, api_key: str = "", extra: str = ""):
    os.makedirs(BASE_DIR, exist_ok=True)
    new_line = f"Email: {email} | Password: {password}"
    if api_key:
        new_line += f" | API_Key: {api_key}"
    if extra:
        new_line += f" | {extra}"

    lines = []
    found = False
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for l in f:
                l_strip = l.strip()
                if not l_strip:
                    continue
                if f"Email: {email}" in l_strip:
                    lines.append(new_line)
                    found = True
                else:
                    lines.append(l_strip)

    if not found:
        lines.append(new_line)

    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")

    print(f"💾 [LƯU THÀNH CÔNG] Đã ghi vào accounts.txt:")
    print(f"   -> {new_line}")


# =====================================================================
# Xử lý đóng Popup & Dialog trên Dashboard
# =====================================================================
def dismiss_dialogs_and_popups(page):
    """Tự động đóng cookie banner và TỰ ĐỘNG BẬT 'Enable free models'"""
    try:
        # Bấm Essential only cho cookie
        essential_btn = page.query_selector('button:has-text("Essential only")')
        if essential_btn and essential_btn.is_visible():
            essential_btn.click()
            time.sleep(0.5)

        # TỰ ĐỘNG KÍCH HOẠT GÓI FREE MODELS NẾU CÓ NÚT
        free_btn = page.query_selector('button:has-text("Enable free models")')
        if free_btn and free_btn.is_visible():
            print("[+] Phát hiện nút kích hoạt gói Free models -> Bấm 'Enable free models'!")
            free_btn.click()
            time.sleep(2)

        # Xử lý đóng các dialog thông báo rác khác
        modal_selectors = [
            'button:has-text("Got it")',
            'button:has-text("Close")',
            '[aria-label="Close"]',
        ]
        for sel in modal_selectors:
            btn = page.query_selector(sel)
            if btn and btn.is_visible():
                print(f"[*] Đóng hộp thoại thông báo: '{btn.inner_text().strip()}'")
                btn.click()
                time.sleep(0.5)

        # Fallback bấm Escape
        page.keyboard.press("Escape")
        time.sleep(0.5)
    except Exception:
        pass


# =====================================================================
# TỰ ĐỘNG XÁC MINH EMAIL TẠI TRANG TỔNG QUAN (OVERVIEW)
# =====================================================================
def verify_email_on_dashboard(page, email: str, provider_client, provider_type: str = "emailtick") -> bool:
    """
    Vào trang Tổng quan (/dashboard), tìm nút 'Xác minh email' / 'Verify email',
    bấm gửi mail xác minh, bắt liên kết trong hòm thư và điều hướng kích hoạt.
    """
    print("\n" + "-" * 55)
    print("🔍 [BƯỚC XÁC MINH EMAIL TẠI TỔNG QUAN]")
    print("-" * 55)

    try:
        # Đảm bảo đang ở trang /dashboard
        if "/dashboard" not in page.url:
            print("[*] Đang chuyển hướng về trang Tổng quan (/dashboard)...")
            try:
                page.wait_for_url("**/dashboard**", timeout=8000)
            except Exception:
                page.goto("https://tokenharbor.ai/dashboard", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)

        dismiss_dialogs_and_popups(page)

        # Tìm nút 'Xác minh email' hoặc 'Verify email'
        verify_btn = page.query_selector('button:has-text("Xác minh email"), button:has-text("Verify email")')
        if not verify_btn:
            # Kiểm tra xem có text thông báo banner không
            body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
            if "Xác minh email của bạn" not in body_text and "Verify your email" not in body_text:
                print("✅ Email đã được xác minh trước đó (không còn banner yêu cầu xác minh)!")
                return True
            time.sleep(2)
            verify_btn = page.query_selector('button:has-text("Xác minh email"), button:has-text("Verify email")')

        if not verify_btn:
            print("ℹ️ Không tìm thấy nút Xác minh email trên Tổng quan.")
            return True

        print(f"[+] Tìm thấy nút: '{verify_btn.inner_text().strip()}'")
        print("👉 Đang bấm nút gửi email xác minh...")
        # Sử dụng evaluate click để đảm bảo kích hoạt kể cả khi có lớp phủ
        page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button'));
            const b = btns.find(x => x.innerText.includes('Xác minh email') || x.innerText.includes('Verify email'));
            if (b) b.click();
        }""")
        time.sleep(3)
        print("📨 Đã gửi lệnh yêu cầu gửi link xác minh từ máy chủ Token Harbor!")

        # Chờ và lấy link xác minh từ hộp thư
        found_link = None
        if provider_type == "emailtick":
            found_link = provider_client.wait_for_verification_link(timeout_s=90, check_interval=5)
        else:
            # InstantMail
            messages = provider_client.wait_for_inbox(timeout_seconds=90, check_interval=3)
            for m in messages:
                mid = m.get("id")
                detail = provider_client.get_message_detail(email, mid) if mid else {}
                full_content = (detail.get("html") or "") + " " + (detail.get("text") or "") + " " + (m.get("text") or "")
                l = provider_client.extract_verification_link(full_content)
                if l:
                    found_link = l
                    break

        if found_link:
            print(f"\n🎉 Đã nhận được liên kết xác minh:")
            print(f"   👉 {found_link}")
            print("[*] Đang điều hướng trình duyệt đến link xác minh...")
            page.goto(found_link, wait_until="domcontentloaded", timeout=30000)
            time.sleep(5)
            print(f"✅ Trang sau khi xác minh: {page.url}")

            # Quay lại /dashboard để kiểm tra banner đã biến mất
            print("[*] Kiểm tra lại trang Tổng quan...")
            page.goto("https://tokenharbor.ai/dashboard", wait_until="domcontentloaded", timeout=20000)
            time.sleep(3)
            dismiss_dialogs_and_popups(page)

            body_check = page.evaluate("() => document.body ? document.body.innerText : ''")
            if "Xác minh email của bạn" not in body_check and "Verify your email" not in body_check:
                print("🏆 XÁC MINH EMAIL THÀNH CÔNG! Banner xác minh đã được gỡ bỏ!")
                return True
            else:
                print("ℹ️ Đã mở liên kết xác minh hoàn tất.")
                return True
        else:
            print("⚠️ Hết thời gian chờ nhưng chưa thấy link xác minh gửi về hòm thư.")
            return False

    except Exception as e:
        print(f"[-] Lỗi trong quá trình xác minh email: {e}")
        return False


# =====================================================================
# TỰ ĐỘNG KHỞI TẠO API KEY
# =====================================================================
def extract_or_create_api_key(page) -> str:
    """Tự động vào trang API keys để tạo và lấy API Key"""
    try:
        print("[*] Đang mở trang /dashboard/api-keys để lấy API Key...")
        page.goto("https://tokenharbor.ai/dashboard/api-keys", wait_until="domcontentloaded", timeout=25000)
        time.sleep(3)
        dismiss_dialogs_and_popups(page)

        new_key_btn = page.query_selector('button:has-text("+ New key")')
        if new_key_btn and new_key_btn.is_visible():
            new_key_btn.click()
            time.sleep(1.5)

        label_inp = page.query_selector('input[placeholder*="Key label" i], input[placeholder*="label" i], input[type="text"]')
        if label_inp and label_inp.is_visible():
            key_label = f"key_{random.randint(1000, 9999)}"
            label_inp.fill(key_label)
            time.sleep(0.5)

        create_btn = page.query_selector('button:has-text("Create key")')
        if create_btn and create_btn.is_visible():
            create_btn.click()
            time.sleep(3)

        # Trích xuất key
        key_inputs = page.query_selector_all('input[readonly], input[value*="thk_"], input[value*="th-"], input[value*="sk-"]')
        for inp in key_inputs:
            val = inp.get_attribute("value")
            if val and len(val) >= 20 and ("thk_" in val or "th-" in val or "sk-" in val):
                print(f"🔑 Lấy được API Key: {val}")
                return val

        body_text = page.evaluate("() => document.body ? document.body.innerText : ''")
        matches = re.findall(r'(?:thk_[a-zA-Z0-9_-]{20,}|th-[a-zA-Z0-9_-]{16,}|sk-[a-zA-Z0-9_-]{16,})', body_text)
        if matches:
            print(f"🔑 Lấy được API Key: {matches[0]}")
            return matches[0]

    except Exception as e:
        print(f"[-] Không thể lấy API key tự động: {e}")
    return ""


# =====================================================================
# Tiện ích xoay Proxy WARP (Cloudflare WARP IPv6 cổng 2080)
# =====================================================================
def start_or_rotate_warp() -> str:
    """Tự động kết nối hoặc cấp IP mới qua Cloudflare WARP trên cổng 127.0.0.1:2080"""
    print("[*] Đang khởi động / xoay IP Cloudflare WARP trên cổng 127.0.0.1:2080...")
    try:
        sys.path.insert(0, r"C:\python\ip")
        import ipv6_tool
        import psutil
        import subprocess

        ipv6_tool.generate_warp_account()
        for p in psutil.process_iter(["pid", "name"]):
            if "sing-box" in (p.info["name"] or "").lower():
                try:
                    p.terminate()
                    p.wait(timeout=2)
                except Exception:
                    pass

        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0
        subprocess.Popen(
            [r"C:\python\ip\bin\sing-box.exe", "run", "-c", r"C:\python\ip\singbox_config.json"],
            creationflags=creationflags,
            close_fds=True
        )
        time.sleep(3)
        print("[+] Đã kết nối Cloudflare WARP thành công qua proxy SOCKS5 127.0.0.1:2080!")
        return "socks5://127.0.0.1:2080"
    except Exception as e:
        print(f"[-] Không thể kích hoạt WARP: {e}")
        return ""


# =====================================================================
# QUY TRÌNH TẠO 1 TÀI KHOẢN HOÀN CHỈNH
# =====================================================================
def create_single_account(provider_type: str = "emailtick",
                          mail_option: str = "+googlemail.com",
                          emailtick_domain: str = "smarta4.com",
                          proxy: str = None,
                          use_warp: bool = False,
                          headless: bool = True) -> bool:
    print("\n" + "=" * 65)
    print("🚀 BẮT ĐẦU TẠO TÀI KHOẢN TOKEN HARBOR")
    print("=" * 65)

    # 1. Khởi tạo Proxy nếu có
    active_proxy = None
    network_mode = "Direct IP (IP máy trực tiếp)"
    if proxy:
        active_proxy = {"server": proxy} if isinstance(proxy, str) else proxy
        network_mode = f"Custom Proxy ({proxy})"
    elif use_warp or ProxyService.is_warp_available():
        warp_proxy = ProxyService.rotate_proxy()
        if warp_proxy and warp_proxy != "direct":
            active_proxy = {"server": warp_proxy}
            network_mode = f"Cloudflare WARP Free ({warp_proxy})"

    # 2. Khởi tạo mail provider
    if provider_type == "emailtick":
        mail_client = EmailTickProvider(domain=emailtick_domain)
        email = mail_client.create()
    else:
        mail_client = InstantMailPopular()
        mail_info = mail_client.create_email(option=mail_option)
        email = mail_info["email"]

    password = generate_strong_password(16)
    print(f"📧 Email đăng ký : {email}")
    print(f"🔑 Mật khẩu      : {password}")
    print(f"🌐 Chế độ mạng   : {network_mode}")

    user_data_dir = os.path.join(tempfile.gettempdir(), f"th_acc_{int(time.time())}_{random.randint(100, 999)}")

    # 3. Khởi tạo cloakbrowser
    context = launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=headless,
        proxy=active_proxy,
        humanize=False
    )

    try:
        page = context.pages[0] if context.pages else context.new_page()

        print("[*] Đang truy cập https://tokenharbor.ai/login?mode=signup ...")
        page.goto("https://tokenharbor.ai/login?mode=signup", wait_until="domcontentloaded", timeout=35000)
        time.sleep(3)
        dismiss_dialogs_and_popups(page)

        email_input = page.wait_for_selector('input[name="email"]', timeout=10000)
        pwd_input = page.wait_for_selector('input[name="password"]', timeout=10000)
        submit_btn = page.wait_for_selector('button[type="submit"]', timeout=10000)

        if not email_input or not pwd_input or not submit_btn:
            print("❌ Không tìm thấy form đăng ký!")
            return False

        print(f"✍️ Điền Email: {email}...")
        email_input.type(email, delay=25)
        time.sleep(0.5)

        print("✍️ Điền Password...")
        pwd_input.type(password, delay=25)
        time.sleep(1)

        print("👉 Nhấn nút [Create account]...")
        try:
            submit_btn.click(force=True)
        except Exception:
            page.evaluate("() => { const b = document.querySelector('button[type=\"submit\"]'); if (b) b.click(); }")
        time.sleep(4)

        # Chờ phản hồi từ máy chủ
        is_success = False
        for i in range(12):
            current_url = page.url
            print(f"   [{i+1}/12] URL hiện tại: {current_url}")

            # Kiểm tra chuyển hướng thành công sang /dashboard
            if "/dashboard" in current_url:
                print("🎉 Đăng ký thành công và đã vào /dashboard!")
                is_success = True
                break

            # Kiểm tra thông báo lỗi cụ thể
            err_el = page.query_selector('p[data-bordered="true"], [role="alert"]')
            if err_el:
                err_text = err_el.inner_text().strip()
                if err_text and "Token Harbor" not in err_text:
                    if "too many sign-ups" in err_text.lower():
                        print(f"\n❌ [GIỚI HẠN IP MẠNG] {err_text}")
                        print("💡 IP mạng này đã chạm giới hạn đăng ký trong 1 giờ của Token Harbor.")
                        print("👉 Giải pháp: Đổi sang 4G phát từ điện thoại (bật tắt máy bay 3s), hoặc khởi động lại router Wi-Fi, hoặc chờ 1 giờ.")
                        return False
                    elif "already" in err_text.lower():
                        print(f"❌ Email này đã được sử dụng: {err_text}")
                        return False
                    elif "fast" in err_text.lower() or "breath" in err_text.lower():
                        print(f"⏳ Cảnh báo tần suất: {err_text}. Đang chờ 15s...")
                        time.sleep(15)
                        submit_btn.click()
                        time.sleep(3)
                        continue
                    elif "ip" in err_text.lower() or "vpn" in err_text.lower():
                        print(f"❌ Máy chủ từ chối kết nối IP/VPN: {err_text}")
                        return False
                    else:
                        print(f"⚠️ Thông báo máy chủ: {err_text}")

            time.sleep(2)

        if is_success:
            # 4. TỰ ĐỘNG BẤM 'XÁC MINH EMAIL' TRÊN TRANG TỔNG QUAN
            verified = verify_email_on_dashboard(page, email, mail_client, provider_type=provider_type)

            # 5. TỰ ĐỘNG LẤY API KEY
            api_key = extract_or_create_api_key(page)

            status_str = f"Status: Active & Email Verified ({network_mode})" if verified else f"Status: Active ({network_mode})"
            save_account(email, password, api_key=api_key, extra=status_str)
            return True
        else:
            print("❌ Đăng ký không thành công.")
            return False

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        try:
            context.close()
        except Exception:
            pass
        ProxyService.stop()


# =====================================================================
# HÀM XÁC MINH CHO TÀI KHOẢN ĐÃ CÓ SẴN
# =====================================================================
def verify_existing_account(email: str, password: str, headless: bool = False) -> bool:
    """Đăng nhập tài khoản có sẵn, vào Tổng quan và kích hoạt xác minh email"""
    print("\n" + "=" * 65)
    print(f"🔑 BẮT ĐẦU XÁC MINH EMAIL CHO TÀI KHOẢN CÓ SẴN: {email}")
    print("=" * 65)

    user_data_dir = os.path.join(tempfile.gettempdir(), f"th_ver_{int(time.time())}")
    context = launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=headless,
        humanize=False
    )

    try:
        page = context.pages[0] if context.pages else context.new_page()

        print("[*] Đang đăng nhập vào Token Harbor...")
        page.goto("https://tokenharbor.ai/login", wait_until="domcontentloaded", timeout=30000)
        time.sleep(3)
        dismiss_dialogs_and_popups(page)

        page.wait_for_selector('input[name="email"]', timeout=10000).fill(email)
        page.wait_for_selector('input[name="password"]', timeout=10000).fill(password)
        try:
            page.click('button[type="submit"]', force=True)
        except Exception:
            page.evaluate("() => document.querySelector('button[type=\"submit\"]').click()")
        time.sleep(5)

        # Chờ điều hướng về Tổng quan (/dashboard)
        try:
            page.wait_for_url("**/dashboard**", timeout=15000)
        except Exception:
            if "/dashboard" not in page.url:
                page.goto("https://tokenharbor.ai/dashboard", wait_until="domcontentloaded", timeout=20000)
        time.sleep(3)
        dismiss_dialogs_and_popups(page)

        # Xác định loại provider từ domain
        if "smarta4.com" in email:
            provider_type = "emailtick"
            mail_client = EmailTickProvider(domain="smarta4.com")
            mail_client._email = email
        else:
            provider_type = "instantmail"
            mail_client = InstantMailPopular()
            mail_client.current_email = email

        verified = verify_email_on_dashboard(page, email, mail_client, provider_type=provider_type)

        # Lấy API Key
        api_key = extract_or_create_api_key(page)
        save_account(email, password, api_key=api_key, extra="Status: Verified via Overview")
        return verified

    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False
    finally:
        try:
            context.close()
        except Exception:
            pass


# =====================================================================
# HÀM CHÍNH (CLI)
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Tự động tạo tài khoản Token Harbor và xác minh email tại Tổng quan")
    parser.add_argument("--headless", action="store_true", help="Chạy chế độ ẩn trình duyệt (mặc định: hiển thị)")
    parser.add_argument("--count", type=int, default=1, help="Số lượng tài khoản cần tạo (mặc định: 1)")
    parser.add_argument("--provider", type=str, default="emailtick", choices=["emailtick", "instantmail"],
                        help="Hộp thư tạm: emailtick (@smarta4.com) hoặc instantmail (@googlemail.com)")
    parser.add_argument("--domain", type=str, default="smarta4.com", help="Domain cho emailtick (mặc định: smarta4.com)")
    parser.add_argument("--option", type=str, default="+googlemail.com",
                        choices=["+googlemail.com", "googlemail.com", "+gmail.com", "gmail.com"],
                        help="Domain cho instantmail")
    parser.add_argument("--proxy", type=str, default=None,
                        help="Địa chỉ Proxy tùy chọn (ví dụ: socks5://127.0.0.1:2080 hoặc http://...)")
    parser.add_argument("--warp", action="store_true",
                        help="Tự động xoay và dùng Cloudflare WARP IPv6 Proxy miễn phí (cổng 2080)")
    parser.add_argument("--verify-account", nargs=2, metavar=("EMAIL", "PASSWORD"),
                        help="Chỉ thực hiện xác minh email trên Tổng quan cho tài khoản đã có sẵn")
    args = parser.parse_args()

    if args.verify_account:
        em, pw = args.verify_account
        verify_existing_account(email=em, password=pw, headless=args.headless)
        return

    net_info = "Cloudflare WARP (Cổng 2080)" if args.warp else (f"Proxy ({args.proxy})" if args.proxy else "IP máy trực tiếp (Direct IP)")
    print(f"🎯 Kế hoạch: Tạo {args.count} tài khoản Token Harbor")
    print(f"   📧 Hòm thư : {args.provider} (@{args.domain if args.provider == 'emailtick' else args.option})")
    print(f"   🌐 Kết nối : {net_info}")

    success_count = 0
    for i in range(args.count):
        print(f"\n[{i+1}/{args.count}] Tiến hành tạo tài khoản...")
        ok = create_single_account(
            provider_type=args.provider,
            mail_option=args.option,
            emailtick_domain=args.domain,
            proxy=args.proxy,
            use_warp=args.warp,
            headless=args.headless
        )
        if ok:
            success_count += 1
            print(f"✅ Hoàn tất tài khoản {i+1}/{args.count}!")
        else:
            print(f"❌ Chưa hoàn thành tài khoản {i+1}/{args.count}!")

        if i < args.count - 1:
            print("⏳ Tạm nghỉ 10 giây trước tài khoản tiếp theo...")
            time.sleep(10)

    print("\n" + "=" * 65)
    print(f"🏁 KẾT QUẢ: Thành công {success_count}/{args.count} tài khoản.")
    print(f"📂 Danh sách tài khoản: {ACCOUNTS_FILE}")
    print("=" * 65)


if __name__ == "__main__":
    main()


