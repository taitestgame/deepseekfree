import os
import sys
import time
import requests

IP_TOOL_DIR = r"C:\python\ip"
WARP_AVAILABLE = False
if os.path.exists(os.path.join(IP_TOOL_DIR, "ipv6_tool.py")):
    if IP_TOOL_DIR not in sys.path:
        sys.path.insert(0, IP_TOOL_DIR)
    try:
        import ipv6_tool
        WARP_AVAILABLE = True
    except Exception:
        WARP_AVAILABLE = False


class ProxyService:
    PROXY_PORT = 2080
    PROXY_URL = f"http://127.0.0.1:{PROXY_PORT}"

    @classmethod
    def is_warp_available(cls) -> bool:
        return WARP_AVAILABLE

    @classmethod
    def is_healthy(cls) -> bool:
        proxies = {"http": cls.PROXY_URL, "https": cls.PROXY_URL}
        try:
            r = requests.get("https://api64.ipify.org?format=json", proxies=proxies, timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    @classmethod
    def get_current_ip(cls) -> str:
        proxies = {"http": cls.PROXY_URL, "https": cls.PROXY_URL}
        try:
            r = requests.get("https://api64.ipify.org?format=json", proxies=proxies, timeout=5)
            return r.json().get("ip", "unknown")
        except Exception:
            return "unknown"

    @classmethod
    def rotate_proxy(cls) -> str:
        """
        Xoay sang 1 địa chỉ IP mới toanh hoàn toàn miễn phí qua Cloudflare WARP.
        Mỗi lần gọi sẽ cấp 1 IPv6 và IPv4 Anycast mới.
        """
        if not WARP_AVAILABLE:
            print("[-] Không tìm thấy ipv6_tool tại C:\\python\\ip. Sử dụng kết nối trực tiếp.")
            return "direct"

        print("\n🔄 [PROXY FREE] Đang khởi tạo địa chỉ IP mới miễn phí qua Cloudflare WARP...")
        try:
            # 1. Dừng proxy cũ nếu đang chạy
            ipv6_tool.stop_ipv6()
            time.sleep(1)

            # 2. Đăng ký tài khoản WARP mới để nhận dải IP mới
            acc = ipv6_tool.generate_warp_account()
            ipv6_tool.build_singbox_config(acc)

            # 3. Khởi động tunnel sing-box
            ipv6_tool.start_ipv6(system_proxy=False)
            time.sleep(2)

            # 4. Kiểm tra sức khỏe kết nối
            for attempt in range(6):
                ip = cls.get_current_ip()
                if ip != "unknown":
                    print(f"✅ [PROXY FREE SẴN SÀNG] Public IP mới: {ip} (IPv6: {acc.get('ipv6', 'N/A')})")
                    return cls.PROXY_URL
                time.sleep(1)

            print("⚠️ Cảnh báo: Không thể xác nhận IP proxy sau 6 giây.")
            return cls.PROXY_URL
        except Exception as e:
            print(f"⚠️ Lỗi xoay proxy WARP: {e}")
            return "direct"

    @classmethod
    def stop(cls):
        """Dừng tunnel proxy khi hoàn tất đăng ký tài khoản"""
        if WARP_AVAILABLE:
            try:
                ipv6_tool.stop_ipv6()
            except Exception:
                pass


if __name__ == "__main__":
    print("WARP available:", ProxyService.is_warp_available())
    proxy = ProxyService.rotate_proxy()
    print("Proxy URL:", proxy)
    print("Public IP:", ProxyService.get_current_ip())
    ProxyService.stop()
