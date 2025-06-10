# main.py - The new main entrypoint for the application
import os
from threading import Thread

# Import a few necessary things from our other files
from keep_alive import app
from bot import client, DISCORD_TOKEN
from gunicorn.app.base import BaseApplication

def run_bot():
    """Runs the discord bot."""
    client.run(DISCORD_TOKEN)

# Gunicorn server hook to start the bot in a background thread
def when_ready(server):
    print("Gunicorn server is ready. Starting Discord Bot...")
    bot_thread = Thread(target=run_bot)
    bot_thread.daemon = True
    bot_thread.start()

# Custom Gunicorn application
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

# Main execution block
if __name__ == '__main__':
    port = os.environ.get('PORT', 8080)
    options = {
        'bind': f'0.0.0.0:{port}',
        'workers': 1,
        'threads': 8,
        'timeout': 0,
        'when_ready': when_ready, # Here is our magic hook!
    }

    print("--- [LAUNCH] Starting Gunicorn Web Server ---")
    StandaloneApplication(app, options).run()
