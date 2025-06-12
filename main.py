# main.py (Phiên bản Sửa Lỗi và Ổn Định)
import os
from threading import Thread
from flask import Flask

# Import app và client từ bot.py
# Đảm bảo DISCORD_TOKEN cũng được import để kiểm tra
from bot import app, client, DISCORD_TOKEN

def run_bot():
    """Hàm chạy discord bot một cách an toàn."""
    if DISCORD_TOKEN:
        print("--- [THREAD] Bắt đầu luồng Discord Bot... ---")
        client.run(DISCORD_TOKEN)
    else:
        print("--- [CRITICAL] Không tìm thấy DISCORD_TOKEN, luồng bot không chạy. ---")

def run_web_server():
    """Hàm chạy Flask web server để giữ cho Render luôn 'sống'."""
    # Render sẽ tự động gán cổng qua biến môi trường PORT
    port = int(os.environ.get('PORT', 8080))
    print(f"--- [THREAD] Bắt đầu luồng Web Server trên cổng {port}... ---")
    app.run(host='0.0.0.0', port=port)

# Main execution
if __name__ == '__main__':
    print("--- [LAUNCH] Khởi chạy ứng dụng đa luồng... ---")
    
    # Tạo một luồng cho web server (để trả lời health check của Render)
    web_thread = Thread(target=run_web_server)
    web_thread.daemon = True  # Tự động tắt khi chương trình chính kết thúc
    
    # Tạo luồng chính cho Discord bot
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True

    # Khởi chạy cả hai luồng
    web_thread.start()
    bot_thread.start()

    # Giữ cho chương trình chính chạy mãi mãi
    # Nếu không có dòng này, chương trình sẽ kết thúc và cả 2 luồng cũng sẽ chết
    try:
        web_thread.join()
        bot_thread.join()
    except KeyboardInterrupt:
        print("--- [SHUTDOWN] Đang tắt ứng dụng... ---")
