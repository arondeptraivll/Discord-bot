# keep_alive.py (Phiên bản Gunicorn)
from flask import Flask
from threading import Thread
import os
from gunicorn.app.base import BaseApplication

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive and running with Gunicorn!"

class StandaloneApplication(BaseApplication):
    def __init__(self, app, options=None):
        self.options = options or {}
        self.application = app
        super().__init__()

    def load_config(self):
        config = {key: value for key, value in self.options.items()
                  if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        return self.application

def run():
    port = os.environ.get('PORT', 8080)
    options = {
        'bind': f'0.0.0.0:{port}',
        'workers': 1,
        'threads': 8,
        'timeout': 0,
    }
    StandaloneApplication(app, options).run()

def keep_alive():
    """Khởi chạy web server Gunicorn trong một luồng riêng."""
    server_thread = Thread(target=run)
    server_thread.daemon = True
    server_thread.start()
