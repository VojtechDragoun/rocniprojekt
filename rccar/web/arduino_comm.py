"""
arduino_comm.py
===============

Tenhle soubor slouží jako jednoduchý most mezi Flask backendem a Arduinem.

Co dělá:
- automaticky hledá COM port, na kterém je pravděpodobně Arduino
- otevře sériovou komunikaci na 115200 baud
- umí poslat textový příkaz do Arduina, např. "STEER:L"

Použití v projektu:
- app.py zavolá send_line("STEER:L")
- tenhle soubor otevře serial port
- a pošle do Arduina text s koncem řádku

Příklad:
  send_line("STEER:L")

Do Arduina pak odejde:
  STEER:L\\n
"""

from __future__ import annotations
# dovolí modernější typové anotace

import time
# používá se na krátké čekání po otevření portu

from typing import Optional
# Optional znamená, že proměnná může být buď daného typu, nebo None

import serial
# hlavní pyserial knihovna pro sériovou komunikaci

import serial.tools.list_ports
# část pyserial knihovny pro hledání dostupných COM portů


# přenosová rychlost
# musí souhlasit s tím, co je nastavené v Arduino kódu přes Serial.begin(...)
BAUD = 115200


# sem se uloží otevřený serial port
# na začátku je None, protože ještě není otevřený
_ser: Optional[serial.Serial] = None


def _auto_find_port() -> str:
    """
    Pokusí se automaticky najít správný COM port pro Arduino.

    Postup:
    1) načte všechny dostupné COM porty
    2) zkusí najít takový, který vypadá jako Arduino / USB serial převodník
    3) pokud nic takového nenajde, vezme aspoň první dostupný port

    Vrací:
    - název portu jako string, např. 'COM3'
    """

    # načte seznam všech dostupných portů
    ports = list(serial.tools.list_ports.comports())

    # když není žádný port, vyhodí chybu
    if not ports:
        raise RuntimeError("Nenalezen žádný COM port (Arduino není připojené?).")

    # sem se budou ukládat porty, které vypadají jako správné
    preferred = []

    # projdeme všechny nalezené porty
    for p in ports:
        # popis portu, např. Arduino Uno / USB Serial apod.
        desc = (p.description or "").lower()

        # hardwarové ID portu
        hwid = (p.hwid or "").lower()

        # pokud popis nebo hwid obsahuje typické výrazy pro Arduino / převodníky,
        # bereme ten port jako pravděpodobně správný
        if any(x in desc for x in ["arduino", "ch340", "usb serial", "cp210", "ftdi"]) or any(
            x in hwid for x in ["ch340", "cp210", "ftdi"]
        ):
            preferred.append(p.device)

    # když jsme našli nějaké "lepší" kandidáty, vezmeme první z nich
    if preferred:
        return preferred[0]

    # když nic nenašlo nic typického, vrátí aspoň první dostupný port
    return ports[0].device


def _get_serial() -> serial.Serial:
    """
    Vrátí otevřený serial port.

    Pokud už port jednou otevřený je, použije se znovu.
    Pokud ještě otevřený není, automaticky se najde a otevře.

    To je výhodné, protože se port neotevírá při každém příkazu znovu.
    """

    global _ser
    # chceme pracovat s globální proměnnou _ser

    # když už serial existuje a je otevřený, jen ho vrátíme
    if _ser is not None and _ser.is_open:
        return _ser

    # najdeme vhodný COM port
    port = _auto_find_port()

    # otevření serial portu
    _ser = serial.Serial(port, BAUD, timeout=0.2, write_timeout=0.2)

    # Arduino se po otevření portu často automaticky resetuje
    # proto je potřeba chvíli počkat, než naběhne
    time.sleep(2.0)

    try:
        # vyčištění vstupního bufferu
        _ser.reset_input_buffer()

        # vyčištění výstupního bufferu
        _ser.reset_output_buffer()
    except Exception:
        # některé implementace nebo situace můžou vyhodit chybu
        # tady to není kritické, takže to jen ignorujeme
        pass

    return _ser


def send_line(line: str) -> None:
    """
    Pošle jeden textový řádek do Arduina.

    Např.:
      send_line("STEER:L")

    Výsledek:
      do serialu se odešle "STEER:L\\n"
    """

    # získání otevřeného serial portu
    ser = _get_serial()

    # připraví zprávu:
    # - strip() odstraní mezery a konce řádku kolem textu
    # - přidá se "\n", protože Arduino čeká příkaz po řádcích
    # - encode převede text na bytes
    msg = (line.strip() + "\n").encode("ascii", errors="ignore")

    # odeslání dat do portu
    ser.write(msg)

    # flush zajistí, že se data opravdu hned pošlou ven
    ser.flush()