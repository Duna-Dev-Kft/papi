"""
Windows automatikus indítás beállítása.

Futtatás: python setup_autostart.py
Ez hozzáadja a Papi Monitor-t a Windows indítási programokhoz,
így a számítógép bekapcsolásakor automatikusan elindul.

Eltávolítás: python setup_autostart.py --remove
"""

import sys
import os
import subprocess
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent.resolve()
MAIN_PY = SCRIPT_DIR / "main.py"
STARTUP_FOLDER = Path(os.environ.get("APPDATA", "")) / \
    "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
VBS_FILE = STARTUP_FOLDER / "papi_monitor.vbs"


VBS_TEMPLATE = '''
' Papi Monitor automatikus indító (ablak nélkül)
Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw.exe ""{main_py}""", 0, False
'''


def add_autostart():
    """Hozzáadja a Papi Monitor-t a Windows indítási mappához."""
    if not STARTUP_FOLDER.exists():
        print(f"HIBA: Indítási mappa nem található: {STARTUP_FOLDER}")
        return False

    # VBScript az ablak nélküli indításhoz (pythonw.exe)
    vbs_content = VBS_TEMPLATE.format(main_py=str(MAIN_PY).replace("\\", "\\\\"))
    VBS_FILE.write_text(vbs_content, encoding="utf-8")

    print("✅ Papi Monitor beállítva automatikus indításra!")
    print(f"   Indítási fájl: {VBS_FILE}")
    print()
    print("A következő bejelentkezéskor automatikusan elindul.")
    return True


def remove_autostart():
    """Eltávolítja az automatikus indítást."""
    if VBS_FILE.exists():
        VBS_FILE.unlink()
        print("✅ Automatikus indítás eltávolítva.")
    else:
        print("ℹ️  Nem volt beállítva automatikus indítás.")


def check_python():
    """Ellenőrzi, hogy a Python elérhető-e."""
    try:
        result = subprocess.run(
            ["python", "--version"], capture_output=True, text=True
        )
        print(f"Python: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("HIBA: Python nem található a PATH-ban!")
        return False


def install_dependencies():
    """Telepíti a szükséges csomagokat."""
    req_file = SCRIPT_DIR / "requirements.txt"
    if not req_file.exists():
        print("HIBA: requirements.txt nem található!")
        return False

    print("Csomagok telepítése...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", str(req_file)],
        capture_output=False,
    )
    return result.returncode == 0


if __name__ == "__main__":
    if "--remove" in sys.argv:
        remove_autostart()
        sys.exit(0)

    print("=" * 60)
    print("  Papi Monitor – Telepítő")
    print("=" * 60)
    print()

    if not check_python():
        sys.exit(1)

    print()
    print("Függőségek telepítése...")
    if install_dependencies():
        print("✅ Csomagok telepítve.")
    else:
        print("⚠️  Néhány csomag telepítése sikertelen – ellenőrizd manuálisan.")

    print()
    add_autostart()

    print()
    print("=" * 60)
    print("Következő lépések:")
    print("  1. Másold .env.example → .env")
    print("  2. Töltsd ki az API_ID, API_HASH, PHONE mezőket")
    print("     (my.telegram.org/apps oldalon regisztrálj egy appot)")
    print("  3. Futtasd: python main.py")
    print("  4. Első indításkor Telegram kódot kér SMS-ben")
    print("=" * 60)
