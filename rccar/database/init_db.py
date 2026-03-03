"""
init_db.py
==========

Co to dělá:
1) Vytvoří (nebo aktualizuje) databázi rccar.db podle schema.sql
2) Vloží ukázková data (min. 3 záznamy do každé tabulky):
   - 3 uživatele (hash hesla přes werkzeug)
   - 3 auta
   - 3 jízdy (včetně jedné nedokončené s duration_sec = NULL)

Jak spustit (Windows):
  cd rccar
  py -m venv .venv
  .venv\\Scripts\\activate
  pip install flask
  py database\\init_db.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash


# ------------------------------------------------------------
# Cesty
# ------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent   # .../rccar
DB_DIR = PROJECT_ROOT / "database"
DB_PATH = DB_DIR / "rccar.db"
SCHEMA_PATH = DB_DIR / "schema.sql"


# ------------------------------------------------------------
# DB helper
# ------------------------------------------------------------
def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Chybí schema.sql: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)


def seed_data(conn: sqlite3.Connection) -> None:
    """
    Vloží 3 záznamy do každé tabulky, ale tak,
    aby se data nevkládala znovu při opakovaném spuštění.

    Používáme INSERT OR IGNORE tam, kde máme UNIQUE.
    """

    # -----------------------------
    # 1) USERS (3 záznamy)
    # -----------------------------
    # Hesla pro demo:
    # - vojtěch / Vojtech123
    # - admin   / Admin123
    # - pepa    / Pepa123
    demo_users = [
        ("vojtech", generate_password_hash("Vojtech123"), "user"),
        ("admin", generate_password_hash("Admin123"), "admin"),
        ("pepa", generate_password_hash("Pepa123"), "user"),
    ]

    for username, pw_hash, role in demo_users:
        conn.execute(
            """
            INSERT OR IGNORE INTO users (username, password_hash, role)
            VALUES (?, ?, ?);
            """,
            (username, pw_hash, role),
        )

    # -----------------------------
    # 2) CARS (3 záznamy)
    # -----------------------------
    demo_cars = [
        ("Auto 1", 10, 45),
        ("Auto 2", 20, 40),
        ("Auto 3", 30, 35),
    ]

    for name, power, angle in demo_cars:
        conn.execute(
            """
            INSERT OR IGNORE INTO cars (name, power_limit_percent, steer_angle_deg)
            VALUES (?, ?, ?);
            """,
            (name, power, angle),
        )

    # -----------------------------
    # 3) RIDES (3 záznamy)
    # -----------------------------
    # Abychom mohli vložit rides, potřebujeme reálné user_id a car_id.
    # Vezmeme si je SELECTem podle username a car name.

    u_vojtech = conn.execute("SELECT id FROM users WHERE username = 'vojtech';").fetchone()
    u_admin = conn.execute("SELECT id FROM users WHERE username = 'admin';").fetchone()
    u_pepa = conn.execute("SELECT id FROM users WHERE username = 'pepa';").fetchone()

    c1 = conn.execute("SELECT id FROM cars WHERE name = 'Auto 1';").fetchone()
    c2 = conn.execute("SELECT id FROM cars WHERE name = 'Auto 2';").fetchone()
    c3 = conn.execute("SELECT id FROM cars WHERE name = 'Auto 3';").fetchone()

    if not (u_vojtech and u_admin and u_pepa and c1 and c2 and c3):
        raise RuntimeError("Seed selhal: nenašel se user/car po INSERTu.")

    # Aby se rides neduplikovaly při každém spuštění, vložíme je jen pokud
    # v tabulce rides zatím nejsou žádná data.
    rides_count = conn.execute("SELECT COUNT(*) AS n FROM rides;").fetchone()["n"]
    if rides_count == 0:
        # 2 dokončené jízdy + 1 nedokončená (duration_sec = NULL)
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, ?);",
            (int(u_vojtech["id"]), int(c1["id"]), 120),
        )
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, ?);",
            (int(u_admin["id"]), int(c2["id"]), 75),
        )
        conn.execute(
            "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, NULL);",
            (int(u_pepa["id"]), int(c3["id"])),
        )


def main() -> None:
    DB_DIR.mkdir(exist_ok=True)

    conn = connect()
    apply_schema(conn)
    seed_data(conn)
    conn.commit()
    conn.close()

    print("✅ DB vytvořena/aktualizována:", DB_PATH)
    print("✅ Vložena demo data (3 users, 3 cars, 3 rides).")
    print("Demo login:")
    print("- vojtěch: username=vojtech, heslo=Vojtech123")
    print("- admin:   username=admin,   heslo=Admin123")
    print("- pepa:    username=pepa,    heslo=Pepa123")


if __name__ == "__main__":
    main()