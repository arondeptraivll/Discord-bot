# main.py
import os
import asyncio
from bot import app, client, DISCORD_TOKEN

# Gunicorn sẽ chạy đối tượng `app` này.
# Không cần threading ở đây nữa.

@app.before_serving
async def before_serving():
    """Hàm này sẽ chạy TRƯỚC KHI web server bắt đầu nhận request."""
    print("--- [GUNICORN] Web server sắp khởi động, bắt đầu chạy Discord Bot... ---")
    # Tạo một task để chạy bot bất đồng bộ
    # Bot sẽ chạy song song với web server trong cùng một event loop
    loop = asyncio.get_event_loop()
    loop.create_task(client.start(DISCORD_TOKEN))
    print("--- [GUNICORN] Task chạy Discord Bot đã được tạo. ---")

@app.after_serving
async def after_serving():
    """Hàm này sẽ chạy KHI web server tắt."""
    print("--- [GUNICORN] Web server đang tắt, đóng kết nối bot... ---")
    if not client.is_closed():
        await client.close()
    print("--- [GUNICORN] Bot đã được đóng. ---")
