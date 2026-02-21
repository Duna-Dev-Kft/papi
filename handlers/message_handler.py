"""
Bejövő Telegram üzenetek kezelése.

Minden bejövő üzenet megjelenik a képernyő jobb felső sarkában,
egy nagy, böngésző felett úszó értesítő ablakban.
Kattintásra megnyitja / előre hozza a Telegram Desktop-ot.
"""

import time
import threading
import subprocess
from pathlib import Path

from telethon import events
from telethon.tl.types import User

try:
    import win32gui
    import win32con
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False

from ui.message_overlay import MessageOverlay
from config import TELEGRAM_PATHS


class MessageHandler:
    def __init__(self, client):
        self.client = client
        self.overlay = MessageOverlay()

    async def handle(self, event: events.NewMessage.Event):
        # Saját üzenetek kihagyása
        if event.out:
            return

        # Bot üzenetek kihagyása (opcionális)
        sender = await event.get_sender()
        if sender and getattr(sender, "bot", False):
            return

        sender_name = self._get_sender_name(sender)
        message_text = event.message.message or ""

        # Média leírása, ha nincs szöveg
        if not message_text and event.message.media:
            message_text = self._describe_media(event.message.media)

        if not message_text:
            return

        print(f"[MessageHandler] Új üzenet: {sender_name}: {message_text[:50]}")

        # Chat ID az overlay kattintás callbackhoz
        chat_id = event.chat_id

        self.overlay.show(
            sender_name=sender_name,
            message_text=message_text,
            open_callback=lambda: self._open_telegram_to_chat(chat_id),
        )

    def _get_sender_name(self, sender) -> str:
        if sender is None:
            return "Ismeretlen"
        if isinstance(sender, User):
            parts = [sender.first_name or "", sender.last_name or ""]
            name = " ".join(p for p in parts if p).strip()
            return name or sender.username or "Ismeretlen"
        return getattr(sender, "title", None) or "Ismeretlen"

    def _describe_media(self, media) -> str:
        class_name = type(media).__name__.lower()
        if "photo" in class_name:
            return "📷 Kép"
        if "video" in class_name or "document" in class_name:
            return "🎥 Videó / fájl"
        if "voice" in class_name or "audio" in class_name:
            return "🎵 Hangüzenet"
        if "sticker" in class_name:
            return "😊 Matrica"
        return "📎 Melléklet"

    def _open_telegram_to_chat(self, chat_id):
        """Megnyitja a Telegram Desktop-ot és előre hozza."""
        hwnd = self._find_telegram_window()

        if not hwnd:
            # Telegram Desktop indítása
            for path in TELEGRAM_PATHS:
                if path.exists():
                    subprocess.Popen([str(path)])
                    time.sleep(3)
                    hwnd = self._find_telegram_window()
                    break

        if hwnd and WIN32_AVAILABLE:
            self._bring_to_front(hwnd)

    def _find_telegram_window(self):
        if not WIN32_AVAILABLE:
            return None
        found = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            if "Telegram" in win32gui.GetWindowText(hwnd):
                found.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        return found[0] if found else None

    def _bring_to_front(self, hwnd):
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"[MessageHandler] Ablak előre hozása sikertelen: {e}")
