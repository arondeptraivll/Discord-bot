# account_manager.py
import re
import random
from typing import Optional, Dict

ACCOUNT_FILE = 'account_aov.txt'

def parse_account_line(line: str) -> Optional[Dict[str, str]]:
    """Phân tích một dòng trong file tài khoản thành username và password."""
    # Sử dụng regex để tìm chính xác tài khoản và mật khẩu
    match = re.search(r"Tài khoản:\s*(.*?)\s*🔑 Mật khẩu:\s*(.*)", line)
    if match:
        username = match.group(1).strip()
        password = match.group(2).strip()
        return {"username": username, "password": password}
    return None

def get_random_account() -> Optional[Dict[str, str]]:
    """
    Đọc file account_aov.txt, phân tích cú pháp các dòng,
    và trả về một tài khoản ngẫu nhiên.
    """
    try:
        with open(ACCOUNT_FILE, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Lọc ra những dòng hợp lệ và phân tích chúng
        accounts = []
        for line in lines:
            if line.strip(): # Bỏ qua các dòng trống
                parsed = parse_account_line(line)
                if parsed:
                    accounts.append(parsed)

        if not accounts:
            return None # Không có tài khoản nào hợp lệ trong file
        
        # Chọn ngẫu nhiên một tài khoản từ danh sách
        return random.choice(accounts)

    except FileNotFoundError:
        print(f"!!! [ERROR] Không tìm thấy file dữ liệu tài khoản: {ACCOUNT_FILE}")
        return None
    except Exception as e:
        print(f"!!! [ERROR] Lỗi khi đọc file tài khoản: {e}")
        return None
