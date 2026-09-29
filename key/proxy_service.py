import os
import sys
import time
import subprocess
import requests

IP_TOOL_DIR = r"C:\python\ip"
if IP_TOOL_DIR not in sys.path:
    sys.path.insert(0, IP_TOOL_DIR)

import ipv6_tool

class ProxyService:
    PROXY_URL = "socks5h://127.0.0.1:2080"
    
    @classmethod
    def is_healthy(cls) -> bool:
        proxies = {"http": cls.PROXY_URL, "https": cls.PROXY_URL}
        try:
            r = requests.get("https://api64.ipify.org?format=json", proxies=proxies, timeout=4)
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
        print("[proxy] Dang xoay IP moi qua Cloudflare WARP IPv6...")
        # 1. Kill old singbox
        subprocess.run("taskkill /f /im sing-box.exe", shell=True, capture_output=True)
        time.sleep(1)
        
        # 2. Gen new WARP IPv6
        acc = ipv6_tool.generate_warp_account()
        ipv6_tool.build_singbox_config(acc)
        
        # 3. Start sing-box using cmd /c start
        cmd = f'cmd.exe /c start /b "" "{ipv6_tool.SING_BOX_EXE}" run -c "{ipv6_tool.CONFIG_FILE}"'
        subprocess.Popen(cmd, shell=True)
        
        # 4. Wait for it to bind
        time.sleep(3)
        for _ in range(5):
            ip = cls.get_current_ip()
            if ip != "unknown":
                print(f"[proxy] Proxy san sang! Public IP moi: {ip}")
                return ip
            time.sleep(1)
            
        print("[proxy] Canh bao: Khong the ket noi proxy sau 8 giay!")
        return "unknown"

if __name__ == "__main__":
    ip = ProxyService.rotate_proxy()
    print("Ket qua IP:", ip)
    print("Healthy:", ProxyService.is_healthy())
