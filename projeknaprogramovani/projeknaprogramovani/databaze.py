import sqlite3
import os

def init_db():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    slozka = os.path.join(BASE_DIR, "data")
    os.makedirs(slozka, exist_ok=True)
    cesta = os.path.join(slozka, "uzivatele.db")

    conn = sqlite3.connect(cesta)
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS uzivatele (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        heslo TEXT NOT NULL
    )
    ''')
    conn.commit()
    conn.close()
    return cesta
