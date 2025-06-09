# keep_alive.py

from flask import Flask
from threading import Thread
import os

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"

def run():
    # Render cung cấp port qua biến môi trường 'PORT', chúng ta phải dùng nó.
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    """Khởi chạy web server trong một luồng riêng."""
    server_thread = Thread(target=run)
    server_thread.start()