"""
arduino_comm.py – jednoduchý bridge pro Serial komunikaci s Arduinem
===============================================================

- Automaticky se pokusí najít Arduino COM port
- Otevře Serial na 115200
- Funkce send_line("L") pošle "L\n"

Poznámky:
- Když je otevřený Arduino Serial Monitor, port může být obsazený.
- Po otevření portu se Arduino často resetne -> čekáme 2 s.
"""

from __future__ import annotations

import time
from typing import Optional

import serial
import serial.tools.list_ports

BAUD = 115200
_ser: Optional[serial.Serial] = None


def _auto_find_port() -> str:
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        raise RuntimeError("Nenalezen žádný COM port (Arduino není připojené?).")

    # Preferujeme zařízení, která typicky odpovídají Arduinu/USB převodníkům
    preferred = []
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(x in desc for x in ["arduino", "ch340", "usb serial", "cp210", "ftdi"]) or any(
            x in hwid for x in ["ch340", "cp210", "ftdi"]
        ):
            preferred.append(p.device)

    if preferred:
        return preferred[0]

    # fallback: první port
    return ports[0].device


def _get_serial() -> serial.Serial:
    global _ser

    if _ser is not None and _ser.is_open:
        return _ser

    port = _auto_find_port()

    # timeout krátký – ať to neblokuje Flask requesty dlouho
    _ser = serial.Serial(port, BAUD, timeout=0.2, write_timeout=0.2)

    # Arduino se po otevření portu často resetne
    time.sleep(2.0)

    try:
        _ser.reset_input_buffer()
        _ser.reset_output_buffer()
    except Exception:
        pass

    return _ser


def send_line(line: str) -> None:
    """
    Pošle jednu "řádku" do Arduina.
    I když posíláme jen 'L', přidáváme \n – je to standardní a kompatibilní.
    """
    ser = _get_serial()
    msg = (line.strip() + "\n").encode("ascii", errors="ignore")
    ser.write(msg)
    ser.flush()