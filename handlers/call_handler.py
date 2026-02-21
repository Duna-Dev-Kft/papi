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

try:
    import uiautomation as auto
    UIA_AVAILABLE = True
except ImportError:
    UIA_AVAILABLE = False
    print("[CallHandler] uiautomation nem elérhető – UIA-alapú kattintás kihagyva")

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

        # 1. kísérlet: Windows UI Automation (API-alapú, megbízható)
        if UIA_AVAILABLE and hwnd:
            print("[CallHandler] UIA-alapú kattintás kísérlet...")
            success = self._click_via_uia(hwnd)

        # 2. kísérlet: pixel-alapú fallback
        if not success and PYAUTOGUI_AVAILABLE and hwnd and WIN32_AVAILABLE:
            print("[CallHandler] Pixel-alapú kattintás kísérlet...")
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

    def _click_via_uia(self, hwnd) -> bool:
        """
        Windows UI Automation alapú kattintás.
        Az accessibility tree-n keresztül keresi a hívás elfogadó gombot
        – nem pixel, hanem vezérlő neve/szerepe alapján.

        Telegram Desktop Qt-alapú, a gomb neve angolul vagy lokalizáltan
        jelenhet meg. Ha nem találja névvel, végigmegy az összes Button-on
        és amelyik a hívásjelző területen van (ablak teteje), arra kattint.
        """
        if not UIA_AVAILABLE:
            return False
        try:
            # Az ablak accessibility objektuma hwnd alapján
            ctrl = auto.ControlFromHandle(hwnd)
            if ctrl is None:
                return False

            # Ismert gombnevek (Telegram különböző verziók / nyelvek)
            candidate_names = [
                "Accept call", "Answer call", "Answer", "Accept",
                "Fogadás", "Elfogad", "Felvesz",
                "accept_call", "answer",
            ]

            for name in candidate_names:
                try:
                    btn = ctrl.ButtonControl(searchDepth=8, Name=name)
                    if btn.Exists(maxSearchSeconds=0.3):
                        print(f"[UIA] Gomb megtalálva névvel: '{name}'")
                        btn.Click()
                        return True
                except Exception:
                    pass

            # Névvel nem sikerült – végigmegyünk az összes gombon,
            # és amelyik az ablak felső részén van (hívásjelző sáv), arra kattintunk
            print("[UIA] Névvel nem találtam, keresem pozíció alapján...")

            window_rect = win32gui.GetWindowRect(hwnd)
            win_top = window_rect[1]
            call_bar_bottom = win_top + 200  # hívásjelző sáv max 200px magas

            all_buttons = ctrl.GetChildren()
            self._collect_buttons(ctrl, all_buttons, depth=6)

            for btn in all_buttons:
                try:
                    if btn.ControlType != auto.ControlType.ButtonControl:
                        continue
                    r = btn.BoundingRectangle
                    # A gomb a képernyő felső részén van (hívásjelző sávban)
                    if r.top < call_bar_bottom and r.width() > 10 and r.height() > 10:
                        print(
                            f"[UIA] Gomb pozíció alapján: '{btn.Name}' "
                            f"@ ({r.left},{r.top})"
                        )
                        btn.Click()
                        return True
                except Exception:
                    pass

            print("[UIA] Nem találtam elfogadó gombot az accessibility tree-ben")
            return False

        except Exception as e:
            print(f"[UIA] Hiba: {e}")
            return False

    def _collect_buttons(self, ctrl, result: list, depth: int):
        """Rekurzívan összegyűjti az összes Button vezérlőt."""
        if depth <= 0:
            return
        try:
            for child in ctrl.GetChildren():
                result.append(child)
                self._collect_buttons(child, result, depth - 1)
        except Exception:
            pass

    def _click_green_accept_button(self, hwnd) -> bool:
        """
        Megkeresi a zöld "Elfogad" gombot a Telegram hívásjelző sávban.

        A Telegram Desktop hívásjelző sávja a bal panel TETEJÉN jelenik meg
        (kb. felső 160px, bal 420px). Az online jelzők (kis zöld pontok) a
        névsor többi részén találhatók – azokat szűrjük ki azzal, hogy csak
        a felső sávban keresünk, és koncentrált klasztert keresünk.
        """
        try:
            rect = win32gui.GetWindowRect(hwnd)
            wx, wy = rect[0], rect[1]
            ww = rect[2] - rect[0]
            wh = rect[3] - rect[1]

            # Csak a bal panel felső részét vizsgáljuk (hívásjelző sáv területe)
            search_w = min(460, ww // 2)
            search_h = min(180, wh // 4)

            screenshot = ImageGrab.grab(
                bbox=(wx, wy, wx + search_w, wy + search_h)
            )
            width, height = screenshot.size

            # Telegram elfogad gomb zöldje: #4dcd5e, #5cb85c, #00c853 stb.
            # R < 120, G > 160, B < 130
            green_pixels = []
            for y in range(0, height, 2):
                for x in range(0, width, 2):
                    r, g, b = screenshot.getpixel((x, y))[:3]
                    if g > 160 and r < 120 and b < 130:
                        green_pixels.append((x, y))

            print(f"[CallHandler] Zöld pixelek a hívássávban: {len(green_pixels)}")

            if len(green_pixels) < 12:
                print("[CallHandler] Zöld gomb nem található a hívássávban")
                return False

            # Legsűrűbb klaszter keresése (a gomb egy koncentrált folt,
            # az online jelzők szétszórtak)
            center = self._find_dense_cluster(green_pixels, radius=18, min_count=10)
            if not center:
                print("[CallHandler] Nem találtam koncentrált zöld klasztert")
                return False

            screen_x = wx + center[0]
            screen_y = wy + center[1]

            print(f"[CallHandler] Zöld gomb: ({screen_x}, {screen_y}) – kattintás")
            pyautogui.click(screen_x, screen_y)
            return True

        except Exception as e:
            print(f"[CallHandler] Gombkeresés hiba: {e}")
            return False

    def _find_dense_cluster(self, pixels, radius=18, min_count=10):
        """
        Megkeresi a legsűrűbb pixel-klasztert.
        Visszaadja a klaszter középpontját (x, y), vagy None-t.
        """
        if not pixels:
            return None

        best_center = None
        best_count = 0

        # Mintavételezés: minden 3. pixel lehet klaszterközpont
        for px, py in pixels[::3]:
            nearby = [
                (qx, qy) for qx, qy in pixels
                if abs(qx - px) <= radius and abs(qy - py) <= radius
            ]
            if len(nearby) > best_count:
                best_count = len(nearby)
                best_center = (
                    sum(q[0] for q in nearby) // len(nearby),
                    sum(q[1] for q in nearby) // len(nearby),
                )

        if best_count < min_count:
            return None
        return best_center
