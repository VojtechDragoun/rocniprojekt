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
# pohodlná práce s cestami k souborům a složkám

from werkzeug.security import generate_password_hash
# funkce pro vytvoření hashe hesla
# hesla se díky tomu neukládají jako obyčejný text


# -------------------------------------------------
# CESTY K SOUBORŮM
# -------------------------------------------------

# ROOT = hlavní složka projektu
# __file__ = cesta k tomuto souboru
# .resolve() = převede na absolutní cestu
# .parent.parent = o dvě úrovně výš:
# database/init_db.py -> database -> root projektu
ROOT = Path(__file__).resolve().parent.parent

# složka s databázovými soubory
DB_DIR = ROOT / "database"

# cesta k SQLite databázi
DB_PATH = DB_DIR / "rccar.db"

# cesta k SQL schématu
SCHEMA = DB_DIR / "schema.sql"


# -------------------------------------------------
# PŘIPOJENÍ K DATABÁZI
# -------------------------------------------------

def connect():
    # vytvoří připojení k databázi
    # pokud soubor databáze neexistuje, SQLite ho vytvoří

    conn = sqlite3.connect(DB_PATH)

    # row_factory umožní číst řádky jako slovníky
    # např. row["id"] místo row[0]
    conn.row_factory = sqlite3.Row

    # zapnutí cizích klíčů
    # ve SQLite to není vždy aktivní automaticky
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


# -------------------------------------------------
# NAČTENÍ A PROVEDENÍ SCHEMA.SQL
# -------------------------------------------------

def apply_schema(conn):
    # zkontrolujeme, že schema.sql opravdu existuje
    if not SCHEMA.exists():
        raise Exception("schema.sql nenalezen")

    # načteme celý obsah schema.sql do stringu
    sql = SCHEMA.read_text(encoding="utf-8")

    # executescript umí spustit více SQL příkazů najednou
    conn.executescript(sql)


# -------------------------------------------------
# VLOŽENÍ UKÁZKOVÝCH DAT
# -------------------------------------------------

def seed(conn):
    """
    Vloží ukázková data do tabulek.

    Používá se hlavně pro školní projekt a první spuštění,
    aby aplikace měla hned nějaké uživatele, auta a jízdy.
    """

    # -------------------
    # USERS
    # -------------------

    # připravíme si demo uživatele
    # každý záznam má:
    # - username
    # - password_hash
    # - role
    users = [
        ("vojtech", generate_password_hash("Vojtech123"), "user"),
        ("admin", generate_password_hash("Admin123"), "admin"),
        ("pepa", generate_password_hash("Pepa123"), "user"),
    ]

    # vložíme uživatele do tabulky
    for u in users:
        conn.execute(
            "INSERT OR IGNORE INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            u
        )
        # INSERT OR IGNORE znamená:
        # pokud už záznam existuje, nevznikne chyba a nic se neduplikuje

    # -------------------
    # CARS
    # -------------------

    # ukázková auta
    # každý záznam má:
    # - name = název auta
    # - color = barva auta
    # - steer_angle_deg = úhel zatáčení
    cars = [
        ("Auto 1", "červená", 45),
        ("Auto 2", "modrá", 40),
        ("Auto 3", "černá", 35),
    ]

    # vložíme auta do tabulky cars
    for c in cars:
        conn.execute(
            "INSERT OR IGNORE INTO cars (name, color, steer_angle_deg) VALUES (?, ?, ?);",
            c
        )

    # -------------------
    # RIDES
    # -------------------

    # než vložíme jízdy, musíme si načíst skutečná id
    # uživatelů a aut z databáze

    u1 = conn.execute("SELECT id FROM users WHERE username='vojtech'").fetchone()
    u2 = conn.execute("SELECT id FROM users WHERE username='admin'").fetchone()
    u3 = conn.execute("SELECT id FROM users WHERE username='pepa'").fetchone()

    c1 = conn.execute("SELECT id FROM cars WHERE name='Auto 1'").fetchone()
    c2 = conn.execute("SELECT id FROM cars WHERE name='Auto 2'").fetchone()
    c3 = conn.execute("SELECT id FROM cars WHERE name='Auto 3'").fetchone()

    # pojistka:
    # pokud by některé id neexistovalo, něco se při vkládání nepovedlo
    if not (u1 and u2 and u3 and c1 and c2 and c3):
        raise Exception("něco se nevložilo")

    # zjistíme, kolik jízd už v tabulce je
    count = conn.execute("SELECT COUNT(*) as n FROM rides").fetchone()["n"]

    # jízdy vložíme jen tehdy, když je tabulka rides zatím prázdná
    if count == 0:
        # dokončená jízda uživatele vojtech s autem Auto 1
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, ?);",
            (u1["id"], c1["id"], 120)
        )

        # dokončená jízda uživatele admin s autem Auto 2
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, ?);",
            (u2["id"], c2["id"], 75)
        )

        # nedokončená jízda uživatele pepa s autem Auto 3
        # duration_sec = NULL
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, NULL);",
            (u3["id"], c3["id"])
        )


# -------------------------------------------------
# HLAVNÍ FUNKCE
# -------------------------------------------------

def main():
    # zajistíme, že složka database existuje
    DB_DIR.mkdir(exist_ok=True)

    # připojení k databázi
    conn = connect()

    # vytvoření tabulek podle schema.sql
    apply_schema(conn)

    # vložení ukázkových dat
    seed(conn)

    # uložení všech změn do DB
    conn.commit()

    # zavření spojení
    conn.close()

    # informační výpis do konzole
    print("DB ready")
    print("login:")
    print("vojtech / Vojtech123")
    print("admin / Admin123")
    print("pepa / Pepa123")


# tenhle blok zajistí, že se main() spustí jen při přímém spuštění souboru
if __name__ == "__main__":
    main()