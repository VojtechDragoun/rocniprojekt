"""
database/init_db.py
===================

Jednorázový skript na vytvoření SQLite databáze a tabulek (users + rides).

Použití (z rootu projektu rccar/):
    python database\\init_db.py

Co udělá:
- vytvoří soubor database/rccar.db (pokud neexistuje)
- načte a spustí SQL ze souboru database/schema.sql
"""

from pathlib import Path
import sqlite3


def main() -> None:
    # Cesty:
    # init_db.py je v rccar/database/
    # projekt root je tedy o úroveň výš
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "database" / "rccar.db"
    schema_path = project_root / "database" / "schema.sql"

    # Kontrola, že schema.sql existuje
    if not schema_path.exists():
        raise FileNotFoundError(f"Chybí soubor: {schema_path}")

    # Načtení schématu jako text
    schema_sql = schema_path.read_text(encoding="utf-8")

    # Připojení k DB (soubor se vytvoří automaticky, pokud ještě neexistuje)
    conn = sqlite3.connect(db_path)

    # V SQLite musí být FK zapnuté zvlášť pro každé spojení
    conn.execute("PRAGMA foreign_keys = ON;")

    # executescript umí spustit více SQL příkazů najednou
    conn.executescript(schema_sql)

    conn.commit()
    conn.close()

    print(f"[OK] Databáze připravena: {db_path}")


if __name__ == "__main__":
    main()
