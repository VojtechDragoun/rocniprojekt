"""
arduino_comm.py – Serial bridge pro Arduino UNO (auto-detekce COM portu)
=======================================================================

Co to řeší:
- Nemusíš ručně přepisovat COM5/COM7.
- Kód si při prvním použití najde port, kde je Arduino připojené.

Jak hledáme:
- Projdeme všechny COM porty (serial.tools.list_ports.comports()).
- Preferujeme porty podle "description" / "manufacturer":
  - Arduino
  - CH340 (častý klon)
  - CP210
  - USB-SERIAL / USB Serial

Poznámka:
- Po otevření portu se UNO často resetuje -> sleep(1.5)
"""

from __future__ import annotations

import time
import threading
from typing import Optional

import serial
from serial.tools import list_ports


BAUDRATE = 115200
WRITE_TIMEOUT = 0.2

_lock = threading.Lock()
_ser: Optional[serial.Serial] = None
_cached_port: Optional[str] = None


def _pick_port() -> str:
    """
    Vybere nejlepší COM port pro Arduino.

    1) Projde dostupné porty a hledá podle klíčových slov.
    2) Pokud nic nenajde, zkusí vzít první port (když existuje).
    3) Pokud není žádný port, vyhodí error.
    """
    ports = list(list_ports.comports())
    if not ports:
        raise RuntimeError("Nenalezen žádný COM port. Je Arduino připojené přes USB?")

    # Klíčová slova, která se na Windows často objevují u Arduino/USB převodníků
    keywords = [
        "arduino",
        "ch340",
        "cp210",
        "cp210x",
        "usb-serial",
        "usb serial",
        "silicon labs",
        "wch",
    ]

    # Seřadíme kandidáty: nejdřív ty, které matchují keywordy
    scored = []
    for p in ports:
        desc = (p.description or "").lower()
        manuf = (p.manufacturer or "").lower()
        hwid = (p.hwid or "").lower()
        text = f"{desc} {manuf} {hwid}"

        score = 0
        for kw in keywords:
            if kw in text:
                score += 10

        # Bonus: často Arduino UNO hlásí "Arduino Uno" nebo podobně
        if "arduino" in text:
            score += 20

        scored.append((score, p.device, p.description, p.manufacturer))

    scored.sort(reverse=True, key=lambda x: x[0])

    best_score, best_dev, best_desc, best_manuf = scored[0]
    if best_score > 0:
        # Našli jsme něco, co vypadá jako Arduino
        return best_dev

    # Nic "Arduino-like" jsme nenašli -> vezmeme první port
    return ports[0].device


def _connect() -> serial.Serial:
    """
    Otevře serial spojení (pokud už není otevřené).
    Port vybere automaticky.
    """
    global _ser, _cached_port

    if _ser and _ser.is_open:
        return _ser

    # Pokud už jsme port jednou našli, použijeme ho z cache
    port = _cached_port or _pick_port()

    s = serial.Serial(
        port=port,
        baudrate=BAUDRATE,
        timeout=0.1,
        write_timeout=WRITE_TIMEOUT,
    )

    # UNO reset při otevření portu
    time.sleep(1.5)

    _ser = s
    _cached_port = port
    return s


def send_line(cmd: str) -> None:
    """
    Pošle jeden příkaz do Arduino jako řádek.
    Např: "STEER:L"
    """
    line = (cmd.strip() + "\n").encode("utf-8")

    with _lock:
        s = _connect()
        s.write(line)
        s.flush()


def debug_list_ports() -> list[str]:
    """
    Pomocná funkce – kdybys chtěl vypsat porty a zjistit, co Windows ukazuje.
    Nevolá se automaticky, jen pro debug.
    """
    out = []
    for p in list_ports.comports():
        out.append(f"{p.device} | {p.description} | {p.manufacturer} | {p.hwid}")
    return out