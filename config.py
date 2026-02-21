import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# --- Telegram API ---
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH", "")
PHONE = os.getenv("PHONE", "")

# --- Telegram Desktop útvonal ---
_username = os.getenv("USERNAME", "User")
TELEGRAM_PATHS = [
    Path(os.getenv("TELEGRAM_PATH", "")) if os.getenv("TELEGRAM_PATH") else None,
    Path(f"C:/Program Files/Telegram Desktop/Telegram.exe"),
    Path(os.environ.get("APPDATA", "")) / "Telegram Desktop" / "Telegram.exe",
    Path(os.environ.get("LOCALAPPDATA", "")) / "Telegram Desktop" / "Telegram.exe",
]
TELEGRAM_PATHS = [p for p in TELEGRAM_PATHS if p and p.exists()]

# --- Megjelenítés ---
# Hívás overlay
CALL_BG_COLOR = "#1a1a2e"
CALL_ACCENT_COLOR = "#00d26a"
CALL_TEXT_COLOR = "#ffffff"
CALL_FONT_SIZE = 52

# Üzenet overlay
MSG_BG_COLOR = "#1e3a5f"
MSG_TEXT_COLOR = "#ffffff"
MSG_FONT_SIZE = 22
MSG_DISPLAY_SECONDS = 12

# Automatikus felvétel késleltetése másodpercben
AUTO_ANSWER_DELAY = 2.0
