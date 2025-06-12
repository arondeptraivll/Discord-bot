# spammer.py (Phiên bản 5.1 - Tích hợp Async)
import requests
import re
import random
import string
import threading
import time
import asyncio
from typing import Optional, Callable
# Thay thế lời gọi hàm cũ bằng lời gọi hàm async mới
from keygen import validate_key as async_validate_license_from_file

class SpamManager:
    def __init__(self):
        # API Endpoints
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        
        self.REQUEST_TIMEOUT = 15
        self.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
        if not self.FIREBASE_APP_CHECK_TOKEN:
            print("CRITICAL: Không thể lấy App Check Token.")
        
        # Session State
        self.active_spam_sessions = {}
        self.last_error_message = ""
        self.emojis = [
            '😀', '😂', '😍', '🥰', '😊', '😇', '😚', '😘', '😻', '😽', '🤗', '😎', '🥳',
            '😜', '🤩', '😢', '😡', '😴', '🙈', '🙌', '💖', '🔥', '👍', '✨', '🌟', '🍎',
            '🍕', '🚀', '🎉', '🎈', '🌈', '🐶', '🐱', '🦁', '😋', '😬', '😳', '😷', '🤓',
            '😈', '👻', '💪', '👏', '🙏', '💕', '💔', '🌹', '🍒', '🍉', '🍔', '🍟', '☕',
            '🍷', '🎂', '🎁', '🎄', '🎃', '🔔', '⚡', '💡', '📚', '✈️', '🚗', '🏠', '⛰️',
            '🌊', '☀️', '☁️', '❄️', '🌙', '🐻', '🐼', '🐸', '🐝', '🦄', '🐙', '🦋', '🌸',
            '🌺', '🌴', '🏀', '⚽', '🎸'
        ]

    def _fetch_app_check_token(self):
        try:
            res = requests.get(self.TOKEN_API_URL, timeout=self.REQUEST_TIMEOUT)
            res.raise_for_status()
            return res.json().get("data", {}).get("token")
        except requests.RequestException as e:
            print(f"Lỗi khi lấy App Check Token: {e}")
            return None

    def validate_license(self, key: str) -> dict:
        """
        Wrapper đồng bộ để gọi hàm validate_key bất đồng bộ từ một luồng.
        """
        # Chạy coroutine trong một event loop mới
        return asyncio.run(async_validate_license_from_file(key))

    def find_locket_uid(self, user_input: str) -> Optional[str]:
        user_input = user_input.strip()
        self.last_error_message = ""
        url_to_check = f"https://locket.cam/{user_input}" if not re.match(r'^https?://', user_input) else user_input
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"}
            response = requests.get(url_to_check, headers=headers, timeout=self.REQUEST_TIMEOUT, allow_redirects=True)
            response.raise_for_status()
            uid = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', response.url)
            if uid: return uid.group(1)
            js_redirect_match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', response.text)
            if js_redirect_match:
                uid_from_js = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', js_redirect_match.group(1))
                if uid_from_js: return uid_from_js.group(1)
            self.last_error_message = "Không thể tìm thấy link mời Locket hợp lệ trong trang."
            return None
        except requests.RequestException as e:
            self.last_error_message = f"Lỗi kết nối mạng: {e}"; return None

    def _finalize_user(self, id_token: str, custom_name: str, use_emojis: bool) -> bool:
        first_name = custom_name[:20] # Giới hạn 20 ký tự
        last_name = ' '.join(random.sample(self.emojis, 5)) if use_emojis else ""
        
        payload = {
            "data": {
                "username": ''.join(random.choice(string.ascii_lowercase) for _ in range(8)),
                "last_name": last_name,
                "first_name": first_name
            }
        }
        headers = {'Content-Type': 'application/json', 'Authorization': f"Bearer {id_token}"}
        try:
            res = requests.post(f"{self.API_LOCKET_URL}/finalizeTemporaryUser", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return res.status_code == 200
        except requests.RequestException:
            return False

    def _send_friend_request(self, id_token: str, target_uid: str) -> bool:
        payload = {"data": {"user_uid": target_uid}}
        headers = {'Content-Type': 'application/json', 'Authorization': f"Bearer {id_token}"}
        try:
            res = requests.post(f"{self.API_LOCKET_URL}/sendFriendRequest", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return res.status_code == 200
        except requests.RequestException:
            return False

    def start_spam_session(self, user_id: int, target: str, custom_name: str, use_emojis: bool, update_callback: Callable):
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
            
            while not stop_event.is_set():
                threads = [threading.Thread(target=self._run_single_spam_thread, args=(target_uid, custom_name, use_emojis, stop_event, stats)) for _ in range(25)]
                for t in threads: t.start()
                for t in threads: t.join() 
                
                if time.time() - last_update > 2.5:
                    update_callback(status="running", stats=stats)
                    last_update = time.time()

            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions:
                del self.active_spam_sessions[user_id]
            
        session_thread = threading.Thread(target=spam_loop)
        session_thread.daemon = True
        session_thread.start()
        # Thông báo ban đầu cho người dùng biết bot đã bắt đầu
        update_callback(status="started", message=f"✅ Đã khởi động phiên spam đến `{target}`.")

    def _run_single_spam_thread(self, target_uid, custom_name, use_emojis, stop_event, stats):
        if not self.FIREBASE_APP_CHECK_TOKEN or stop_event.is_set():
            if not stop_event.is_set(): stats['failed'] += 1
            return
            
        try:
            # Step 1: Create Account
            headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.FIREBASE_APP_CHECK_TOKEN}
            email = f"{''.join(random.choices(string.ascii_lowercase + string.digits, k=15))}@thanhdieu.com"
            password = 'zlocket' + ''.join(random.choices(string.ascii_lowercase + string.digits, k=7))
            payload = {"data": {"email": email, "password": password, "client_email_verif": True, "platform": "ios"}}
            
            res = requests.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)

            if res.status_code != 200 or stop_event.is_set():
                if not stop_event.is_set(): stats['failed'] += 1
                return
            
            # Step 2: Get ID Token
            id_token = res.json().get("result", {}).get("idToken")
            if not id_token:
                stats['failed'] += 1
                return

            # Step 3: Finalize user with custom name
            if not self._finalize_user(id_token, custom_name, use_emojis):
                stats['failed'] += 1
                return

            # Step 4: Send friend request
            if self._send_friend_request(id_token, target_uid):
                stats['success'] += 1
            else:
                stats['failed'] += 1

        except:
            if not stop_event.is_set():
                stats['failed'] += 1

    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions:
            self.active_spam_sessions[user_id].set()
            return True
        return False
