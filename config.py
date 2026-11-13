"""Settings. Secrets come from environment variables, never from Git."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.environ.get("SVIAMS_DB", os.path.join(BASE_DIR, "instance", "autogate.db"))

# Fake plate/card readings until camera.py, nfc.py and anpr.py are connected (Step 7).
USE_MOCK = os.environ.get("SVIAMS_USE_MOCK", "1") == "1"

CARD_TIMEOUT_SECONDS = 10
UTC_OFFSET_HOURS = 1  # Nigeria (WAT). Every stored timestamp uses this one zone.

# Dev default is localhost only. On the Pi, set SVIAMS_HOST=0.0.0.0 so staff can reach /admin.
HOST = os.environ.get("SVIAMS_HOST", "127.0.0.1")
PORT = int(os.environ.get("SVIAMS_PORT", "5000"))

# If unset, a random key is made at start-up, so admin logins reset whenever the app restarts.
SECRET_KEY = os.environ.get("SVIAMS_SECRET_KEY") or os.urandom(32).hex()
