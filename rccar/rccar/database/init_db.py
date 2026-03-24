"""
init_db.py
==========

Tenhle soubor slouží k vytvoření databáze a vložení ukázkových dat.

Co dělá:
1) načte schema.sql
2) vytvoří tabulky v SQLite databázi
3) vloží demo data:
   - 3 uživatele
   - 3 auta
   - 3 jízdy

Použití:
- hodí se hlavně na začátku projektu
- po spuštění bude aplikace hned mít s čím pracovat
- backend (např. app.py) pak může z této databáze číst

Spuštění:
  py database\\init_db.py
"""

import sqlite3
# vestavěná knihovna Pythonu pro práci se SQLite databází

from pathlib import Path
# Path je pohodlnější způsob práce s cestami k souborům a složkám

from werkzeug.security import generate_password_hash
# funkce pro vytvoření hashe hesla
# díky tomu nejsou hesla uložená přímo jako obyčejný text


# -------------------------------------------------
# CESTY K SOUBORŮM
# -------------------------------------------------

# __file__ = cesta k tomuto souboru
# .resolve() = převede na absolutní cestu
# .parent.parent = posune se o 2 úrovně výš:
# database/init_db.py -> database -> root projektu
ROOT = Path(__file__).resolve().parent.parent

# cesta ke složce database
DB_DIR = ROOT / "database"

# cesta k SQLite databázi
DB_PATH = DB_DIR / "rccar.db"

# cesta k SQL souboru se strukturou databáze
SCHEMA = DB_DIR / "schema.sql"


# -------------------------------------------------
# PŘIPOJENÍ K DATABÁZI
# -------------------------------------------------

def connect():
    # vytvoří připojení k databázi
    # pokud soubor rccar.db ještě neexistuje, SQLite ho vytvoří
    conn = sqlite3.connect(DB_PATH)

    # díky row_factory můžeme pak číst výsledek třeba jako row["id"]
    # místo row[0], což je přehlednější
    conn.row_factory = sqlite3.Row

    # zapnutí foreign keys
    # ve SQLite nejsou vždy aktivní automaticky
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


# -------------------------------------------------
# NAČTENÍ A PROVEDENÍ SCHEMA.SQL
# -------------------------------------------------

def apply_schema(conn):
    # nejdřív zkontrolujeme, jestli schema.sql opravdu existuje
    if not SCHEMA.exists():
        raise Exception("schema.sql nenalezen")

    # načtení celého obsahu souboru schema.sql do proměnné
    sql = SCHEMA.read_text(encoding="utf-8")

    # executescript umí spustit více SQL příkazů najednou
    # takže se hodí na celé schema.sql
    conn.executescript(sql)


# -------------------------------------------------
# VLOŽENÍ UKÁZKOVÝCH DAT
# -------------------------------------------------

def seed(conn):

    # -------------------
    # USERS
    # -------------------

    # připravíme si 3 uživatele
    # hesla se neukládají přímo, ale jako hash
    # role je buď user nebo admin
    users = [
        ("vojtech", generate_password_hash("Vojtech123"), "user"),
        ("admin", generate_password_hash("Admin123"), "admin"),
        ("pepa", generate_password_hash("Pepa123"), "user"),
    ]

    # projdeme všechny uživatele a vložíme je do tabulky users
    for u in users:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            u
        )
        # INSERT OR IGNORE znamená:
        # když už tam takový záznam je (např. stejný username),
        # tak se nevloží znovu a nevznikne chyba

    # -------------------
    # CARS
    # -------------------

    # připravíme si 3 auta
    # sloupce znamenají:
    # - name = název auta
    # - power_limit_percent = omezení výkonu v procentech
    # - steer_angle_deg = úhel zatáčení
    cars = [
        ("Auto 1", 10, 45),
        ("Auto 2", 20, 40),
        ("Auto 3", 30, 35),
    ]

    # vložení aut do tabulky cars
    for c in cars:
        conn.execute(
            "INSERT OR IGNORE INTO cars (name, power_limit_percent, steer_angle_deg) VALUES (?, ?, ?);",
            c
        )

    # -------------------
    # RIDES
    # -------------------

    # u rides potřebujeme skutečná user_id a car_id,
    # protože rides odkazuje na users a cars přes cizí klíče

    # načtení id uživatelů
    u1 = conn.execute("SELECT id FROM users WHERE username='vojtech'").fetchone()
    u2 = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    u3 = conn.execute("SELECT id FROM users WHERE username='pepa'").fetchone()

    # načtení id aut
    c1 = conn.execute("SELECT id FROM cars WHERE name='Auto 1'").fetchone()
    c2 = conn.execute("SELECT id FROM cars WHERE name='Auto 2'").fetchone()
    c3 = conn.execute("SELECT id FROM cars WHERE name='Auto 3'").fetchone()

    # když by některý user nebo car neexistoval,
    # znamená to, že se předchozí data nevložila správně
    if not (u1 and u2 and u3 and c1 and c2 and c3):
        raise Exception("něco se nevložilo")

    # zjistíme, kolik záznamů už je v rides
    count = conn.execute("SELECT COUNT(*) as n FROM rides").fetchone()["n"]

    # rides vložíme jen tehdy, když je tabulka zatím prázdná
    # aby se při každém spuštění nepřidávaly další a další jízdy
    if count == 0:
        # 1. dokončená jízda
        # user vojtech jel s autem Auto 1 po dobu 120 sekund
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, ?);",
            (u1["id"], c1["id"], 120)
        )

        # 2. dokončená jízda
        # admin jel s autem Auto 2 po dobu 75 sekund
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, ?);",
            (u2["id"], c2["id"], 75)
        )

        # 3. nedokončená jízda
        # duration_sec je NULL
        # to může znamenat třeba jízdu, která ještě probíhá,
        # nebo nemá uložený konečný čas
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, NULL);",
            (u3["id"], c3["id"])
        )


# -------------------------------------------------
# HLAVNÍ FUNKCE
# -------------------------------------------------

def main():
    # když složka database neexistuje, vytvoří se
    DB_DIR.mkdir(exist_ok=True)

    # připojení k databázi
    conn = connect()

    # vytvoření tabulek podle schema.sql
    apply_schema(conn)

    # vložení demo dat
    seed(conn)

    # uložení všech změn
    conn.commit()

    # zavření databázového spojení
    conn.close()

    # výpis do konzole, aby bylo vidět, že vše proběhlo správně
    print("DB ready")
    print("login:")
    print("vojtech / Vojtech123")
    print("admin / Admin123")
    print("pepa / Pepa123")


# tento blok zajistí, že se main() spustí jen tehdy,
# když se soubor spustí přímo
# ne když bude jen importovaný z jiného souboru
if __name__ == "__main__":
    main()