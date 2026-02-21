"""
Papi Monitor – Telegram hívás és üzenetfigyelő
===============================================
Automatikusan figyeli a bejövő hívásokat és üzeneteket Telegramon.
Minden más ablak (pl. Chrome) felett jelzi ki a hívásokat és üzeneteket.

Indítás: python main.py
Leállítás: Ctrl+C vagy a tálcán lévő ikonra jobb klikk → Kilépés
"""

import asyncio
import sys
import threading
from pathlib import Path

from telethon import TelegramClient, events
from telethon.tl.types import UpdatePhoneCall

import config

# Ellenőrzés: ki van-e töltve a .env?
if not config.API_ID or not config.API_HASH or not config.PHONE:
    print("=" * 60)
    print("HIBA: Hiányzó beállítások!")
    print("Másold a .env.example fájlt .env névre, és töltsd ki:")
    print("  API_ID    – my.telegram.org/apps oldalról")
    print("  API_HASH  – my.telegram.org/apps oldalról")
    print("  PHONE     – telefonszám pl. +36201234567")
    print("=" * 60)
    sys.exit(1)


def run_tray_icon(stop_event: threading.Event):
    """Rendszertálca ikon futtatása (opcionális, hibakezeléssel)."""
    try:
        import pystray
        from PIL import Image, ImageDraw

        # Egyszerű zöld kör ikon rajzolása
        img = Image.new("RGB", (64, 64), color="#1a1a2e")
        draw = ImageDraw.Draw(img)
        draw.ellipse([8, 8, 56, 56], fill="#00d26a")
        draw.text((20, 18), "P", fill="white")

        def on_quit(icon, item):
            stop_event.set()
            icon.stop()

        icon = pystray.Icon(
            "papi_monitor",
            img,
            "Papi Monitor (fut)",
            menu=pystray.Menu(pystray.MenuItem("Kilépés", on_quit)),
        )
        icon.run()
    except Exception as e:
        print(f"[Tray] Rendszertálca nem elérhető: {e}")


async def main():
    print("=" * 60)
    print("  Papi Monitor – Telegram figyelő")
    print("=" * 60)

    client = TelegramClient(
        str(Path(__file__).parent / "papi_session"),
        config.API_ID,
        config.API_HASH,
    )

    print("Bejelentkezés Telegramra...")
    await client.start(phone=config.PHONE)

    me = await client.get_me()
    print(f"Bejelentkezve: {me.first_name} ({me.phone})")
    print()

    # Handler-ek betöltése
    from handlers.call_handler import CallHandler
    from handlers.message_handler import MessageHandler

    call_handler = CallHandler(client)
    message_handler = MessageHandler(client)

    # --- Eseménykezelők regisztrálása ---

    @client.on(events.Raw(UpdatePhoneCall))
    async def on_phone_call(event):
        await call_handler.handle(event)

    @client.on(events.NewMessage(incoming=True))
    async def on_new_message(event):
        await message_handler.handle(event)

    # Rendszertálca ikon háttérszálon
    stop_event = threading.Event()
    tray_thread = threading.Thread(
        target=run_tray_icon, args=(stop_event,), daemon=True
    )
    tray_thread.start()

    print("Figyelés indul... (Ctrl+C a leállításhoz)")
    print("-" * 60)

    try:
        await client.run_until_disconnected()
    except KeyboardInterrupt:
        print("\nLeállítás...")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
