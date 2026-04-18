"""
Entry point for Render deployment.
Runs the poller in a background thread and exposes a /health endpoint
so Render (and UptimeRobot) can keep the service alive.
"""
import threading
import logging
from flask import Flask
from poller import main as run_poller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

app = Flask(__name__)


@app.route("/")
@app.route("/health")
def health():
    return "OK", 200


def start_poller():
    try:
        run_poller()
    except Exception as e:
        logging.error("Poller crashed: %s", e)


thread = threading.Thread(target=start_poller, daemon=True)
thread.start()
