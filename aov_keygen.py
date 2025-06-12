# aov_keygen.py
import json
import uuid
import datetime
from threading import Lock
from typing import Dict, Any

# Sử dụng file và prefix riêng biệt
KEY_FILE = 'aov_keys.json' 
KEY_PREFIX = 'AOV'
_lock = Lock()

def load_keys() -> dict:
    """Tải và sắp xếp dữ liệu keys từ aov_keys.json."""
    with _lock:
        try:
            with open(KEY_FILE, 'r') as f:
                data = json.load(f)
                sorted_items = sorted(data.items(), key=lambda item: item[1]['expires_at'], reverse=True)
                return dict(sorted_items)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def save_keys(keys_data: dict):
    """Lưu dữ liệu keys vào file JSON một cách an toàn."""
    with _lock:
        with open(KEY_FILE, 'w') as f:
            json.dump(keys_data, f, indent=4)

def generate_key_string() -> str:
    """Tạo một chuỗi key độc nhất."""
    part1 = uuid.uuid4().hex[:4].upper()
    part2 = uuid.uuid4().hex[:4].upper()
    return f"{KEY_PREFIX}-{part1}-{part2}"

def add_key(duration_days: int, created_for_user_id: int, creator_id: int) -> dict:
    """Tạo một key mới và lưu vào file."""
    keys_data = load_keys()
    
    new_key_str = generate_key_string()
    while new_key_str in keys_data:
        new_key_str = generate_key_string()

    now = datetime.datetime.now(datetime.timezone.utc)
    expiration_date = now + datetime.timedelta(days=duration_days)

    key_info = {
        "created_at": now.isoformat(),
        "expires_at": expiration_date.isoformat(),
        "duration_days": duration_days,
        "is_active": True,
        "created_by": str(creator_id),
        "user_id": str(created_for_user_id),
        # === NEW: Thêm trạng thái đổi tài khoản ===
        "change_attempts": 3,
        "cooldown_until": None
    }
    
    keys_data[new_key_str] = key_info
    save_keys(keys_data)
    
    return {"key": new_key_str, "expires_at": expiration_date}

def get_key_info(key: str) -> Dict[str, Any]:
    """Lấy toàn bộ thông tin của một key."""
    return load_keys().get(key, {})

def update_key_state(key: str, updates: Dict[str, Any]) -> bool:
    """Cập nhật các trường dữ liệu cho một key cụ thể."""
    with _lock:
        keys_data = load_keys()
        if key in keys_data:
            keys_data[key].update(updates)
            save_keys(keys_data)
            return True
        return False
        
def validate_key(key: str) -> dict:
    """Kiểm tra một key từ file keys.json."""
    keys_data = load_keys()
    key_info = keys_data.get(key)

    if not key_info:
        return {"valid": False, "code": "NOT_FOUND"}

    if not key_info.get("is_active", False):
        return {"valid": False, "code": "SUSPENDED"}

    # Không vô hiệu hóa key hết hạn ở đây nữa, vì nó có thể còn hiệu lực đổi tài khoản
    expiry_dt = datetime.datetime.fromisoformat(key_info["expires_at"])
    if expiry_dt < datetime.datetime.now(datetime.timezone.utc):
        # Chỉ trả về hết hạn, không tự động lưu is_active = False nữa
        return {"valid": False, "code": "EXPIRED"}

    return {"valid": True, "code": "VALID", "key_info": key_info}

def delete_key(key_to_delete: str) -> bool:
    """Vô hiệu hóa một key bằng cách đặt is_active = False."""
    return update_key_state(key_to_delete, {"is_active": False})
