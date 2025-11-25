import sqlite3
import os

# 🗃️ Cesta k databázi
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'database.db')

# ✅ Pokud složka 'data' neexistuje, vytvoříme ji
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

# 🧩 Spojení s databází
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 📝 Vytvoření tabulky uživatelů
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL
)
''')

# 📝 Vytvoření tabulky pro leaderboard
cursor.execute('''
CREATE TABLE IF NOT EXISTS leaderboard (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    score INTEGER DEFAULT 0
)
''')

# 💾 Uložení změn a zavření spojení
conn.commit()
conn.close()

print("✅ Databáze byla vytvořena nebo již existuje.")
