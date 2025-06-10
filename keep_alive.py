# keep_alive.py (Simplified for Gunicorn main process)
from flask import Flask

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running!"
