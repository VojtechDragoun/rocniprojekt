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
# není to nutné pro funkci programu,
# ale zlepšuje to čitelnost a práci s typy

import time
# používá se na krátké čekání po otevření portu
# Arduino se po otevření COM portu často resetuje,
# takže mu dáme čas naběhnout

from typing import Optional
# Optional znamená, že proměnná může být buď daného typu, nebo None
# tady se to hodí pro globální _ser,
# protože na začátku ještě žádný otevřený serial nemáme

import serial
# hlavní pyserial knihovna pro sériovou komunikaci
# přes ni se otevírá COM port a posílají data

import serial.tools.list_ports
# část pyserial knihovny pro hledání dostupných COM portů
# díky tomu nemusíme COM port zapisovat ručně natvrdo


# ------------------------------------------------------------
# NASTAVENÍ PŘENOSU
# ------------------------------------------------------------

BAUD = 115200
# přenosová rychlost
# musí souhlasit s tím, co je nastavené v Arduino kódu přes Serial.begin(...)
# kdyby se lišila, komunikace by byla rozbitá nebo nečitelná


# ------------------------------------------------------------
# GLOBÁLNÍ ODKAZ NA SERIAL
# ------------------------------------------------------------

_ser: Optional[serial.Serial] = None
# sem se uloží otevřený serial port
# na začátku je None, protože ještě není otevřený
# výhoda je, že port nemusíme při každém příkazu otevírat znovu


# ------------------------------------------------------------
# AUTOMATICKÉ HLEDÁNÍ COM PORTU
# ------------------------------------------------------------

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

    ports = list(serial.tools.list_ports.comports())
    # načte seznam všech dostupných COM portů v systému
    # každý port má různé informace:
    # - device (např. COM3)
    # - description
    # - hwid

    if not ports:
        # pokud není nalezen vůbec žádný port,
        # není k čemu se připojit
        raise RuntimeError("Nenalezen žádný COM port (Arduino není připojené?).")

    preferred = []
    # sem si budeme ukládat porty,
    # které vypadají jako dobrý kandidát na Arduino

    for p in ports:
        # projdeme všechny nalezené porty

        desc = (p.description or "").lower()
        # popis portu jako malá písmena
        # např. "arduino uno", "usb serial device" apod.

        hwid = (p.hwid or "").lower()
        # hardwarové ID portu
        # často obsahuje typ převodníku, třeba CH340 nebo CP210

        if any(x in desc for x in ["arduino", "ch340", "usb serial", "cp210", "ftdi"]) or any(
            x in hwid for x in ["ch340", "cp210", "ftdi"]
        ):
            # pokud popis nebo hwid obsahuje typické výrazy
            # pro Arduino nebo USB-serial převodníky,
            # bereme tento port jako vhodný
            preferred.append(p.device)

    if preferred:
        # když jsme našli nějaké "lepší" kandidáty,
        # vrátíme první z nich
        return preferred[0]

    return ports[0].device
    # když nic neodpovídá typickým názvům,
    # vezmeme aspoň první dostupný port
    # je to nouzové řešení, ale často funguje


# ------------------------------------------------------------
# OTEVŘENÍ / ZNOVUPOUŽITÍ SERIAL PORTU
# ------------------------------------------------------------

def _get_serial() -> serial.Serial:
    """
    Vrátí otevřený serial port.

    Pokud už port jednou otevřený je, použije se znovu.
    Pokud ještě otevřený není, automaticky se najde a otevře.

    To je výhodné, protože se port neotevírá při každém příkazu znovu.
    """

    global _ser
    # chceme pracovat s globální proměnnou _ser
    # bez global bychom uvnitř funkce vytvářeli lokální kopii

    if _ser is not None and _ser.is_open:
        # když už serial existuje a je otevřený,
        # vrátíme ho a nic znovu neotevíráme
        return _ser

    port = _auto_find_port()
    # najdeme vhodný COM port

    _ser = serial.Serial(port, BAUD, timeout=0.2, write_timeout=0.2)
    # otevření serial portu
    # parametry:
    # - port = např. COM3
    # - BAUD = rychlost komunikace
    # - timeout = jak dlouho čekat při čtení
    # - write_timeout = jak dlouho čekat při zápisu

    time.sleep(2.0)
    # Arduino se po otevření portu často automaticky resetuje
    # proto je potřeba chvíli počkat, než naběhne
    # bez tohoto čekání by první příkazy mohly zmizet

    try:
        _ser.reset_input_buffer()
        # vyčistí vstupní buffer
        # aby tam nezůstala stará data

        _ser.reset_output_buffer()
        # vyčistí výstupní buffer
        # aby se neposílalo něco starého
    except Exception:
        # některé implementace nebo situace můžou vyhodit chybu
        # tady to není kritické, takže to jen ignorujeme
        pass

    return _ser
    # vrátíme otevřený serial port,
    # který se pak použije pro zápis


# ------------------------------------------------------------
# ODESLÁNÍ JEDNOHO ŘÁDKU DO ARDUINA
# ------------------------------------------------------------

def send_line(line: str) -> None:
    """
    Pošle jeden textový řádek do Arduina.

    Např.:
      send_line("STEER:L")

    Výsledek:
      do serialu se odešle "STEER:L\\n"
    """

    ser = _get_serial()
    # získání otevřeného serial portu
    # buď už otevřeného, nebo nově otevřeného

    msg = (line.strip() + "\n").encode("ascii", errors="ignore")
    # připraví zprávu:
    # - strip() odstraní mezery a konce řádků kolem textu
    # - přidá se "\n", protože Arduino čeká příkaz po řádcích
    # - encode převede text na bytes
    # - ascii + errors="ignore" zahodí případné znaky,
    #   které by nešly korektně poslat

    ser.write(msg)
    # odeslání dat do portu

    ser.flush()
    # flush zajistí, že se data opravdu hned pošlou ven
    # bez flush by mohla chvíli čekat v bufferu