"""
app.py (Flask backend) pro projekt RCcar
======================================

Cíl:
- Obsloužit HTML šablony v /web/templates
- Obsloužit statické soubory (CSS) v /web/static_css
- Přidat jednoduché přihlášení/registraci (uživatel/admin)
- Ukládat a číst data o jízdách ze SQLite databáze

Poznámky k tvé struktuře projektu (dle screenshotu):
- web/
  - app.py                <-- tento soubor
  - templates/            <-- HTML šablony
  - static_css/style.css  <-- společný CSS

Protože CSS není ve výchozí složce 'static', nastavíme Flasku:
- static_folder="static_css"
- static_url_path="/static"
Tím pádem bude url_for('static', filename='style.css') fungovat správně.

Databáze:
- Uložíme ji do /database/rccar.db (složka database je na stejné úrovni jako web/)
- Použijeme standardní sqlite3 (bez ORM), aby to bylo pro školní projekt srozumitelné.

Bezpečnost:
- Hesla nikdy neukládat jako čistý text -> použijeme hashování (werkzeug.security)
- Přihlášení budeme držet přes Flask session (cookie podepsaná SECRET_KEY)
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------
# 1) Vytvoření Flask aplikace + nastavení cest
# ---------------------------------------------------------------------

# Absolutní cesta ke složce web/ (tam, kde je tento app.py)
BASE_DIR = Path(__file__).resolve().parent

# Projektový root = o úroveň výš (tam máš složku database/)
PROJECT_ROOT = BASE_DIR.parent

# Cesta k databázi (pokud složka database existuje dle screenshotu)
DB_DIR = PROJECT_ROOT / "database"
DB_DIR.mkdir(exist_ok=True)  # když složka neexistuje, vytvoří se

DB_PATH = DB_DIR / "rccar.db"

# Flask aplikace:
# - template_folder necháme default (templates/) -> Flask ji automaticky najde vedle app.py
# - static_folder nastavíme na "static_css", protože tak to máš ve struktuře
# - static_url_path necháme "/static", aby URL vypadaly hezky: /static/style.css
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static",
)

# Secret key je nutný pro session (podepisuje cookie)
# V reálném projektu by byl v .env, tady pro školní projekt stačí natvrdo.
app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"


# ---------------------------------------------------------------------
# 2) Pomocné DB funkce
# ---------------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """
    Vytvoří připojení k SQLite DB.

    row_factory = sqlite3.Row znamená:
    - výsledky SELECTu se budou chovat jako slovník (můžeš psát row["username"])
    - a zároveň funguje i přístup row.keys(), atd.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Vytvoří tabulky, pokud neexistují.

    Tabulka users:
    - id (PK)
    - username (unikátní)
    - password_hash (hash hesla)
    - role (např. 'user' nebo 'admin')

    Tabulka rides:
    - id (PK)
    - user_id (FK na users.id)
    - duration (délka jízdy v sekundách)
    - created_at (datum/čas záznamu, default CURRENT_TIMESTAMP)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL
        );
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rides (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            duration INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)

    conn.commit()
    conn.close()


# Inicializace DB hned při startu aplikace
init_db()


# ---------------------------------------------------------------------
# 3) Autentizace: pomocné funkce + "decorators"
# ---------------------------------------------------------------------

def current_user() -> Optional[Dict[str, Any]]:
    """
    Vrátí slovník s informacemi o přihlášeném uživateli,
    nebo None, pokud nikdo přihlášený není.

    Data držíme v session:
    - session["user_id"]
    - session["username"]
    - session["role"]
    """
    if "user_id" not in session:
        return None

    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
    }


def login_required() -> bool:
    """
    Jednoduchý "check" funkce:
    - vrací True pokud je uživatel přihlášen
    - jinak False

    Pro školní projekt je to čitelné.
    (Alternativa je dělat dekorátor @login_required, ale tady to nechávám
     jednoduše, aby ses v tom neztratil.)
    """
    return "user_id" in session


def admin_required() -> bool:
    """
    Vrací True, pokud je přihlášený admin.
    """
    return login_required() and session.get("role") == "admin"


# ---------------------------------------------------------------------
# 4) Routy (stránky)
# ---------------------------------------------------------------------

@app.route("/")
def index():
    """
    Hlavní stránka.
    Jen renderuje templates/index.html
    """
    return render_template("index.html", user=current_user())


@app.route("/info")
def info():
    """
    Info stránka projektu.
    """
    return render_template("info.html", user=current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registrace uživatele/admina.

    GET:
      - zobrazí formulář

    POST:
      - vezme data z formuláře
      - zkontroluje základní validaci
      - uloží uživatele do DB (heslo uloží jako hash)
      - přesměruje na login
    """
    if request.method == "GET":
        return render_template("register.html", user=current_user())

    # ---------------------------
    # POST - čtení formuláře
    # ---------------------------
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "").strip().lower()

    # ---------------------------
    # Základní validace
    # ---------------------------
    if not username or not password or not role:
        flash("Vyplň všechna pole.", "error")
        return redirect(url_for("register"))

    if role not in ("user", "admin"):
        # Pro školní projekt můžeš povolit jen tyto dvě role,
        # ať je to jasné a kontrolované.
        flash("Role musí být 'user' nebo 'admin'.", "error")
        return redirect(url_for("register"))

    # Hash hesla (nikdy neukládat heslo jako text)
    password_hash = generate_password_hash(password)

    # ---------------------------
    # Uložení do DB
    # ---------------------------
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        # IntegrityError typicky znamená porušení UNIQUE (username už existuje)
        flash("Uživatel s tímto jménem už existuje.", "error")
        return redirect(url_for("register"))

    flash("Registrace proběhla úspěšně. Teď se přihlas.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Přihlášení.

    GET:
      - zobrazí formulář

    POST:
      - ověří username + password
      - pokud sedí, uloží do session user_id/username/role
      - přesměruje na dashboard
    """
    if request.method == "GET":
        return render_template("login.html", user=current_user())

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    user_row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    if user_row is None:
        flash("Uživatel neexistuje.", "error")
        return redirect(url_for("login"))

    # Ověření hesla proti uloženému hashi
    if not check_password_hash(user_row["password_hash"], password):
        flash("Špatné heslo.", "error")
        return redirect(url_for("login"))

    # Pokud je vše OK, uložíme do session info o uživateli
    session["user_id"] = user_row["id"]
    session["username"] = user_row["username"]
    session["role"] = user_row["role"]

    flash("Přihlášení OK.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    """
    Odhlášení:
    - smažeme session (uživatel je pak "anonymní")
    """
    session.clear()
    flash("Odhlášeno.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    """
    Dashboard – historie jízd z DB.

    Aby to dávalo smysl, typicky chceš, aby dashboard viděl jen přihlášený uživatel.
    Takže:
    - pokud není přihlášen -> přesměruj na login

    Data posíláme do dashboard.html jako "rides".

    POZOR:
    Tvoje šablona dashboard.html z mého předchozího návrhu očekává:
      r.username, r.duration, r.created_at
    Proto v SELECTu děláme JOIN users + rides a aliasujeme sloupce.
    """
    if not login_required():
        flash("Nejdřív se přihlas.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()

    # Pokud chceš:
    # - admin vidí všechny jízdy
    # - user vidí jen svoje jízdy
    if admin_required():
        rows = conn.execute("""
            SELECT
                rides.id,
                users.username AS username,
                rides.duration AS duration,
                rides.created_at AS created_at
            FROM rides
            JOIN users ON users.id = rides.user_id
            ORDER BY rides.created_at DESC;
        """).fetchall()
    else:
        rows = conn.execute("""
            SELECT
                rides.id,
                users.username AS username,
                rides.duration AS duration,
                rides.created_at AS created_at
            FROM rides
            JOIN users ON users.id = rides.user_id
            WHERE rides.user_id = ?
            ORDER BY rides.created_at DESC;
        """, (session["user_id"],)).fetchall()

    conn.close()

    # Převedeme sqlite3.Row na "objekt-like" strukturu, aby šablona mohla psát r.username
    # Nejjednodušší je použít dict, ale v Jinja jde i dict přístup přes tečku.
    rides: List[Dict[str, Any]] = [dict(r) for r in rows]

    return render_template("dashboard.html", rides=rides, user=current_user())


# ---------------------------------------------------------------------
# 5) Testovací route – vytvoření jízdy (jen pro demo / vývoj)
# ---------------------------------------------------------------------
@app.route("/ride/add_demo")
def add_demo_ride():
    """
    Tohle je pomocná route, aby sis mohl rychle "naklikat" testovací data do DB.

    - musíš být přihlášen
    - vloží se jedna demo jízda (např. duration 120s)
    - pak tě to hodí na dashboard

    Až budeš mít reálné ukládání jízd z ovládání autíčka,
    tuhle route klidně smažeš.
    """
    if not login_required():
        flash("Nejdřív se přihlas, ať víme komu jízdu uložit.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO rides (user_id, duration) VALUES (?, ?)",
        (session["user_id"], 120),
    )
    conn.commit()
    conn.close()

    flash("Demo jízda přidána (120s).", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------
# 6) Spuštění aplikace
# ---------------------------------------------------------------------
if __name__ == "__main__":
    """
    Spuštění:
      - otevři terminál ve složce web/
      - python app.py

    debug=True:
      - auto reload při změně kódu
      - detailní error page
    host="0.0.0.0":
      - aplikace dostupná i z jiné IP v síti (užitečné při testu na mobilu/ESP32)
    """
    app.run(debug=True, host="0.0.0.0", port=5000)
