"""
Teljes képernyős hívásjelző ablak.
Megjelenik minden más ablak (pl. Chrome) felett, jelzi ki hív.
"""

import tkinter as tk
import threading
import time
from config import (
    CALL_BG_COLOR, CALL_ACCENT_COLOR, CALL_TEXT_COLOR, CALL_FONT_SIZE
)


class CallOverlay:
    def __init__(self):
        self._root = None
        self._thread = None
        self._accept_callback = None

    def show(self, caller_name: str, accept_callback=None):
        """Megmutatja a hívásjelző ablakot."""
        self._accept_callback = accept_callback
        self._close_existing()

        self._thread = threading.Thread(
            target=self._run_window,
            args=(caller_name,),
            daemon=True
        )
        self._thread.start()

    def close(self):
        """Bezárja az ablakot."""
        self._close_existing()

    def _close_existing(self):
        if self._root:
            try:
                self._root.quit()
                self._root.destroy()
            except Exception:
                pass
            self._root = None

    def _run_window(self, caller_name: str):
        try:
            root = tk.Tk()
            self._root = root

            root.title("Bejövő hívás")
            root.attributes("-topmost", True)
            root.attributes("-fullscreen", True)
            root.configure(bg=CALL_BG_COLOR)
            root.focus_force()

            # Pulzáló háttéreffekt
            self._pulse_state = False

            # --- Felső sáv ---
            top_frame = tk.Frame(root, bg=CALL_BG_COLOR)
            top_frame.pack(fill="x", pady=(60, 0))

            phone_icon = tk.Label(
                top_frame,
                text="📞",
                font=("Arial", 80),
                bg=CALL_BG_COLOR,
                fg=CALL_ACCENT_COLOR,
            )
            phone_icon.pack()

            status_label = tk.Label(
                top_frame,
                text="BEJÖVŐ HÍVÁS",
                font=("Arial", 28, "bold"),
                bg=CALL_BG_COLOR,
                fg="#aaaaaa",
                letterSpacing=4,
            )
            status_label.pack(pady=(10, 0))

            # --- Hívó neve ---
            name_label = tk.Label(
                root,
                text=caller_name,
                font=("Arial", CALL_FONT_SIZE, "bold"),
                bg=CALL_BG_COLOR,
                fg=CALL_TEXT_COLOR,
                wraplength=1000,
            )
            name_label.pack(pady=40)

            # --- Automatikus felvétel visszaszámláló ---
            self._countdown = 3
            countdown_label = tk.Label(
                root,
                text=f"Automatikus felvétel {self._countdown} másodperc múlva...",
                font=("Arial", 20),
                bg=CALL_BG_COLOR,
                fg="#888888",
            )
            countdown_label.pack()

            def tick_countdown():
                if self._countdown > 0:
                    self._countdown -= 1
                    if self._countdown == 0:
                        countdown_label.config(text="Csatlakozás...")
                    else:
                        countdown_label.config(
                            text=f"Automatikus felvétel {self._countdown} másodperc múlva..."
                        )
                    root.after(1000, tick_countdown)

            root.after(1000, tick_countdown)

            # --- Gombok ---
            btn_frame = tk.Frame(root, bg=CALL_BG_COLOR)
            btn_frame.pack(pady=60)

            def on_accept():
                if self._accept_callback:
                    threading.Thread(target=self._accept_callback, daemon=True).start()
                self._close_window(root)

            def on_decline():
                self._close_window(root)

            accept_btn = tk.Button(
                btn_frame,
                text="✅  FELVENNI",
                font=("Arial", 28, "bold"),
                bg=CALL_ACCENT_COLOR,
                fg="#ffffff",
                activebackground="#00ff88",
                relief="flat",
                padx=40,
                pady=20,
                cursor="hand2",
                command=on_accept,
            )
            accept_btn.grid(row=0, column=0, padx=40)

            decline_btn = tk.Button(
                btn_frame,
                text="❌  ELUTASÍTANI",
                font=("Arial", 28, "bold"),
                bg="#c0392b",
                fg="#ffffff",
                activebackground="#e74c3c",
                relief="flat",
                padx=40,
                pady=20,
                cursor="hand2",
                command=on_decline,
            )
            decline_btn.grid(row=0, column=1, padx=40)

            # Telefon ikon pulzálása
            def pulse():
                color = CALL_ACCENT_COLOR if self._pulse_state else "#00ff99"
                phone_icon.config(fg=color)
                self._pulse_state = not self._pulse_state
                root.after(600, pulse)

            root.after(600, pulse)
            root.mainloop()

        except Exception as e:
            print(f"[CallOverlay] Hiba: {e}")

    def _close_window(self, root):
        try:
            root.quit()
            root.destroy()
        except Exception:
            pass
        self._root = None
