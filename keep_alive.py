# keep_alive.py (Đơn giản hóa)

from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"
