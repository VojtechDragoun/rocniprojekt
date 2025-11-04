from flask import Flask, render_template, request, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = "tajnyklic"  # pro flash zprávy

# 🧱 Cesta k databázi
DB_CESTA = os.path.join("data", "uzivatele.db")

# 🛠️ Funkce pro inicializaci databáze
def init_db():
    if not os.path.exists("data"):
        os.makedirs("data")
    conn = sqlite3.connect(DB_CESTA)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS uzivatele (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            prezdivka TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            heslo TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    print("✅ Databáze připravena:", DB_CESTA)

# 🧍‍♂️ Registrace uživatele
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        prezdivka = request.form["prezdivka"]
        email = request.form["email"]
        heslo = request.form["heslo"]

        if not prezdivka or not email or not heslo:
            flash("Vyplň všechna pole!", "error")
            return redirect(url_for("register"))

        conn = sqlite3.connect(DB_CESTA)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO uzivatele (prezdivka, email, heslo) VALUES (?, ?, ?)",
                      (prezdivka, email, heslo))
            conn.commit()
            flash("Registrace proběhla úspěšně!", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Tento e-mail je již zaregistrován!", "error")
            return redirect(url_for("register"))
        finally:
            conn.close()
    return render_template("register.html")

# 🔐 Přihlášení uživatele
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        heslo = request.form["heslo"]

        conn = sqlite3.connect(DB_CESTA)
        c = conn.cursor()
        c.execute("SELECT * FROM uzivatele WHERE email = ? AND heslo = ?", (email, heslo))
        user = c.fetchone()
        conn.close()

        if user:
            flash(f"Vítej zpět, {user[1]}!", "success")
            return redirect(url_for("login"))
        else:
            flash("Nesprávný e-mail nebo heslo!", "error")
            return redirect(url_for("login"))
    return render_template("login.html")

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
