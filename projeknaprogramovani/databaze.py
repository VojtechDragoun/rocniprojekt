import sqlite3

def vytvor_databazi():
    # Připojení k databázi (vytvoří soubor data.db, pokud ještě neexistuje)
    conn = sqlite3.connect("data.db")

    # Vytvoření kurzoru pro provádění SQL příkazů
    cursor = conn.cursor()

    # Vytvoření tabulky "uzivatele", pokud ještě neexistuje
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS uzivatele (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   -- automatické ID
        jmeno TEXT NOT NULL,                    -- uživatelské jméno
        heslo TEXT NOT NULL                     -- heslo (zatím jako prostý text)
    )
    """)

    # Uložení změn
    conn.commit()

    # Zavření spojení
    conn.close()

    print("✅ Databáze 'data.db' a tabulka 'uzivatele' byla vytvořena!")

# Spustí se jen pokud je soubor spuštěn přímo
if __name__ == "__main__":
    vytvor_databazi()
