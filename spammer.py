# spammer.py (Phiên bản 2.4 - Asyncio Executor Fix)
import requests
import re
import random
import string
import threading
import time
import queue
import asyncio
from typing import Optional, Callable
from keygen import validate_key as validate_license_from_file

class Spammer:
    def __init__(self, proxy: str, target_uid: str, custom_name: str):
        self.API_LOCKET_URL="https://api.locketcamera.com"; self.FIREBASE_AUTH_URL="https://www.googleapis.com/identitytoolkit/v3/relyingparty"; self.FIREBASE_API_KEY="AIzaSyCQngaaXQIfJaH0aS2l7REgIjD7nL431So"; self.REQUEST_TIMEOUT=15
        self.proxy_str,self.proxies_dict,self.target_uid,self.custom_name=proxy,self._format_proxy(proxy),target_uid,custom_name
        self.session=requests.Session(); self.session.proxies=self.proxies_dict; self.firebase_app_check=SpamManager.FIREBASE_APP_CHECK_TOKEN; self.id_token,self.local_id=None,None
    def _format_proxy(self,proxy_str):
        if not proxy_str or not proxy_str.startswith(('http://','https://')): proxy_str=f"http://{proxy_str}"
        return{"http":proxy_str,"https":proxy_str}
    def _rand_str(self,length=10,chars=string.ascii_lowercase+string.digits): return''.join(random.choice(chars) for _ in range(length))
    def _create_account(self):
        email,password=f"{self._rand_str(15)}@thanhdieu.com",'zlocket'+self._rand_str(7)
        payload,headers={"data":{"email":email,"password":password,"client_email_verif":True,"platform":"ios"}},{'Content-Type':'application/json','X-Firebase-AppCheck':self.firebase_app_check}
        try: return (email,password) if self.session.post(f"{self.API_LOCKET_URL}/createAccountWithEmailPassword",headers=headers,json=payload,timeout=self.REQUEST_TIMEOUT).status_code==200 else (None,None)
        except:return None,None
    def _sign_in(self,email,password):
        payload,headers={"email":email,"password":password,"returnSecureToken":True},{'Content-Type':'application/json','X-Firebase-AppCheck':self.firebase_app_check}
        try:
            res=self.session.post(f"{self.FIREBASE_AUTH_URL}/verifyPassword?key={self.FIREBASE_API_KEY}",headers=headers,json=payload,timeout=self.REQUEST_TIMEOUT)
            if res.status_code==200 and 'idToken' in res.json(): self.id_token,self.local_id=res.json()['idToken'],res.json()['localId'];return True
        except:pass
        return False
    def _finalize_user(self):
        payload,headers={"data":{"username":self._rand_str(8,string.ascii_lowercase),"last_name":"✨","first_name":self.custom_name[:20]}},{'Content-Type':'application/json','Authorization':f'Bearer {self.id_token}'}
        try:return self.session.post(f"{self.API_LOCKET_URL}/finalizeTemporaryUser",headers=headers,json=payload,timeout=self.REQUEST_TIMEOUT).status_code==200
        except:return False
    def _send_friend_request(self):
        payload,headers={"data":{"user_uid":self.target_uid,"source":"signUp"}},{'Content-Type':'application/json','Authorization':f'Bearer {self.id_token}'}
        try:return self.session.post(f"{self.API_LOCKET_URL}/sendFriendRequest",headers=headers,json=payload,timeout=self.REQUEST_TIMEOUT).status_code==200
        except:return False
    def run_cycle(self):
        if not self.firebase_app_check:return"failed",0
        email,password=self._create_account()
        if not email:return"failed",0
        if not self._sign_in(email,password):return"failed",0
        if not self._finalize_user():return"failed",0
        sent_count=sum(1 for _ in range(16) if self._send_friend_request())
        return("success",sent_count) if sent_count>0 else("failed",0)


class SpamManager:
    FIREBASE_APP_CHECK_TOKEN=None
    def __init__(self):
        self.TOKEN_API_URL="https://thanhdieu.com/api/v1/locket/token"
        self.PROXY_APIS=['https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all','https://api.proxyscrape.com/v2/?request=displayproxies&protocol=https&timeout=20000&country=all&ssl=all&anonymity=all',]
        self.active_spam_sessions={}
        self.proxy_queue=queue.Queue()
    def _ensure_dependencies(self):
        if not SpamManager.FIREBASE_APP_CHECK_TOKEN:
            SpamManager.FIREBASE_APP_CHECK_TOKEN=self._fetch_app_check_token()
            if not SpamManager.FIREBASE_APP_CHECK_TOKEN:return False
        if self.proxy_queue.empty():
            if self._load_proxies()==0:return False
        return True
    def _fetch_app_check_token(self):
        try:return requests.get(self.TOKEN_API_URL,timeout=15).json().get("data",{}).get("token")
        except:return None
    def _load_proxies(self):
        proxies=set()
        try:
            with open('proxy.txt','r')as f:proxies.update(p.strip()for p in f if p.strip())
        except FileNotFoundError:pass
        for url in self.PROXY_APIS:
            try:
                res=requests.get(url,timeout=15);res.raise_for_status()
                proxies.update(p.strip()for p in res.text.splitlines()if p.strip())
            except:pass
        proxy_list=list(proxies);random.shuffle(proxy_list)
        for p in proxy_list:self.proxy_queue.put(p)
        return len(proxy_list)
    def find_locket_uid(self,user_input:str)->Optional[str]:
        user_input=user_input.strip();url_to_check=f"https://locket.cam/{user_input}"if not re.match(r'^https?://',user_input)else user_input
        headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36'}
        try:
            response=requests.get(url_to_check,headers=headers,timeout=15,allow_redirects=True);response.raise_for_status()
            final_url=response.url
            if invite_match:=re.search(r'locket\.camera/invites/([a-zA-Z0-9]{28})',final_url):return invite_match.group(1)
            html_content=response.text
            if html_match:=re.search(r'(https?://locket\.camera/invites/[a-zA-Z0-9]{28})',html_content):return re.search(r'([a-zA-Z0-9]{28})',html_match.group(1)).group(1)
        except:return None
        return None
    def validate_license(self,key:str):return validate_license_from_file(key)
    
    async def start_spam_session(self, user_id: int, target: str, custom_name: str, num_threads: int, update_callback: Callable):
        if user_id in self.active_spam_sessions:
            return update_callback(status="error", message="Bạn đã có một phiên spam đang chạy.")
        
        loop = asyncio.get_running_loop()

        if not await loop.run_in_executor(None, self._ensure_dependencies):
            return update_callback(status="error", message="Không thể khởi động: Thiếu token hoặc proxy.")

        target_uid = await loop.run_in_executor(None, self.find_locket_uid, target)
        if not target_uid:
            return update_callback(status="error", message=f"Không thể tìm thấy Locket UID từ `{target}`.")

        stop_event=threading.Event()
        self.active_spam_sessions[user_id]=stop_event
        proxies_count=self.proxy_queue.qsize()
        actual_threads=min(num_threads,proxies_count)
        stats={'accounts':0,'requests':0,'failed':0,'start_time':time.time(),'proxies':proxies_count}
        
        def spam_loop():
            worker_threads=[threading.Thread(target=self._run_worker,args=(target_uid,custom_name,stop_event,stats))for _ in range(actual_threads)]
            for t in worker_threads:t.start()
            if not worker_threads:return update_callback(status="error",message="Không có luồng nào được tạo.")
            
            last_update_time=time.time()
            while not stop_event.is_set()and any(t.is_alive()for t in worker_threads):
                if time.time()-last_update_time>2:
                    stats['proxies']=self.proxy_queue.qsize()
                    update_callback(status="running",stats=stats)
                    last_update_time=time.time()
                time.sleep(0.5)
                
            for t in worker_threads:t.join()
            update_callback(status="stopped",stats=stats)
            if user_id in self.active_spam_sessions:del self.active_spam_sessions[user_id]
            
        threading.Thread(target=spam_loop,daemon=True).start()
        update_callback(status="started",message=f"✅ Đã bắt đầu spam đến `{target_uid}` với **{actual_threads}** luồng.")

    def _run_worker(self,target_uid,custom_name,stop_event,stats):
        while not stop_event.is_set():
            try:
                proxy=self.proxy_queue.get_nowait()
                spammer_instance=Spammer(proxy,target_uid,custom_name)
                status,sent_count=spammer_instance.run_cycle()
                with threading.Lock():
                    if status=="success":stats['accounts']+=1;stats['requests']+=sent_count
                    else:stats['failed']+=1
                self.proxy_queue.put(proxy)
            except queue.Empty:break
            
    def stop_spam_session(self,user_id:int):
        if user_id in self.active_spam_sessions:self.active_spam_sessions[user_id].set();return True
        return False
