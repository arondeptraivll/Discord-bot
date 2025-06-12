# aov_keygen.py (Phiên bản Async với aiofiles)
import json
import uuid
import datetime
import asyncio
import aiofiles

KEY_FILE = 'aov_keys.json' 
KEY_PREFIX = 'AOV'
# Sử dụng asyncio.Lock thay vì threading.Lock
_lock = asyncio.Lock()

async def load_keys() -> dict:
    """Tải và sắp xếp dữ liệu keys một cách bất đồng bộ."""
    async with _lock:
        try:
            async with aiofiles.open(KEY_FILE, 'r') as f:
                content = await f.read()
                data = json.loads(content)
                # Sắp xếp vẫn là tác vụ đồng bộ nhưng rất nhanh
                sorted_items = sorted(data.items(), key=lambda item: item[1]['expires_at'], reverse=True)
                return dict(sorted_items)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

async def save_keys(keys_data: dict):
    """Lưu dữ liệu keys vào file JSON một cách bất đồng bộ."""
    async with _lock:
        async with aiofiles.open(KEY_FILE, 'w') as f:
            await f.write(json.dumps(keys_data, indent=4))

def generate_key_string() -> str:
    """Tạo một chuỗi key độc nhất (hàm này không cần async)."""
    part1 = uuid.uuid4().hex[:4].upper()
    part2 = uuid.uuid4().hex[:4].upper()
    return f"{KEY_PREFIX}-{part1}-{part2}"

async def add_key(duration_days: int, created_for_user_id: int, creator_id: int) -> dict:
    """Tạo một key mới và lưu vào file một cách bất đồng bộ."""
    keys_data = await load_keys()
    
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
        "change_attempts": 3,
        "cooldown_until": None
    }
    
    keys_data[new_key_str] = key_info
    await save_keys(keys_data)
    
    return {"key": new_key_str, "expires_at": expiration_date}

async def get_key_info(key: str) -> dict:
    """Lấy thông tin của một key một cách bất đồng bộ."""
    keys = await load_keys()
    return keys.get(key, {})

async def update_key_state(key: str, updates: dict) -> bool:
    """Cập nhật các trường dữ liệu cho một key một cách bất đồng bộ."""
    async with _lock:
        keys_data = await load_keys()
        if key in keys_data:
            keys_data[key].update(updates)
            await save_keys(keys_data)
            return True
        return False
        
async def validate_key(key: str) -> dict:
    """Kiểm tra một key một cách bất đồng bộ."""
    keys_data = await load_keys()
    key_info = keys_data.get(key)

    if not key_info:
        return {"valid": False, "code": "NOT_FOUND"}
    if not key_info.get("is_active", False):
        return {"valid": False, "code": "SUSPENDED"}

    expiry_dt = datetime.datetime.fromisoformat(key_info["expires_at"].replace("Z", "+00:00"))
    if expiry_dt < datetime.datetime.now(datetime.timezone.utc):
        return {"valid": False, "code": "EXPIRED"}

    return {"valid": True, "code": "VALID", "key_info": key_info}

async def delete_key(key_to_delete: str) -> bool:
    """Vô hiệu hóa một key một cách bất đồng bộ."""
    return await update_key_state(key_to_delete, {"is_active": False})
