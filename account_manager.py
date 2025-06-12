# account_manager.py
import re
import random
from typing import Optional, Dict, List

ACCOUNT_FILE = 'account_aov.txt'
_accounts_cache: List[Dict[str, str]] = [] # Biến cache toàn cục

def _parse_account_line(line: str) -> Optional[Dict[str, str]]:
    """Phân tích một dòng trong file tài khoản thành username và password."""
    match = re.search(r"Tài khoản:\s*(.*?)\s*🔑 Mật khẩu:\s*(.*)", line)
    if match:
        username = match.group(1).strip()
        password = match.group(2).strip()
        return {"username": username, "password": password}
    return None

def load_accounts_into_cache():
    """
    Đọc file và nạp tài khoản vào cache. 
    Hàm này được thiết kế để chạy một lần khi bot khởi động.
    """
    global _accounts_cache
    if _accounts_cache: # Nếu đã có cache thì không chạy lại
        print("--- [CACHE] Cache tài khoản đã tồn tại. Bỏ qua việc nạp lại. ---")
        return

    try:
        with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        parsed_accounts = []
        for line in lines:
            if parsed := _parse_account_line(line):
                parsed_accounts.append(parsed)
        
        _accounts_cache = parsed_accounts
        print(f"--- [CACHE] Đã nạp thành công {_accounts_cache.__len__()} tài khoản AOV vào cache. ---")

    except FileNotFoundError:
        print(f"!!! [ERROR] Không tìm thấy file dữ liệu tài khoản: {ACCOUNT_FILE}")
        _accounts_cache = [] # Đảm bảo cache là một list rỗng
    except Exception as e:
        print(f"!!! [ERROR] Lỗi khi nạp cache tài khoản: {e}")
        _accounts_cache = [] # Đảm bảo cache là một list rỗng

def get_random_account() -> Optional[Dict[str, str]]:
    """
    Lấy một tài khoản ngẫu nhiên từ cache trong bộ nhớ.
    Đây là hàm non-blocking, cực nhanh.
    """
    if not _accounts_cache:
        # Nếu cache rỗng (có thể do lỗi khi khởi động), thử nạp lại một lần nữa
        # Lưu ý: Đây là hành động đồng bộ (blocking), chỉ nên xảy ra trong trường hợp khẩn cấp
        print("!!! [WARNING] Cache tài khoản đang rỗng. Thử nạp lại đồng bộ...")
        load_accounts_into_cache()
        if not _accounts_cache:
             return None # Vẫn rỗng thì trả về None
    
    try:
        return random.choice(_accounts_cache)
    except IndexError:
        # Xảy ra nếu _accounts_cache là list rỗng
        return None
