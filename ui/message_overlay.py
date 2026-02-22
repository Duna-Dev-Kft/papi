"""
Üzenetjelző ablak – a hívásjelzőhöz hasonló nagy, teljes képernyős stílus.
Megjelenik minden más ablak felett, marad amíg az OK gombot meg nem nyomják.
"""

import tkinter as tk
import threading

BG_COLOR     = "#0d1b2a"
HEADER_COLOR = "#1b4f72"
TEXT_COLOR   = "#ffffff"
BTN_OK_COLOR = "#2196f3"
BTN_TG_COLOR = "#1e88e5"


class MessageOverlay:
    def __init__(self):
        self._lock = threading.Lock()
        self._root = None

    def show(self, sender_name: str, message_text: str, open_callback=None):
        """Megmutatja az üzenetjelző ablakot."""
        # Ha már van nyitott ablak, azt bezárjuk és újat nyitunk
        self._close_existing()
        t = threading.Thread(
            target=self._run_window,
            args=(sender_name, message_text, open_callback),
            daemon=True,
        )
        t.start()

    def _close_existing(self):
        with self._lock:
            if self._root:
                try:
                    self._root.quit()
                    self._root.destroy()
                except Exception:
                    pass
                self._root = None

    def _run_window(self, sender_name: str, message_text: str, open_callback):
        try:
            root = tk.Tk()
            with self._lock:
                self._root = root

            root.title("Új üzenet")
            root.attributes("-topmost", True)
            root.configure(bg=BG_COLOR)
            root.focus_force()

            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()

            # Ablak mérete: képernyő 55%-a, középre igazítva
            win_w = int(screen_w * 0.55)
            win_h = int(screen_h * 0.60)
            x = (screen_w - win_w) // 2
            y = (screen_h - win_h) // 2
            root.geometry(f"{win_w}x{win_h}+{x}+{y}")
            root.resizable(False, False)

            # --- Fejléc ---
            header = tk.Frame(root, bg=HEADER_COLOR, pady=18)
            header.pack(fill="x")

            tk.Label(
                header,
                text="💬",
                font=("Arial", 36),
                bg=HEADER_COLOR,
                fg="#ffffff",
            ).pack()

            tk.Label(
                header,
                text="ÚJ ÜZENET",
                font=("Arial", 16, "bold"),
                bg=HEADER_COLOR,
                fg="#aaccee",
            ).pack()

            tk.Label(
                header,
                text=sender_name,
                font=("Arial", 28, "bold"),
                bg=HEADER_COLOR,
                fg="#ffffff",
            ).pack(pady=(4, 0))

            # --- Elválasztó ---
            tk.Frame(root, bg="#2980b9", height=3).pack(fill="x")

            # --- Üzenet szöveg (görgethetővé tehető hosszú üzenetnél) ---
            body = tk.Frame(root, bg=BG_COLOR, padx=30, pady=20)
            body.pack(fill="both", expand=True)

            text_widget = tk.Text(
                body,
                font=("Arial", 20),
                bg="#122333",
                fg=TEXT_COLOR,
                relief="flat",
                wrap="word",
                state="normal",
                cursor="arrow",
                padx=14,
                pady=14,
                borderwidth=0,
                highlightthickness=0,
            )
            text_widget.insert("1.0", message_text)
            text_widget.config(state="disabled")   # csak olvasható
            text_widget.pack(fill="both", expand=True)

            # --- Gombok ---
            btn_frame = tk.Frame(root, bg=BG_COLOR, pady=20)
            btn_frame.pack(fill="x")

            def on_ok():
                _close()

            def on_open_telegram():
                if open_callback:
                    threading.Thread(target=open_callback, daemon=True).start()
                _close()

            def _close():
                with self._lock:
                    self._root = None
                try:
                    root.quit()
                    root.destroy()
                except Exception:
                    pass

            tk.Button(
                btn_frame,
                text="Telegram megnyitása",
                font=("Arial", 16),
                bg=BTN_TG_COLOR,
                fg="#ffffff",
                activebackground="#42a5f5",
                relief="flat",
                padx=24,
                pady=12,
                cursor="hand2",
                command=on_open_telegram,
            ).pack(side="left", padx=(40, 10))

            tk.Button(
                btn_frame,
                text="   OK   ",
                font=("Arial", 20, "bold"),
                bg=BTN_OK_COLOR,
                fg="#ffffff",
                activebackground="#64b5f6",
                relief="flat",
                padx=40,
                pady=12,
                cursor="hand2",
                command=on_ok,
            ).pack(side="right", padx=(10, 40))

            # Enter / Space is bezárja
            root.bind("<Return>", lambda e: on_ok())
            root.bind("<space>", lambda e: on_ok())
            root.bind("<Escape>", lambda e: on_ok())

            root.mainloop()

        except Exception as e:
            print(f"[MessageOverlay] Hiba: {e}")
