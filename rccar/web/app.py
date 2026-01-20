"""
app.py – Flask backend pro projekt RCcar
======================================

Tento soubor je "server" části projektu.
Spouštíš ho příkazem:  python app.py
a Flask pak obsluhuje webové stránky na: http://localhost:5000/

Co tento backend umí:
1) Vrací (renderuje) HTML šablony z /templates
   - index.html, info.html, login.html, register.html, dashboard.html
2) Servíruje statické soubory (CSS) ze složky /static
   - například style.css je dostupný na URL: /static/style.css
3) Uživatelé:
   - registrace (uložení do DB)
   - login (ověření z DB + uložení do session)
   - logout (vymazání session)
4) Databáze SQLite:
   - tabulka users: uživatelé
   - tabulka rides: jízdy (doba jízdy + datum + vazba na uživatele)
5) Dashboard:
   - přístup jen pro přihlášené (autentizace)
   - admin vidí všechny jízdy, user vidí jen svoje (autorizace)

Poznámka k bezpečnosti:
- Heslo nikdy neukládáme jako text.
- Ukládáme jen HASH hesla (nevratná "otisk" funkce).
"""

from __future__ import annotations  # umožní psát typy "dopředu" (není nutné, ale užitečné)

import sqlite3  # standardní knihovna pro SQLite databázi (bez ORM)
from pathlib import Path  # práce s cestami je tu bezpečnější než stringy
from typing import Any, Dict, List, Optional  # typová nápověda (lepší čitelnost)

# Flask:
# - Flask: hlavní objekt aplikace
# - render_template: vezme HTML ze /templates a doplní do něj data (Jinja2)
# - request: čtení dat z formulářů (POST)
# - redirect + url_for: přesměrování na jinou stránku
# - session: uložení stavu přihlášení (cookie)
# - flash: krátké zprávy pro uživatele ("OK" / "error")
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
)

# Werkzeug je knihovna, která Flask používá interně.
# generate_password_hash -> udělá hash hesla
# check_password_hash -> ověří heslo proti uloženému hashi
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------
# 1) Vytvoření Flask aplikace + nastavení cest
# ---------------------------------------------------------------------

# BASE_DIR = cesta ke složce, kde leží tento app.py (tedy /web)
BASE_DIR = Path(__file__).resolve().parent

# PROJECT_ROOT = složka o úroveň výš (např. /rccar)
# tím se dostaneme k /database, i když je mimo web složku
PROJECT_ROOT = BASE_DIR.parent

# DB_DIR = cesta na složku database/
DB_DIR = PROJECT_ROOT / "database"

# mkdir(exist_ok=True):
# - když složka neexistuje, vytvoří ji
# - když existuje, nic se nestane (bez erroru)
DB_DIR.mkdir(exist_ok=True)

# DB_PATH = konkrétní soubor databáze
DB_PATH = DB_DIR / "rccar.db"


# Flask aplikace
# ==============
# Defaultně Flask hledá:
# - šablony v /templates (vedle app.py)
# - statické soubory ve /static (vedle app.py)
#
# Ty explicitně nastavuješ:
# static_folder="static"
# static_url_path="/static"
#
# To znamená:
# - soubory v web/static/ budou dostupné přes URL /static/
# - např. web/static/style.css => /static/style.css
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static",
)

# SECRET_KEY je důležitý:
# - Flask podepisuje session cookie (aby ji uživatel nemohl snadno měnit)
# V reálném projektu to patří do .env (tajné).
app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"


# ---------------------------------------------------------------------
# 2) Pomocné DB funkce (SQLite)
# ---------------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """
    Vytvoří nové připojení k databázi.

    Proč to děláme jako funkci:
    - nechceme mít jedno spojení "napořád"
    - pro každý request se často otevře spojení, provede dotaz a zavře

    row_factory = sqlite3.Row:
    - výsledky SELECTu jsou přístupné jako slovník:
        row["username"], row["role"], ...
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """
    Inicializace DB = vytvoření tabulek, pokud ještě neexistují.

    Tabulka users:
    - id: primární klíč (autoincrement)
    - username: unikátní jméno (nesmí se opakovat)
    - password_hash: hash hesla (ne heslo!)
    - role: 'user' nebo 'admin'

    Tabulka rides:
    - id: primární klíč
    - user_id: cizí klíč na users.id (vazba jízdy na uživatele)
    - duration: délka jízdy v sekundách (INTEGER)
    - created_at: datum/čas vytvoření záznamu (automaticky)
    """
    conn = get_db_connection()
    cur = conn.cursor()

    # CREATE TABLE IF NOT EXISTS:
    # - tabulka se vytvoří jen pokud zatím není v DB
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

    conn.commit()  # potvrzení změn
    conn.close()   # zavření spojení


# Zavoláme init_db hned při startu serveru,
# aby DB existovala ještě před prvním requestem
init_db()


# ---------------------------------------------------------------------
# 3) Autentizace (login/register) – pomocné funkce
# ---------------------------------------------------------------------

def current_user() -> Optional[Dict[str, Any]]:
    """
    Vrátí informace o přihlášeném uživateli (ze session),
    nebo None, pokud nikdo přihlášený není.

    Session je cookie na straně klienta, kterou Flask podepisuje.
    Do session ukládáme:
    - user_id (ID v DB)
    - username
    - role
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
    Jednoduchá kontrola přihlášení.
    - True: uživatel je přihlášen
    - False: uživatel není přihlášen
    """
    return "user_id" in session


def admin_required() -> bool:
    """
    Kontrola admin práv.
    - musí být přihlášen a role musí být 'admin'
    """
    return login_required() and session.get("role") == "admin"


# ---------------------------------------------------------------------
# 4) ROUTY (URL endpointy)
# ---------------------------------------------------------------------
# Route = URL adresa, kterou backend obsluhuje.
# Např. @app.route("/") znamená:
# - když uživatel otevře http://localhost:5000/
# - spustí se funkce index()

@app.route("/")
def index():
    """
    Hlavní stránka / (index)
    - jen renderuje HTML šablonu index.html
    - do šablony posíláme user=current_user()
      => šablona může vědět, jestli je uživatel přihlášený
    """
    return render_template("index.html", user=current_user())


@app.route("/info")
def info():
    """
    Info stránka
    """
    return render_template("info.html", user=current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registrace uživatele.

    GET:
      - zobrazí registrační formulář

    POST:
      - přečte data z formuláře
      - zvaliduje je
      - uloží uživatele do DB
      - přesměruje na login
    """
    if request.method == "GET":
        return render_template("register.html", user=current_user())

    # ---------- POST (odeslání formuláře) ----------
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "").strip().lower()

    # Základní validace:
    if not username or not password or not role:
        flash("Vyplň všechna pole.", "error")
        return redirect(url_for("register"))

    # Povolené role (jednoduché RBAC - role based access control)
    if role not in ("user", "admin"):
        flash("Role musí být 'user' nebo 'admin'.", "error")
        return redirect(url_for("register"))

    # Hash hesla:
    # - uloží se do DB (heslo v čistém textu nikdy!)
    password_hash = generate_password_hash(password)

    # Uložení do DB
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        # IntegrityError často znamená: username už existuje (UNIQUE constraint)
        flash("Uživatel s tímto jménem už existuje.", "error")
        return redirect(url_for("register"))

    flash("Registrace proběhla úspěšně. Teď se přihlas.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login.

    GET:
      - zobrazí login formulář

    POST:
      - ověří jméno a heslo vůči DB
      - pokud sedí, nastaví session
      - přesměruje na dashboard
    """
    if request.method == "GET":
        return render_template("login.html", user=current_user())

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("login"))

    # Najdeme uživatele v DB podle username:
    conn = get_db_connection()
    user_row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    if user_row is None:
        flash("Uživatel neexistuje.", "error")
        return redirect(url_for("login"))

    # Ověření hesla:
    if not check_password_hash(user_row["password_hash"], password):
        flash("Špatné heslo.", "error")
        return redirect(url_for("login"))

    # Úspěšné přihlášení => session
    session["user_id"] = user_row["id"]
    session["username"] = user_row["username"]
    session["role"] = user_row["role"]

    flash("Přihlášení OK.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    """
    Logout:
    - session.clear() odstraní všechny hodnoty ze session cookie
    - uživatel je opět "nepřihlášen"
    """
    session.clear()
    flash("Odhlášeno.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    """
    Dashboard = stránka se záznamy jízd.

    1) Ochrana:
       - bez přihlášení sem nepustíme
       - pokud user není v session => redirect na login

    2) Načtení dat:
       - admin vidí všechny jízdy
       - user vidí pouze své jízdy

    3) Render:
       - posíláme rides do dashboard.html
    """
    if not login_required():
        flash("Nejdřív se přihlas.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()

    if admin_required():
        # Admin má přístup ke všemu:
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
        # Běžný user vidí pouze svoje:
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

    # Převedeme sqlite3.Row na list dictů,
    # aby se s tím dobře pracovalo v Jinja šabloně
    rides: List[Dict[str, Any]] = [dict(r) for r in rows]

    return render_template("dashboard.html", rides=rides, user=current_user())


@app.route("/ride/add_demo")
def add_demo_ride():
    """
    Pomocná route:
    - vloží demo jízdu (duration 120s) přihlášenému uživateli
    - hodí tě na dashboard

    Používá se pro otestování DB a dashboardu,
    dokud ještě nemáš napojené reálné řízení autíčka.
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
# 5) Spuštění aplikace
# ---------------------------------------------------------------------
if __name__ == "__main__":
    """
    Tento blok se spustí jen když spouštíš soubor přímo:
      python app.py

    debug=True:
      - automatický restart při změně kódu
      - podrobné chybové stránky

    host="0.0.0.0":
      - server poslouchá na všech IP (užitečné, když chceš testovat z mobilu)
    """
    app.run(debug=True, host="0.0.0.0", port=5000)


"""
    render_template(): vezme HTML z templates/ a vyrenderuje ho (Jinja2 doplní proměnné)

    static/: Flask automaticky servíruje statiku (CSS/JS/obrázky) přes /static/...

    session: drží info „uživatel přihlášen / nepřihlášen“, ukládá se do cookie

    flash(): krátké zprávy pro uživatele (success/error)

    hash hesla: bezpečný způsob ukládání hesel

    autentizace: „kdo jsi“ (login)

    autorizace: „co smíš“ (admin vidí vše, user jen své)    
   
   
"""