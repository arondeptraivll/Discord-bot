
# main.py - Entrypoint chính để chạy ứng dụng trên Render
import os
from threading import Thread

# --- THAY ĐỔI QUAN TRỌNG ---
# Import 'app' và bot 'client_instance' từ file bot.py, nơi chúng được định nghĩa.
# Đổi tên 'client_instance' thành 'client' để giữ sự tương thích với code bên dưới.
from bot import app, client_instance as client, DISCORD_TOKEN

# Import các thành phần của Gunicorn để chạy web server
from gunicorn.app.base import BaseApplication

def run_bot():
    """Hàm này sẽ được chạy trong một luồng (thread) riêng biệt để khởi động bot."""
    if not DISCORD_TOKEN:
        print("!!! [CRITICAL] Không tìm thấy DISCORD_TOKEN, bot không thể khởi chạy.")
        return
        
    print("--- [BOT THREAD] Đang khởi chạy bot Discord...")
    try:
        # Sử dụng đối tượng 'client' (tức là client_instance) đã được import từ bot.py
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"!!! [CRITICAL BOT ERROR] Bot đã dừng hoạt động với lỗi: {e}")

# Đây là một "hook" của Gunicorn, nó sẽ được gọi khi web server đã sẵn sàng.
# Chúng ta dùng nó để khởi động bot trong một luồng nền.
def when_ready(server):
    print("Gunicorn server is ready. Starting Discord Bot in a background thread...")
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True # Đặt là daemon để luồng tự tắt khi chương trình chính kết thúc
    bot_thread.start()

# Lớp tùy chỉnh để chạy Gunicorn từ code Python thay vì dòng lệnh
class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        # Nạp cấu hình từ dictionary 'options' vào Gunicorn
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

# Đây là khối code được thực thi khi bạn chạy `python main.py` (hoặc khi Render chạy nó).
if __name__ == '__main__':
    # Render sẽ cung cấp biến môi trường 'PORT'
    # Nếu không có, mặc định là 8080 để test trên máy local
    port = int(os.environ.get('PORT', 8080))
    
    # Cấu hình cho server Gunicorn
    options = {
        'bind': f'0.0.0.0:{port}',
        'workers': 1,             # Số lượng tiến trình worker
        'threads': 8,             # Số lượng luồng cho mỗi worker
        'timeout': 0,             # Không có timeout
        'when_ready': when_ready, # "Hook" để chạy bot khi server sẵn sàng
    }

    print("--- [LAUNCH] Starting Gunicorn Web Server ---")
    # Khởi tạo và chạy ứng dụng web của chúng ta
    StandaloneApplication(app, options).run()
