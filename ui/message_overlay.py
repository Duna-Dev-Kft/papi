"""
Üzenetjelző popup ablak.
Megjelenik a képernyő jobb felső sarkában, minden más ablak felett.
Automatikusan eltűnik néhány másodperc múlva.
"""

import tkinter as tk
import threading
from config import MSG_BG_COLOR, MSG_TEXT_COLOR, MSG_FONT_SIZE, MSG_DISPLAY_SECONDS


class MessageOverlay:
    def __init__(self):
        self._windows = []
        self._lock = threading.Lock()
        self._y_offset = 20  # következő ablak y pozíciója

    def show(self, sender_name: str, message_text: str, open_callback=None):
        """Megmutat egy üzenet értesítőt."""
        t = threading.Thread(
            target=self._run_window,
            args=(sender_name, message_text, open_callback),
            daemon=True,
        )
        t.start()

    def _run_window(self, sender_name: str, message_text: str, open_callback):
        try:
            root = tk.Tk()
            root.overrideredirect(True)          # nincs ablakkeret
            root.attributes("-topmost", True)    # minden felett
            root.attributes("-alpha", 0.95)      # enyhén átlátszó
            root.configure(bg=MSG_BG_COLOR)

            # Méret és pozíció
            width = 440
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()

            # Vízszintes pozíció: jobb felső sarok
            x = screen_w - width - 20

            # Függőleges: más értesítők alatt
            with self._lock:
                y = self._y_offset
                self._y_offset += 160
                self._windows.append(root)

            root.geometry(f"{width}x150+{x}+{y}")

            # --- Fejléc: feladó ---
            header = tk.Frame(root, bg="#2980b9", padx=12, pady=8)
            header.pack(fill="x")

            sender_label = tk.Label(
                header,
                text=f"💬  {sender_name}",
                font=("Arial", MSG_FONT_SIZE - 2, "bold"),
                bg="#2980b9",
                fg="#ffffff",
                anchor="w",
            )
            sender_label.pack(fill="x")

            # --- Üzenet szöveg ---
            body = tk.Frame(root, bg=MSG_BG_COLOR, padx=12, pady=10)
            body.pack(fill="both", expand=True)

            # Megjelenítendő szöveg (max 100 karakter)
            preview = message_text[:100] + ("…" if len(message_text) > 100 else "")

            msg_label = tk.Label(
                body,
                text=preview,
                font=("Arial", MSG_FONT_SIZE - 4),
                bg=MSG_BG_COLOR,
                fg=MSG_TEXT_COLOR,
                wraplength=width - 24,
                justify="left",
                anchor="nw",
            )
            msg_label.pack(fill="both", expand=True)

            # Kattintásra megnyitja a Telegram Desktop-ot
            def on_click(event=None):
                if open_callback:
                    threading.Thread(target=open_callback, daemon=True).start()
                close_window()

            root.bind("<Button-1>", on_click)
            header.bind("<Button-1>", on_click)
            sender_label.bind("<Button-1>", on_click)
            body.bind("<Button-1>", on_click)
            msg_label.bind("<Button-1>", on_click)

            # Bezárás gomb (kis "×" jobb felső sarokban)
            close_btn = tk.Label(
                root,
                text="✕",
                font=("Arial", 14),
                bg="#1a5276",
                fg="#aaaaaa",
                cursor="hand2",
                padx=6,
            )
            close_btn.place(relx=1.0, rely=0.0, anchor="ne")
            close_btn.bind("<Button-1>", lambda e: close_window())

            def close_window():
                with self._lock:
                    if root in self._windows:
                        self._windows.remove(root)
                    # y_offset visszaállítása ha üres
                    if not self._windows:
                        self._y_offset = 20
                try:
                    root.quit()
                    root.destroy()
                except Exception:
                    pass

            # Automatikus bezárás
            root.after(MSG_DISPLAY_SECONDS * 1000, close_window)

            # Belépési animáció (fade in)
            root.attributes("-alpha", 0.0)
            def fade_in(alpha=0.0):
                alpha = min(alpha + 0.1, 0.95)
                root.attributes("-alpha", alpha)
                if alpha < 0.95:
                    root.after(30, lambda: fade_in(alpha))

            root.after(50, fade_in)
            root.mainloop()

        except Exception as e:
            print(f"[MessageOverlay] Hiba: {e}")
