# cooldown_manager.py
import json
import time
from threading import Lock

STATE_FILE = 'aov_change_cooldowns.json'
_lock = Lock()
CHANGE_LIMIT = 3
WINDOW_SECONDS = 3600  # 1 tiếng

def _load_state() -> dict:
    """Tải trạng thái từ file JSON."""
    with _lock:
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

def _save_state(state: dict):
    """Lưu trạng thái vào file JSON."""
    with _lock:
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)

def check_and_use_change(user_id: int) -> dict:
    """
    Kiểm tra xem người dùng có được phép đổi tài khoản không và cập nhật trạng thái.
    
    Returns:
        dict: Một dictionary chứa thông tin về kết quả.
              - {"allowed": True} nếu được phép.
              - {"allowed": False, "reason": "COOLDOWN", "retry_after": int} nếu đang trong thời gian chờ.
    """
    user_id_str = str(user_id)
    state = _load_state()
    user_data = state.get(user_id_str, {})
    
    current_time = int(time.time())
    
    window_start_time = user_data.get("window_start_time", 0)
    change_count = user_data.get("change_count", 0)
    
    # Kiểm tra xem cửa sổ 1 tiếng có còn hiệu lực không
    if current_time - window_start_time < WINDOW_SECONDS:
        # Nếu vẫn trong cửa sổ, kiểm tra số lần đổi
        if change_count >= CHANGE_LIMIT:
            retry_after = WINDOW_SECONDS - (current_time - window_start_time)
            return {"allowed": False, "reason": "COOLDOWN", "retry_after": retry_after}
        else:
            # Vẫn được đổi, tăng số lần và lưu lại
            user_data["change_count"] += 1
            state[user_id_str] = user_data
            _save_state(state)
            return {"allowed": True}
    else:
        # Cửa sổ đã hết hạn hoặc đây là lần đổi đầu tiên
        # Reset lại cửa sổ
        new_data = {
            "window_start_time": current_time,
            "change_count": 1
        }
        state[user_id_str] = new_data
        _save_state(state)
        return {"allowed": True}
