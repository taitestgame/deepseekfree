import sys
import io
import time
import json
import base64
import random
import string
import re
import subprocess
import requests

# Đảm bảo in tiếng Việt không bị lỗi trên Windows console
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass


class InstantMailPopular:
    """
    Client API tạo và bắt thư CHUẨN XÁC theo 4 tùy chọn Tab 'Phổ biến' của Instant Mail:
    1. @+gmail.com      (Gmail Dot-Trick + Plus-Trick: xxx.yyy+random12@gmail.com)
    2. @gmail.com       (Gmail Dot-Trick: x.x.x.y.y.y@gmail.com)
    3. @googlemail.com  (Googlemail Dot-Trick: k.ilianoko.ndu.r.u@googlemail.com)
    4. @+googlemail.com (Googlemail Dot-Trick + Plus-Trick: ma.nl.iob...+random12@googlemail.com)
    """
    BASE_URL = "https://mail-server.1timetech.com/api"

    POPULAR_DOMAINS = [
        "+gmail.com",       # random @+gmail.com (Dot trick + Plus trick)
        "gmail.com",        # @gmail.com (Dot trick)
        "googlemail.com",   # @googlemail.com (Dot trick)
        "+googlemail.com"   # @+googlemail.com (Dot trick + Plus trick)
    ]

    # Danh sách Master Accounts thực tế từ hệ thống app
    MASTER_ACCOUNTS = [
        {"user": "tabichthao63366", "domain": "gmail.com"},
        {"user": "kilianokonduru",  "domain": "googlemail.com"},
        {"user": "manliobizness",   "domain": "googlemail.com"},
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            "Content-Type": "application/json",
            "Accept": "application/json",
        })
        self.current_email = None
        self.current_id = None

    @staticmethod
    def _encode(data: dict) -> str:
        b64 = base64.b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
        return b64[::-1]

    @staticmethod
    def _decode(raw_b64: str) -> dict:
        return json.loads(base64.b64decode(raw_b64[::-1]).decode("utf-8"))

    @staticmethod
    def apply_dot_trick(username: str) -> str:
        """
        Thuật toán Dot-Trick (Chèn ngẫu nhiên dấu chấm '.' giữa các chữ cái).
        Gmail coi tất cả các địa chỉ có dấu chấm như:
        't.a.b.i.c.h.t.h.a.o' và 'tabichthao' là CÙNG MỘT HÒM THƯ.
        """
        clean_user = username.replace(".", "")
        result = clean_user[0]
        for char in clean_user[1:]:
            if result[-1] != "." and random.random() < 0.45:
                result += "."
            result += char
        return result

    @staticmethod
    def apply_plus_trick(length: int = 12) -> str:
        """Sinh chuỗi ngẫu nhiên 12 ký tự cho thẻ '+' (Ví dụ: +a9sprl6pd5a6)"""
        return "".join(random.choices(string.ascii_lowercase + string.digits, k=length))

    def create_email(self, option: str = "+gmail.com") -> dict:
        """
        Tạo Email:
        - option='+gmail.com'       -> ví dụ: tabi.chth.ao.6.336.6+7d8g1f4a9b2c@gmail.com
        - option='gmail.com'        -> ví dụ: tabi.chth.ao.6.336.6@gmail.com
        - option='googlemail.com'   -> ví dụ: k.ilianoko.ndu.r.u@googlemail.com
        - option='+googlemail.com'  -> ví dụ: ma.nl.iob.i.z.n.es.s+a9sprl6pd5a6@googlemail.com
        """
        if "googlemail" in option:
            candidates = [m for m in self.MASTER_ACCOUNTS if m["domain"] == "googlemail.com"]
            selected_master = random.choice(candidates)["user"]
            domain_suffix = "googlemail.com"
        else:
            candidates = [m for m in self.MASTER_ACCOUNTS if m["domain"] == "gmail.com"]
            selected_master = random.choice(candidates)["user"] if candidates else "tabichthao63366"
            domain_suffix = "gmail.com"

        dotted_user = self.apply_dot_trick(selected_master)

        if option.startswith("+"):
            plus_tag = self.apply_plus_trick(12)
            generated_email = f"{dotted_user}+{plus_tag}@{domain_suffix}"
        else:
            generated_email = f"{dotted_user}@{domain_suffix}"

        self.current_email = generated_email
        self.current_id = generated_email

        return {
            "success": True,
            "email": generated_email,
            "id": generated_email,
            "option": option
        }

    def get_message_detail(self, email_address: str, message_id: str) -> dict:
        """
        Lấy chi tiết đầy đủ nội dung thư (bao gồm cả toàn bộ mã HTML và link đăng nhập/xác nhận).
        Endpoint chuẩn: GET /email/{email}/messages/{id}
        """
        url = f"{self.BASE_URL}/email/{email_address}/messages/{message_id}"
        try:
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                raw_data = resp.json().get("data", "")
                if raw_data:
                    return self._decode(raw_data)
        except Exception:
            pass
        return {}

    def get_messages(self, email_address: str = None) -> list:
        """
        Lấy danh sách thư từ server 1TimeTech cho email Gmail/Googlemail.
        """
        target_email = email_address or self.current_email
        if not target_email:
            raise ValueError("Chưa có địa chỉ email để lấy thư!")

        emails_to_check = [target_email]
        if "@googlemail.com" in target_email:
            emails_to_check.append(target_email.replace("@googlemail.com", "@gmail.com"))
        elif "@gmail.com" in target_email:
            emails_to_check.append(target_email.replace("@gmail.com", "@googlemail.com"))

        all_messages = []
        seen_ids = set()

        for em in emails_to_check:
            url = f"{self.BASE_URL}/email/{em}/messages"
            try:
                resp = self.session.get(url, timeout=10)
                if resp.status_code == 200:
                    raw_data = resp.json().get("data", "")
                    if raw_data and raw_data != "=01W":
                        msgs = self._decode(raw_data)
                        for m in msgs:
                            mid = m.get("id") or str(m)
                            if mid not in seen_ids:
                                seen_ids.add(mid)
                                m["_query_email"] = em
                                all_messages.append(m)
            except Exception:
                pass

        return all_messages

    @staticmethod
    def extract_otp_code(text: str) -> str:
        """Tự động quét và bóc tách mã OTP (4 - 8 chữ số) từ nội dung thư"""
        if not text:
            return None

        clean_text = re.sub(r'\b\d{4}[-/]\d{2}[-/]\d{2}\b', ' ', text)
        clean_text = re.sub(r'\b\d{2}:\d{2}:\d{2}\b', ' ', clean_text)
        for year in ["2024", "2025", "2026", "2027", "2028"]:
            clean_text = re.sub(r'\b' + year + r'\b', ' ', clean_text)

        p_keywords = r'(?:code|mã|otp|verification|password|xác thực|pin|xác minh)[\s:]*([0-9]{4,8})\b'
        match = re.search(p_keywords, clean_text, re.IGNORECASE)
        if match:
            return match.group(1)

        for p in [r'\b([0-9]{6})\b', r'\b([0-9]{4})\b', r'\b([0-9]{8})\b']:
            m = re.search(p, clean_text)
            if m:
                return m.group(1)
        return None

    @staticmethod
    def extract_verification_link(text: str) -> str:
        """Trích xuất link đăng nhập / xác nhận tài khoản (Magic link) nếu có"""
        if not text:
            return None
        links = re.findall(r'https?://[^\s<>"\'\)]+', text)
        clean_links = []
        for l in links:
            if any(ext in l.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.otf', '.ttf', '.svg', '.css', 'logo', 'social', 'icon', 'apple-touch']):
                continue
            clean_links.append(l)

        for link in clean_links:
            if any(k in link.lower() for k in ['magic-link', 'login', 'verify', 'confirm', 'auth', 'magic', 'token', 'action']):
                return link
        return clean_links[0] if clean_links else None

    def wait_for_inbox(self, timeout_seconds: int = 120, check_interval: int = 3) -> list:
        """
        Chờ thư đến và trích xuất mã OTP hoặc Magic Link
        """
        if not self.current_email:
            raise ValueError("Chưa khởi tạo email để chờ!")

        print("=" * 65)
        print(f"📧 ĐANG THEO DÕI HỘM THƯ: {self.current_email}")
        print(f"⏳ Chế độ chờ: Tối đa {timeout_seconds} giây (Kiểm tra mỗi {check_interval}s)")
        print("=" * 65)

        start_time = time.time()
        seen_message_ids = set()

        while time.time() - start_time < timeout_seconds:
            elapsed = int(time.time() - start_time)
            remaining = timeout_seconds - elapsed

            try:
                messages = self.get_messages()
            except Exception:
                messages = []

            new_messages = []
            for msg in messages:
                msg_id = msg.get("id") or str(msg)
                if msg_id not in seen_message_ids:
                    seen_message_ids.add(msg_id)
                    new_messages.append(msg)

            if new_messages:
                print(f"\n\n🔔 [TINH TING] PHÁT HIỆN {len(new_messages)} THƯ MỚI!")
                for idx, msg in enumerate(new_messages, 1):
                    msg_id = msg.get("id")
                    query_email = msg.get("_query_email") or self.current_email

                    detail = self.get_message_detail(query_email, msg_id) if msg_id else {}
                    full_html = detail.get("html") or msg.get("html") or ""
                    full_text = detail.get("text") or msg.get("text") or msg.get("body_text") or ""
                    html_content = re.sub(r'<(style|script)[^>]*>.*?</\1>', ' ', full_html, flags=re.DOTALL | re.IGNORECASE) if full_html else ""
                    clean_text = re.sub(r'<[^>]+>', ' ', html_content) if html_content else full_text
                    clean_text = " ".join(clean_text.split())

                    sender = msg.get("from") or detail.get("from") or "Không rõ người gửi"
                    subject = msg.get("subject") or detail.get("subject") or "(Không có tiêu đề)"

                    otp = self.extract_otp_code(f"{subject} {clean_text}")
                    link = self.extract_verification_link(full_html or full_text)

                    print("-" * 55)
                    print(f"📨 THƯ #{idx}")
                    print(f"👤 Người gửi : {sender}")
                    print(f"📌 Tiêu đề   : {subject}")
                    if otp:
                        print(f"🔑 MÃ OTP    : >> [ {otp} ] <<")
                    if link:
                        print(f"🔗 LINK ĐĂNG NHẬP / XÁC NHẬN :")
                        print(f"   👉 {link}")
                    print(f"📝 Nội dung  : {clean_text[:250]}..." if len(clean_text) > 250 else f"📝 Nội dung  : {clean_text}")
                    print("-" * 55)

                return new_messages

            spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"][elapsed % 10]
            print(f"\r{spinner} Đang đợi thư tới... ({elapsed}s trôi qua / còn {remaining}s) ", end="", flush=True)
            time.sleep(check_interval)

        print("\n\n❌ HẾT THỜI GIAN CHỜ (Timeout) - Chưa có thư nào gửi đến.")
        return []


if __name__ == "__main__":
    client = InstantMailPopular()
    selected_option = "+googlemail.com"
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip().lower().replace("@", "")
        if arg in client.POPULAR_DOMAINS:
            selected_option = arg
        elif ("+" + arg) in client.POPULAR_DOMAINS:
            selected_option = "+" + arg

    print(f"[+] Đang tạo Email: @{selected_option} ...")
    email_info = client.create_email(option=selected_option)
    print(f"✅ ĐÃ TẠO: {email_info.get('email')}")
    client.wait_for_inbox(timeout_seconds=60, check_interval=3)
