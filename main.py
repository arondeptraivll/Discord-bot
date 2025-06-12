# main.py (Threading ổn định)
import os
import time
from threading import Thread
from bot import app, client, DISCORD_TOKEN

def run_bot():
    """Hàm chạy Discord bot."""
    if not DISCORD_TOKEN:
        print("!!! [CRITICAL] Không tìm thấy DISCORD_TOKEN, bot không chạy.")
        return
    
    try:
        print("--- [THREAD] Luồng Discord Bot đang khởi chạy... ---")
        client.run(DISCORD_TOKEN)
    except Exception as e:
        print(f"!!! [CRITICAL] Lỗi nghiêm trọng trong luồng bot: {e}")

def run_web_server():
    """Hàm chạy Flask web server."""
    port = int(os.environ.get('PORT', 8080))
    print(f"--- [THREAD] Luồng Web Server đang khởi chạy trên cổng {port}... ---")
    # Sử dụng waitress thay cho server mặc định của Flask để ổn định hơn
    from waitress import serve
    serve(app, host='0.0.0.0', port=port)

if __name__ == '__main__':
    print("--- [LAUNCH] Khởi chạy ứng dụng đa luồng... ---")

    web_thread = Thread(target=run_web_server)
    bot_thread = Thread(target=run_bot)
    
    # Ưu tiên khởi động luồng web trước để Render phát hiện cổng
    web_thread.start()
    
    # Chờ một chút để web server chắc chắn đã khởi động
    print("--- [LAUNCH] Chờ 5 giây cho web server ổn định... ---")
    time.sleep(5)
    
    # Sau đó mới khởi động luồng bot
    bot_thread.start()
    
    web_thread.join()
    bot_thread.join()
