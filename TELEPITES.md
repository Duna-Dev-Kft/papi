# Papi Monitor – Telepítési útmutató

## Mi ez?

Egy alkalmazás, amely automatikusan figyeli a Telegram hívásokat és üzeneteket,
és minden más ablak (pl. Chrome) felett jelzi ki őket vizuálisan.

## Funkciók

- 📞 **Bejövő hívás** → teljes képernyős riasztó ablak, automatikus felvétel
- 💬 **Bejövő üzenet** → popup értesítő a Chrome felett, kattintásra Telegram nyílik
- 🔄 **Automatikus indítás** → számítógép bekapcsolásakor elindul
- 🖥️ **Rendszertálca ikon** → a háttérben fut, szinte nem látható

---

## Telepítés

### 1. Python telepítése (ha még nincs)

Töltsd le innen: **https://www.python.org/downloads/**

> Fontos: Telepítéskor pipáld be az **"Add Python to PATH"** opciót!

### 2. Telegram API hitelesítő adatok megszerzése

1. Nyisd meg: **https://my.telegram.org/apps**
2. Jelentkezz be a nagyapa telefonszámával
3. Kattints: **"Create application"**
4. Töltsd ki (bármi megfelel):
   - App title: `PapiMonitor`
   - Short name: `papimon`
5. Másold le az **API ID** és **API Hash** értékeket

### 3. Konfiguráció beállítása

1. A `papi` mappában másold a `.env.example` fájlt → `.env`
2. Nyisd meg a `.env` fájlt Notepaddel
3. Töltsd ki:
   ```
   API_ID=12345678        ← a my.telegram.org-ról
   API_HASH=abc123...     ← a my.telegram.org-ról
   PHONE=+36201234567     ← a nagyapa telefonszáma
   ```

### 4. Telepítés futtatása

Nyiss egy Parancsablakot (CMD) a `papi` mappában, és futtasd:

```
python setup_autostart.py
```

Ez:
- Telepíti a szükséges programokat
- Beállítja az automatikus indítást

### 5. Első indítás és bejelentkezés

```
python main.py
```

Első futtatáskor:
1. Kéri a telefonszámot (már ki van töltve)
2. SMS-ben érkezik egy Telegram kód – ezt be kell írni
3. Ezután elmenti a bejelentkezést, legközelebb nem kéri

---

## Használat

Az alkalmazás automatikusan:
- Elindul a Windows bejelentkezésekor
- Fut a háttérben (rendszertálca zöld ikon)
- Jelzi a hívásokat és üzeneteket

### Hívásjelzés

Bejövő hívásnál megjelenik egy **piros teljes képernyős ablak**:
- Mutatja a hívó nevét
- 2 másodperc múlva automatikusan felveszi (Telegram Desktop-on)
- Ha ez nem sikerül: a nagy **FELVENNI** gombra kell kattintani

### Üzenetjelzés

Minden bejövő üzenet megjelenik a **jobb felső sarokban**:
- Mutatja a feladót és az üzenet elejét
- 12 másodperc múlva eltűnik
- Kattintásra megnyílik a Telegram Desktop

---

## Megjegyzések

- A Telegram Desktop-nak telepítve kell lennie (automatikus híváskezeléshez)
- Az automatikus felvétel a Telegram Desktop zöld gombját keresi a képernyőn
- Ha a Telegram Desktop sötét témán van, a zöldkereső jobban működik
- Az alkalmazás nem tárolja az üzeneteket, csak megjeleníti őket

## Leállítás

- Rendszertálcán a zöld ikonra jobb klikk → **Kilépés**
- Vagy: CMD-ben `Ctrl+C`

## Automatikus indítás eltávolítása

```
python setup_autostart.py --remove
```
