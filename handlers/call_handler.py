"""
Bejövő Telegram hívások kezelése.

Stratégia:
  1. Telethon észleli a bejövő hívást (PhoneCallRequested)
  2. Teljes képernyős overlay jelenik meg a hívó nevével
  3. Az app automatikusan megnyitja / előre hozza a Telegram Desktop-ot
  4. Megpróbálja automatikusan elfogadni a hívást a Telegram Desktop ablakban
     (zöld Elfogad gomb keresésével képernyőn, majd kattintással)
  5. Ha az auto-elfogadás nem sikerül, a felhasználó a nagy FELVENNI
     gombra kattinthat az overlayen
"""

import asyncio
import subprocess
import time
import threading
from pathlib import Path

from telethon import TelegramClient
from telethon.tl.types import (
    UpdatePhoneCall,
    PhoneCallRequested,
    PhoneCallDiscarded,
)

try:
    import win32gui
    import win32con
    import win32api
    WIN32_AVAILABLE = True
except ImportError:
    WIN32_AVAILABLE = False
    print("[CallHandler] pywin32 nem elérhető – Windows automatizálás korlátozott")

try:
    import pyautogui
    from PIL import ImageGrab
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

from ui.call_overlay import CallOverlay
from config import TELEGRAM_PATHS, AUTO_ANSWER_DELAY


class CallHandler:
    def __init__(self, client: TelegramClient):
        self.client = client
        self.overlay = CallOverlay()
        self._active_call_id = None

    async def handle(self, event: UpdatePhoneCall):
        call = event.phone_call

        if isinstance(call, PhoneCallRequested):
            await self._on_incoming_call(call)

        elif isinstance(call, PhoneCallDiscarded):
            if self._active_call_id == call.id:
                self._active_call_id = None
                self.overlay.close()
                print("[CallHandler] Hívás megszakadt vagy letéve.")

    async def _on_incoming_call(self, call: PhoneCallRequested):
        self._active_call_id = call.id

        # Hívó nevének lekérése
        caller_name = await self._get_caller_name(call.admin_id)
        print(f"[CallHandler] Bejövő hívás: {caller_name} (id={call.admin_id})")

        # Overlay megjelenítése + auto-elfogadás callback
        self.overlay.show(
            caller_name=caller_name,
            accept_callback=self._accept_in_telegram_desktop,
        )

        # Automatikus elfogadás késleltetéssel
        asyncio.get_event_loop().call_later(
            AUTO_ANSWER_DELAY,
            lambda: threading.Thread(
                target=self._accept_in_telegram_desktop, daemon=True
            ).start(),
        )

    async def _get_caller_name(self, user_id: int) -> str:
        try:
            entity = await self.client.get_entity(user_id)
            parts = [entity.first_name or "", entity.last_name or ""]
            name = " ".join(p for p in parts if p).strip()
            return name or f"Ismeretlen ({user_id})"
        except Exception:
            return f"Ismeretlen ({user_id})"

    # ------------------------------------------------------------------
    # Auto-elfogadás Telegram Desktop-on keresztül
    # ------------------------------------------------------------------

    def _accept_in_telegram_desktop(self):
        """
        Megpróbálja automatikusan elfogadni a hívást a Telegram Desktop-ban.
        1. Biztosítja, hogy a Telegram Desktop fut
        2. Előre hozza az ablakot
        3. Megkeresi és rákattint a zöld elfogad gombra
        """
        self._ensure_telegram_running()
        time.sleep(1.5)

        hwnd = self._find_telegram_window()
        if hwnd and WIN32_AVAILABLE:
            self._bring_to_front(hwnd)
            time.sleep(0.5)

        success = False
        if PYAUTOGUI_AVAILABLE and hwnd and WIN32_AVAILABLE:
            success = self._click_green_accept_button(hwnd)

        if success:
            print("[CallHandler] Auto-elfogadás sikerült!")
            self.overlay.close()
        else:
            print("[CallHandler] Auto-elfogadás nem sikerült – overlay megmarad")

    def _ensure_telegram_running(self):
        """Elindítja a Telegram Desktop-ot, ha nem fut."""
        hwnd = self._find_telegram_window()
        if hwnd:
            return  # már fut

        for path in TELEGRAM_PATHS:
            if path.exists():
                print(f"[CallHandler] Telegram Desktop indítása: {path}")
                subprocess.Popen([str(path)])
                time.sleep(4)
                return

        print("[CallHandler] Telegram Desktop nem található – kézzel kell indítani")

    def _find_telegram_window(self):
        """Megkeresi a Telegram Desktop ablak handle-jét."""
        if not WIN32_AVAILABLE:
            return None

        found = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            title = win32gui.GetWindowText(hwnd)
            if "Telegram" in title:
                found.append(hwnd)
            return True

        win32gui.EnumWindows(callback, None)
        return found[0] if found else None

    def _bring_to_front(self, hwnd):
        """Előre hozza a Telegram Desktop ablakot."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            # SetForegroundWindow megköveteli, hogy a hívó ablak is fókuszban legyen
            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)          # Alt lenyomás
            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
            win32gui.SetForegroundWindow(hwnd)
        except Exception as e:
            print(f"[CallHandler] Ablak előre hozása sikertelen: {e}")

    def _click_green_accept_button(self, hwnd) -> bool:
        """
        Megkeresi a zöld "Elfogad" gombot a Telegram ablakban
        RGB pixel-szín alapján, majd rákattint.
        Visszatérési érték: True ha sikerült kattintani.
        """
        try:
            rect = win32gui.GetWindowRect(hwnd)
            wx, wy, ww, wh = rect[0], rect[1], rect[2] - rect[0], rect[3] - rect[1]

            # Képernyőkép az ablakról
            screenshot = ImageGrab.grab(bbox=(wx, wy, wx + ww, wy + wh))

            # Zöld pixelek keresése (Telegram zöld: ~#4dcd5e vagy #00d26a)
            green_cluster = []
            width, height = screenshot.size

            for y in range(0, height, 3):
                for x in range(0, width, 3):
                    pixel = screenshot.getpixel((x, y))
                    r, g, b = pixel[0], pixel[1], pixel[2]
                    # Zöld: magas G, alacsony R és B
                    if g > 140 and r < 120 and b < 120:
                        green_cluster.append((x, y))

            if len(green_cluster) < 20:
                print("[CallHandler] Zöld gomb nem található a képernyőn")
                return False

            # Kattintás a klaszter közepére
            avg_x = sum(p[0] for p in green_cluster) // len(green_cluster)
            avg_y = sum(p[1] for p in green_cluster) // len(green_cluster)

            screen_x = wx + avg_x
            screen_y = wy + avg_y

            print(f"[CallHandler] Zöld gomb megtalálva: ({screen_x}, {screen_y}) – kattintás")
            pyautogui.click(screen_x, screen_y)
            return True

        except Exception as e:
            print(f"[CallHandler] Gombkeresés hiba: {e}")
            return False
