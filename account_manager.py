--- START OF FILE account_manager.py ---

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

def get_random_account(exclude_username: Optional[str] = None) -> Optional[Dict[str, str]]:
    """
    Lấy một tài khoản ngẫu nhiên từ cache.
    Có thể loại trừ một username cụ thể để không bị trùng lặp.
    """
    if not _accounts_cache:
        # Nếu cache rỗng (có thể do lỗi khi khởi động), thử nạp lại một lần nữa
        print("!!! [WARNING] Cache tài khoản đang rỗng. Thử nạp lại đồng bộ...")
        load_accounts_into_cache()
        if not _accounts_cache:
             return None # Vẫn rỗng thì trả về None
    
    # Lọc ra danh sách các tài khoản hợp lệ (không phải là tài khoản cần loại trừ)
    available_accounts = [acc for acc in _accounts_cache if acc['username'] != exclude_username]

    if not available_accounts:
        # Xảy ra nếu tất cả tài khoản đều bị loại trừ hoặc kho chỉ có 1 tài khoản đó
        return None
    
    try:
        return random.choice(available_accounts)
    except IndexError:
        # Trường hợp dự phòng nếu list rỗng (dù đã kiểm tra)
        return None
