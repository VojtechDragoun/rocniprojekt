from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import os

# 🧩 Inicializace Flask aplikace
app = Flask(__name__)
app.secret_key = 'tajny_klic'  # nutné pro práci se session a flash zprávami

# 🗃️ Cesta k databázi
DB_PATH = os.path.join(os.path.dirname(__file__), 'data', 'database.db')


# 📘 Pomocná funkce – spojení s databází
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # výsledky jako slovník (přístup přes názvy sloupců)
    return conn


# 🏠 Hlavní stránka
@app.route('/')
def index():
    return render_template('index.html')


# ℹ️ Stránka s informacemi o hře
@app.route('/info')
def info():
    return render_template('info.html')


# 🧮 Žebříček (výsledky z databáze)
@app.route('/leaderboard')
def leaderboard():
    conn = get_db_connection()
    scores = conn.execute('SELECT username, score FROM leaderboard ORDER BY score DESC').fetchall()
    conn.close()
    return render_template('leaderboard.html', scores=scores)


# 🔑 Přihlášení
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        heslo = request.form['heslo']

        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, heslo)).fetchone()
        conn.close()

        if user:
            session['user'] = user['username']
            flash('Přihlášení proběhlo úspěšně!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Špatný e-mail nebo heslo.', 'error')

    return render_template('login.html')


# 📝 Registrace
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        heslo = request.form['heslo']

        conn = get_db_connection()
        # kontrola, zda už existuje účet se stejným e-mailem
        existing = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            flash('Tento e-mail je již registrován.', 'error')
        else:
            conn.execute('INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                         (username, email, heslo))
            conn.commit()
            flash('Registrace proběhla úspěšně! Nyní se přihlaš.', 'success')
        conn.close()
        return redirect(url_for('login'))

    return render_template('registrace.html')


# 🚪 Odhlášení
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Byl jsi odhlášen.', 'info')
    return redirect(url_for('index'))


# ⚙️ Inicializace databáze (pokud neexistuje)
def init_db():
    if not os.path.exists(DB_PATH):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        conn = get_db_connection()
        conn.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )''')
        conn.execute('''
        CREATE TABLE leaderboard (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            score INTEGER DEFAULT 0
        )''')
        conn.commit()
        conn.close()
        print("✅ Databáze byla vytvořena.")


# ▶️ Spuštění aplikace
if __name__ == '__main__':
    init_db()
    app.run(debug=True)
