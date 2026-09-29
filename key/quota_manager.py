import os
import sys
import time
import json
import re
import argparse
import subprocess
import requests

# Cấu hình UTF-8 cho Windows console
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stderr.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ACCOUNTS_FILE = os.path.join(BASE_DIR, "accounts.txt")
TOKENHARBOR_CONFIG_PATH = os.path.expanduser(r"~\.tokenharbor\config.json")
TOKENHARBOR_CMD = os.path.expanduser(r"~\.tokenharbor\bin\tokenharbor.cmd")


# =====================================================================
# Tiện ích đọc / ghi danh sách tài khoản
# =====================================================================
def load_accounts():
    """Đọc toàn bộ tài khoản từ accounts.txt"""
    accounts = []
    if not os.path.exists(ACCOUNTS_FILE):
        return accounts

    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f):
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            email_m = re.search(r"Email:\s*([^\s|]+)", line_str)
            pass_m = re.search(r"Password:\s*([^\s|]+)", line_str)
            key_m = re.search(r"API_Key:\s*([^\s|]+)", line_str)
            status_m = re.search(r"Status:\s*([^|]+)", line_str)

            if email_m and pass_m:
                accounts.append({
                    "index": idx,
                    "email": email_m.group(1).strip(),
                    "password": pass_m.group(1).strip(),
                    "api_key": key_m.group(1).strip() if key_m else "",
                    "status": status_m.group(1).strip() if status_m else "Active",
                    "raw_line": line_str
                })
    return accounts


def save_account_status(email: str, new_status: str, new_key: str = None):
    """Cập nhật trạng thái hoặc API Key cho tài khoản trong accounts.txt"""
    if not os.path.exists(ACCOUNTS_FILE):
        return

    lines = []
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            l = line.strip()
            if not l:
                continue
            if f"Email: {email}" in l:
                # Cập nhật key nếu có
                if new_key and "API_Key:" not in l:
                    l = l.replace(f"Email: {email} | Password:", f"Email: {email} | Password:")
                    l += f" | API_Key: {new_key}"
                elif new_key and "API_Key:" in l:
                    l = re.sub(r"API_Key:\s*[^\s|]+", f"API_Key: {new_key}", l)

                # Cập nhật status
                if "Status:" in l:
                    l = re.sub(r"Status:\s*[^|]+", f"Status: {new_status}", l)
                else:
                    l += f" | Status: {new_status}"
            lines.append(l)

    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        for l in lines:
            f.write(l + "\n")


# =====================================================================
# Tiện ích cấu hình Token Harbor CLI & Môi trường hệ thống
# =====================================================================
def get_current_tokenharbor_key() -> str:
    """Đọc API Key hiện tại từ file config của Token Harbor CLI"""
    if os.path.exists(TOKENHARBOR_CONFIG_PATH):
        try:
            with open(TOKENHARBOR_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("key", "").strip()
        except Exception:
            pass
    return os.environ.get("TOKENHARBOR_API_KEY", "").strip()


def apply_tokenharbor_key(api_key: str, email: str = ""):
    """
    Cập nhật API Key mới cho:
    1. Cấu hình ~/.tokenharbor/config.json
    2. Biến môi trường hệ thống Windows (setx TOKENHARBOR_API_KEY)
    3. Biến môi trường trong process hiện tại
    """
    print(f"\n🔄 [XOAY KEY] Đang áp dụng API Key mới cho hệ thống...")
    os.environ["TOKENHARBOR_API_KEY"] = api_key
    os.environ["OPENAI_BASE_URL"] = "https://tokenharbor.ai/v1"

    # 1. Cập nhật ~/.tokenharbor/config.json
    try:
        os.makedirs(os.path.dirname(TOKENHARBOR_CONFIG_PATH), exist_ok=True)
        config_data = {}
        if os.path.exists(TOKENHARBOR_CONFIG_PATH):
            try:
                with open(TOKENHARBOR_CONFIG_PATH, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
            except Exception:
                config_data = {}

        config_data["key"] = api_key
        with open(TOKENHARBOR_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=2)
        print(f"   ✅ Đã cập nhật Token Harbor config: {TOKENHARBOR_CONFIG_PATH}")
    except Exception as e:
        print(f"   ⚠️ Lỗi ghi file config.json: {e}")

    # 2. Cập nhật Claude Code (~/.claude/settings.json) - GIỮ NGUYÊN MODEL HIỆN TẠI
    claude_settings_path = os.path.expanduser(r"~/.claude/settings.json")
    if os.path.exists(claude_settings_path):
        try:
            with open(claude_settings_path, "r", encoding="utf-8") as f:
                c_data = json.load(f)
            c_data.setdefault("env", {})
            c_data["env"]["ANTHROPIC_BASE_URL"] = "https://tokenharbor.ai"
            c_data["env"]["ANTHROPIC_AUTH_TOKEN"] = api_key
            # GIỮ NGUYÊN MODEL: không ghi đè ANTHROPIC_MODEL nếu người dùng đã có
            if "ANTHROPIC_MODEL" not in c_data["env"]:
                c_data["env"]["ANTHROPIC_MODEL"] = "th-orchestra"
            with open(claude_settings_path, "w", encoding="utf-8") as f:
                json.dump(c_data, f, indent=2)
            current_m = c_data["env"].get("ANTHROPIC_MODEL", "mặc định")
            print(f"   ✅ Claude Code: Đã tráo Key mới, GIỮ NGUYÊN MODEL: '{current_m}' (Không bị bắt chọn lại!)")
        except Exception as e:
            print(f"   ⚠️ Lỗi cập nhật Claude Code: {e}")

    # 3. Cập nhật OpenCode (~/.config/opencode/opencode.json) - BẢO LƯU MODEL
    opencode_path = os.path.expanduser(r"~/.config/opencode/opencode.json")
    if os.path.exists(opencode_path):
        try:
            with open(opencode_path, "r", encoding="utf-8") as f:
                o_data = json.load(f)
            # Đảm bảo provider tokenharbor có sẵn key
            if "provider" in o_data and "tokenharbor" in o_data["provider"]:
                o_data["provider"]["tokenharbor"].setdefault("options", {})
                o_data["provider"]["tokenharbor"]["options"]["baseURL"] = "https://tokenharbor.ai/v1"
                o_data["provider"]["tokenharbor"]["options"]["apiKey"] = "{env:TOKENHARBOR_API_KEY}"
            with open(opencode_path, "w", encoding="utf-8") as f:
                json.dump(o_data, f, indent=2)
            current_om = o_data.get("model", "mặc định")
            print(f"   ✅ OpenCode: Đã bảo lưu cấu hình & MODEL: '{current_om}' (Không bị reset!)")
        except Exception as e:
            print(f"   ⚠️ Lỗi cập nhật OpenCode: {e}")

    # 4. Gán biến môi trường Windows vĩnh viễn (User level)
    try:
        subprocess.run(
            ["setx", "TOKENHARBOR_API_KEY", api_key],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        print(f"   ✅ Đã gán biến môi trường hệ thống: TOKENHARBOR_API_KEY={api_key[:12]}...")
    except Exception:
        pass

    # 5. Cập nhật Halyard IDE (~/.halyard) - GIỮ NGUYÊN MODEL
    halyard_dir = os.path.expanduser(r"~/.halyard")
    if os.path.exists(halyard_dir):
        try:
            h_json = os.path.join(halyard_dir, "credentials.json")
            with open(h_json, "w", encoding="utf-8") as f:
                json.dump({"api_key": api_key}, f, indent=2)
            h_yaml = os.path.join(halyard_dir, ".credentials.yaml")
            with open(h_yaml, "w", encoding="utf-8") as f:
                f.write(f"HALYARD_API_KEY: {api_key}\n")
            print("   ✅ Halyard IDE: Đã tráo Key mới vào credentials.json & .credentials.yaml (Giữ nguyên model!)")
        except Exception as e:
            print(f"   ⚠️ Lỗi cập nhật Halyard: {e}")


# =====================================================================
# Kiểm tra Quota Token Harbor
# =====================================================================
def check_quota_via_key(api_key: str):
    """
    Kiểm tra trạng thái của Key qua API Gateway:
    - https://tokenharbor.ai/v1/models
    """
    if not api_key:
        return {"ok": False, "error": "Chưa có API Key"}

    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "TokenHarbor-QuotaWatcher/1.0"
    }

    try:
        resp = requests.get("https://tokenharbor.ai/v1/models", headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            models = [m.get("id") for m in data.get("data", [])]
            return {
                "ok": True,
                "verified": True,
                "models_count": len(models),
                "models": models[:6],
                "status_code": 200
            }
        elif resp.status_code == 403:
            err = resp.json().get("error", {})
            msg = err.get("message", "")
            code = err.get("code", "")
            return {
                "ok": False,
                "verified": False,
                "error": "Email chưa được xác minh (Email verification required)",
                "detail": msg,
                "code": code,
                "status_code": 403
            }
        elif resp.status_code == 429:
            return {
                "ok": False,
                "verified": True,
                "exhausted": True,
                "error": "Hết hạn mức Quota (429 RateLimit/Exhausted)",
                "status_code": 429
            }
        else:
            return {
                "ok": False,
                "error": f"Lỗi phản hồi HTTP {resp.status_code}",
                "detail": resp.text[:200],
                "status_code": resp.status_code
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}


def check_quota_via_browser_session(email: str, password: str):
    """
    Đăng nhập lấy thông tin chi tiết Quota từ API nội bộ /api/me/free-tier:
    - used_pct: % quota đã dùng
    - req_used: số request đã dùng
    - exhausted: boolean
    - reset_at: thời gian reset
    """
    import tempfile
    from cloakbrowser import launch_persistent_context

    user_data_dir = os.path.join(tempfile.gettempdir(), f"th_qcheck_{int(time.time())}")
    ctx = launch_persistent_context(user_data_dir=user_data_dir, headless=True)
    try:
        page = ctx.pages[0]
        page.goto("https://tokenharbor.ai/login", wait_until="domcontentloaded", timeout=25000)
        time.sleep(2)
        try:
            page.click('button:has-text("Essential only")', timeout=2000)
        except Exception:
            pass

        page.wait_for_selector('input[name="email"]', timeout=8000).type(email, delay=15)
        page.wait_for_selector('input[name="password"]', timeout=8000).type(password, delay=15)
        page.click('button[type="submit"]')
        time.sleep(5)

        # Đóng popup nếu có
        page.evaluate('''() => {
            document.querySelectorAll('[role="dialog"], .fixed.inset-0').forEach(el => el.remove());
        }''')

        # Gọi API /api/me/free-tier
        free_tier = page.evaluate('''async () => {
            try {
                const res = await fetch("/api/me/free-tier");
                return await res.json();
            } catch(e) {
                return { error: e.toString() };
            }
        }''')
        return free_tier
    except Exception as e:
        return {"error": str(e)}
    finally:
        try:
            ctx.close()
        except Exception:
            pass


# =====================================================================
# Tự động xoay tài khoản (Rotate Account)
# =====================================================================
def rotate_to_next_account(current_email: str = None) -> dict:
    """
    Chuyển sang tài khoản tiếp theo trong accounts.txt còn khả dụng
    """
    accounts = load_accounts()
    if not accounts:
        print("❌ Không có tài khoản nào trong accounts.txt!")
        return None

    # Đánh dấu tài khoản hiện tại hết Quota nếu có
    if current_email:
        save_account_status(current_email, "Exhausted (Hết Quota)")

    # Tìm tài khoản khả dụng tiếp theo
    candidate = None
    for acc in accounts:
        if acc["email"] == current_email:
            continue
        if "exhausted" not in acc["status"].lower():
            candidate = acc
            break

    if not candidate:
        print("⚠️ Tất cả tài khoản hiện có đều đã hết hạn mức Quota!")
        print("🚀 Đang tự động kích hoạt tạo tài khoản mới ngay lập tức...")
        new_acc = trigger_create_new_account()
        return new_acc

    print(f"🎯 Đã chọn tài khoản tiếp theo: {candidate['email']}")
    if candidate.get("api_key"):
        apply_tokenharbor_key(candidate["api_key"], candidate["email"])
    else:
        print(f"ℹ️ Tài khoản {candidate['email']} chưa có API Key. Đang tạo API Key...")
        # Tạo key và cập nhật
        from create_account_direct import extract_or_create_api_key
        # Thử lấy key qua browser nếu cần
    return candidate


# =====================================================================
# Tự động kích hoạt tạo tài khoản mới (Backup Registration)
# =====================================================================
def trigger_create_new_account():
    """
    Kích hoạt tiến trình tạo 1 tài khoản mới qua hòm thư EmailTick (@smarta4.com)
    được lưu tự động vào accounts.txt
    """
    print("\n" + "=" * 65)
    print("⚡ [TỰ ĐỘNG KÍCH HOẠT] Quota sắp hết (<20%) -> Đang tạo tài khoản mới dự phòng...")
    print("=" * 65)

    try:
        from create_account_direct import create_single_account
        ok = create_single_account(
            provider_type="emailtick",
            emailtick_domain="smarta4.com",
            headless=True
        )
        if ok:
            print("🎉 TẠO TÀI KHOẢN MỚI THÀNH CÔNG! Đã cập nhật vào accounts.txt.")
            accs = load_accounts()
            return accs[-1] if accs else None
        else:
            print("❌ Quá trình tự động tạo tài khoản dự phòng gặp sự cố.")
            return None
    except Exception as e:
        print(f"❌ Lỗi khi tự động tạo tài khoản: {e}")
        return None


# =====================================================================
# Giám sát Quota định kỳ (Watchdog)
# =====================================================================
def watch_quota(interval_seconds: int = 60, threshold_pct: float = 20.0):
    """
    Vòng lặp giám sát:
    - Nếu Quota còn lại < threshold_pct (mặc định 20%): Tự động tạo tài khoản mới dự phòng.
    - Nếu Quota cạn kiệt (0% hoặc 429): Tự động xoay sang tài khoản tiếp theo.
    """
    print("=" * 65)
    print("🛡️ TOKEN HARBOR QUOTA WATCHDOG ĐANG KHỞI CHẠY")
    print(f"   ⏱️ Chu kỳ kiểm tra : Mỗi {interval_seconds} giây")
    print(f"   ⚠️ Ngưỡng tạo acc   : Quota còn lại dưới {threshold_pct}%")
    print("=" * 65)

    accounts = load_accounts()
    current_key = get_current_tokenharbor_key()

    # Tìm account tương ứng với key
    active_acc = None
    for acc in accounts:
        if acc.get("api_key") and acc["api_key"] == current_key:
            active_acc = acc
            break

    if not active_acc and accounts:
        active_acc = accounts[0]
        if active_acc.get("api_key"):
            apply_tokenharbor_key(active_acc["api_key"], active_acc["email"])

    backup_created = False

    while True:
        try:
            print(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Đang kiểm tra Quota...")
            if not active_acc:
                print("⚠️ Chưa có tài khoản active. Đang nạp tài khoản...")
                active_acc = rotate_to_next_account()
                if not active_acc:
                    time.sleep(interval_seconds)
                    continue

            key = active_acc.get("api_key") or get_current_tokenharbor_key()
            print(f"👤 Tài khoản active : {active_acc['email']}")
            print(f"🔑 API Key          : {key[:15]}...{key[-5:] if len(key)>20 else ''}")

            # 1. Kiểm tra qua Key
            key_stat = check_quota_via_key(key)
            if not key_stat.get("ok"):
                if key_stat.get("exhausted"):
                    print(f"❌ [CẠN KIỆT QUOTA] Tài khoản đã hết 100% hạn mức (429 RateLimit).")
                    active_acc = rotate_to_next_account(current_email=active_acc["email"])
                    backup_created = False
                    continue
                elif key_stat.get("status_code") == 403:
                    print(f"⚠️ {key_stat.get('error')}: Vui lòng bấm link xác minh email.")

            # 2. Đọc chi tiết % Quota từ Session Web
            session_stat = check_quota_via_browser_session(active_acc["email"], active_acc["password"])
            if session_stat and "used_pct" in session_stat:
                used_pct = session_stat.get("used_pct", 0)
                req_used = session_stat.get("req_used", 0)
                exhausted = session_stat.get("exhausted", False)
                remaining_pct = max(0, 100 - used_pct)

                print(f"📊 QUOTA BÁO CÁO:")
                print(f"   - Đã sử dụng   : {used_pct}% ({req_used} requests)")
                print(f"   - Còn lại      : {remaining_pct}%")
                print(f"   - Trạng thái   : {'🔴 HẾT QUOTA' if exhausted else '🟢 KHẢ DỤNG'}")

                # Kiểm tra cạn kiệt
                if exhausted or remaining_pct <= 0:
                    print("🚨 Quota đã hết hoàn toàn! Bắt đầu xoay tài khoản...")
                    active_acc = rotate_to_next_account(current_email=active_acc["email"])
                    backup_created = False
                    continue

                # Kiểm tra ngưỡng dưới 20%
                if remaining_pct < threshold_pct and not backup_created:
                    print(f"⚠️ CẢNH BÁO: Quota còn lại ({remaining_pct}%) dưới ngưỡng {threshold_pct}%!")
                    trigger_create_new_account()
                    backup_created = True
                elif remaining_pct >= threshold_pct:
                    backup_created = False
            else:
                print("ℹ️ Đã kiểm tra kết nối qua API Gateway (OK).")

        except Exception as e:
            print(f"[-] Lỗi trong chu kỳ giám sát: {e}")

        print(f"💤 Đang nghỉ {interval_seconds}s trước lần kiểm tra tiếp theo...")
        time.sleep(interval_seconds)


# =====================================================================
# HÀM CHÍNH (CLI)
# =====================================================================
def main():
    parser = argparse.ArgumentParser(description="Quản lý & Tự động xoay Quota Token Harbor")
    parser.add_argument("--check", action="store_true", help="Kiểm tra trạng thái Quota hiện tại")
    parser.add_argument("--rotate", action="store_true", help="Xoay sang tài khoản tiếp theo trong danh sách")
    parser.add_argument("--watch", action="store_true", help="Chạy chế độ tự động giám sát và xoay Quota")
    parser.add_argument("--interval", type=int, default=60, help="Chu kỳ kiểm tra tính bằng giây (mặc định: 60)")
    parser.add_argument("--threshold", type=float, default=20.0, help="Ngưỡng %% quota còn lại để tạo acc mới (mặc định: 20)")
    parser.add_argument("--set-key", type=str, help="Gán trực tiếp API Key cho hệ thống")

    args = parser.parse_args()

    if args.set_key:
        apply_tokenharbor_key(args.set_key)
        return

    if args.rotate:
        current_acc = load_accounts()
        curr_email = current_acc[0]["email"] if current_acc else None
        rotate_to_next_account(current_email=curr_email)
        return

    if args.watch:
        watch_quota(interval_seconds=args.interval, threshold_pct=args.threshold)
        return

    # Mặc định: --check
    accounts = load_accounts()
    current_key = get_current_tokenharbor_key()
    print("=" * 65)
    print("📋 KIỂM TRA TRẠNG THÁI TOKEN HARBOR & QUOTA")
    print("=" * 65)
    print(f"🔑 Key hệ thống hiện tại : {current_key if current_key else '(Chưa cấu hình)'}")
    print(f"📂 Tổng số tài khoản     : {len(accounts)}")
    print("-" * 65)

    for i, acc in enumerate(accounts, 1):
        print(f"[{i}] {acc['email']}")
        print(f"    Mật khẩu : {acc['password']}")
        print(f"    API Key  : {acc['api_key'][:15]}... ({'Đang dùng' if acc['api_key'] == current_key else 'Dự phòng'})" if acc['api_key'] else "    API Key  : (Chưa có)")
        print(f"    Trạng thái: {acc['status']}")

    if current_key:
        print("\n🔍 Đang kiểm tra tình trạng kết nối API Gateway của Key hiện tại...")
        stat = check_quota_via_key(current_key)
        if stat.get("ok"):
            print(f"✅ Key hợp lệ! Gateway trả về {stat.get('models_count')} models khả dụng.")
            print(f"   Models tiêu biểu: {', '.join(stat.get('models', []))}")
        else:
            print(f"❌ Thông báo lỗi từ API: {stat.get('error')}")
            if stat.get("detail"):
                print(f"   Chi tiết: {stat.get('detail')}")

    print("=" * 65)


if __name__ == "__main__":
    main()
