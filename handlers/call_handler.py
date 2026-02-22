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
import ctypes
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
    import win32process
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

        FONTOS: Az overlay-t ELŐSZÖR bezárjuk, különben a fullscreen topmost
        ablak takarja a Telegram hívás popup-ját – sem a pixelkereső, sem az
        UIA nem látja a gombot, amíg az overlay előttük van.
        """
        # COM inicializálás – szálban kötelező UIA előtt
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass

        # 1. Overlay bezárása – Telegram hívás UI láthatóvá válik
        self.overlay.close()
        time.sleep(0.6)   # hagyjuk hogy az ablak teljesen eltűnjön

        self._ensure_telegram_running()
        time.sleep(1.0)

        all_hwnds = self._find_all_telegram_windows()
        if not all_hwnds:
            print("[CallHandler] Telegram ablak nem található")
            return

        print(f"[CallHandler] {len(all_hwnds)} Telegram ablak találva")
        for hwnd in all_hwnds:
            title = win32gui.GetWindowText(hwnd) if WIN32_AVAILABLE else "?"
            rect = win32gui.GetWindowRect(hwnd) if WIN32_AVAILABLE else (0, 0, 0, 0)
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            print(f"  hwnd={hwnd} title='{title}' méret={w}x{h}")

        success = False

        for hwnd in all_hwnds:
            if WIN32_AVAILABLE:
                self._bring_to_front(hwnd)
                time.sleep(0.4)

            # UIA kísérlet
            if UIA_AVAILABLE:
                if self._click_via_uia(hwnd):
                    success = True
                    break

            # Pixel fallback
            if not success and PYAUTOGUI_AVAILABLE and WIN32_AVAILABLE:
                if self._click_green_accept_button(hwnd):
                    success = True
                    break

        if success:
            print("[CallHandler] Auto-elfogadás sikerült!")
        else:
            # Legalább a legkisebb ablakot hozzuk előre (valószínűleg a hívás popup)
            # A legkisebb ablak általában a hívás értesítő, nem a fő ablak
            if WIN32_AVAILABLE and all_hwnds:
                call_hwnd = self._pick_call_window(all_hwnds)
                self._bring_to_front(call_hwnd)
            print("[CallHandler] Auto-elfogadás nem sikerült – Telegram előtérben")

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
        """Visszaadja az első Telegram ablakot (kompatibilitáshoz megmarad)."""
        windows = self._find_all_telegram_windows()
        return windows[0] if windows else None

    def _find_all_telegram_windows(self):
        """
        Megkeresi az összes Telegram.exe-hez tartozó látható ablakot.
        PID alapján keres, így a hívás popup ablakot is megtalálja,
        még ha a címe nem 'Telegram'.
        """
        if not WIN32_AVAILABLE:
            return []

        # Telegram.exe PID-ek lekérése tasklist segítségével
        telegram_pids = self._get_telegram_pids()
        if not telegram_pids:
            # Fallback: cím alapján keresés
            found = []
            def title_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd) and "Telegram" in win32gui.GetWindowText(hwnd):
                    found.append(hwnd)
                return True
            win32gui.EnumWindows(title_cb, None)
            return found

        found = []

        def callback(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return True
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid in telegram_pids:
                    rect = win32gui.GetWindowRect(hwnd)
                    w = rect[2] - rect[0]
                    h = rect[3] - rect[1]
                    if w > 80 and h > 80:   # apró helper ablakokat kihagyjuk
                        found.append(hwnd)
            except Exception:
                pass
            return True

        win32gui.EnumWindows(callback, None)
        return found

    def _get_telegram_pids(self) -> set:
        """Visszaadja a futó Telegram.exe folyamatok PID-jeit."""
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Telegram.exe", "/FO", "CSV", "/NH"],
                capture_output=True, text=True, timeout=5
            )
            pids = set()
            for line in result.stdout.strip().splitlines():
                parts = line.strip('"').split('","')
                if len(parts) >= 2:
                    try:
                        pids.add(int(parts[1]))
                    except ValueError:
                        pass
            return pids
        except Exception:
            return set()

    def _pick_call_window(self, hwnds: list) -> int:
        """
        A hívás popup ablakot választja ki a listából.
        A popup általában kisebb, mint a fő ablak.
        Ha csak egy ablak van, azt adja vissza.
        """
        if len(hwnds) == 1:
            return hwnds[0]

        # Méret szerint rendezve – a legkisebb valószínűleg a hívás popup
        def area(hwnd):
            r = win32gui.GetWindowRect(hwnd)
            return (r[2] - r[0]) * (r[3] - r[1])

        return min(hwnds, key=area)

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

        Telegram Desktop Qt-ban a gomb típusa nem feltétlenül ButtonControl –
        lehet CustomControl vagy más. Ezért:
          1. Minden vezérlőtípusban keresünk "Accept" nevűt
          2. Ha nincs, kilistázzuk az összes vezérlőt (debug) és a
             felső sávban lévőre kattintunk
        """
        if not UIA_AVAILABLE:
            return False
        try:
            ctrl = auto.ControlFromHandle(hwnd)
            if ctrl is None:
                return False

            # 1. Keresés névvel – BÁRMILYEN vezérlőtípusban
            # (Telegram Qt nem mindig ButtonControl-ként regisztrál)
            accept_names = [
                "Accept", "Accept call", "Answer", "Answer call",
                "Fogadás", "Elfogad",
            ]
            for name in accept_names:
                try:
                    # Control() = bármilyen típus
                    found = ctrl.Control(searchDepth=10, Name=name)
                    if found.Exists(maxSearchSeconds=0.5):
                        print(f"[UIA] Vezérlő megtalálva: '{name}' "
                              f"(típus: {found.ControlTypeName})")
                        found.Click()
                        return True
                except Exception:
                    pass

            # 2. Debug: listázzuk az összes vezérlőt a fő ablakban
            print("[UIA] Nem találtam 'Accept' nevűt – összes vezérlő:")
            all_ctrls: list = []
            self._collect_all_controls(ctrl, all_ctrls, depth=6)

            window_rect = win32gui.GetWindowRect(hwnd)
            win_top = window_rect[1]
            call_bar_bottom = win_top + 250

            for c in all_ctrls:
                try:
                    r = c.BoundingRectangle
                    name = c.Name or ""
                    ctype = c.ControlTypeName
                    # Kiírjuk a felső 250px-en lévő összes elemet
                    if r.top < call_bar_bottom and r.width() > 5 and r.height() > 5:
                        print(f"  [{ctype}] '{name}' @ ({r.left},{r.top}) "
                              f"{r.width()}x{r.height()}")
                except Exception:
                    pass

            # 3. Kattintás az első kattintható elemre a felső sávban
            for c in all_ctrls:
                try:
                    r = c.BoundingRectangle
                    if r.top < call_bar_bottom and r.width() > 20 and r.height() > 20:
                        patterns = c.GetSupportedPatterns()
                        # InvokePattern = kattintható/aktiválható elem
                        if any("Invoke" in str(p) for p in patterns):
                            print(f"[UIA] Kattintás: '{c.Name}' @ ({r.left},{r.top})")
                            c.Click()
                            return True
                except Exception:
                    pass

            print("[UIA] Nem találtam kattintható elemet")
            return False

        except Exception as e:
            print(f"[UIA] Hiba: {e}")
            return False

    def _collect_all_controls(self, ctrl, result: list, depth: int):
        """Rekurzívan összegyűjti az összes UIA vezérlőt."""
        if depth <= 0:
            return
        try:
            for child in ctrl.GetChildren():
                result.append(child)
                self._collect_all_controls(child, result, depth - 1)
        except Exception:
            pass

    def _capture_window_region(self, hwnd, rx, ry, rw, rh):
        """
        PrintWindow API-val fotózza le az ablak egy részét.
        Akkor is működik ha más ablak takarja (pl. az overlay).
        Visszatér PIL Image-dzsel, vagy None-nal hiba esetén.
        """
        try:
            import win32ui
            from PIL import Image as PilImage

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()

            rect = win32gui.GetWindowRect(hwnd)
            full_w = rect[2] - rect[0]
            full_h = rect[3] - rect[1]

            bmp = win32ui.CreateBitmap()
            bmp.CreateCompatibleBitmap(mfc_dc, full_w, full_h)
            save_dc.SelectObject(bmp)

            # PW_RENDERFULLCONTENT = 2, lefotózza az ablakot ha takart is
            ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

            bmp_info = bmp.GetInfo()
            bmp_str = bmp.GetBitmapBits(True)
            img = PilImage.frombuffer(
                "RGB",
                (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                bmp_str, "raw", "BGRX", 0, 1,
            )

            win32gui.DeleteObject(bmp.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            return img.crop((rx, ry, rx + rw, ry + rh))
        except Exception as e:
            print(f"[CallHandler] PrintWindow hiba: {e}")
            return None

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

            # PrintWindow: az ablak valódi tartalmát kapjuk még akkor is,
            # ha valami más ablak takarja (pl. korábban az overlay)
            screenshot = self._capture_window_region(hwnd, 0, 0, search_w, search_h)
            if screenshot is None:
                # fallback: sima screenshot
                screenshot = ImageGrab.grab(bbox=(wx, wy, wx + search_w, wy + search_h))
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
