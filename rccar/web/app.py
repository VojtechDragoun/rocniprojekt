"""
app.py – Flask backend pro projekt RCcar
======================================

Struktura projektu (dle tvého screenshotu):
rccar/
  database/
    rccar.db
    schema.sql
  web/
    app.py
    templates/
    static/

Co backend umí:
- renderuje stránky z /web/templates (Jinja2)
- servíruje CSS ze /web/static (např. /static/style.css)
- registrace / login / logout přes session
- ukládání jízd (rides) k uživateli (users) => vztah 1 : N
- dashboard:
  - běžný user vidí jen svoje jízdy
  - admin vidí všechny jízdy

DŮLEŽITÉ:
- SQLite má foreign keys vypnuté defaultně => musíme zapnout PRAGMA foreign_keys=ON
- Schéma DB bereme ze souboru database/schema.sql (zdroj pravdy)
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
    abort,
)
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------
# 1) CESTY K PROJEKTU + DB
# ---------------------------------------------------------------------

# web/ (tam kde je app.py)
BASE_DIR = Path(__file__).resolve().parent

# rccar/ (o úroveň výš)
PROJECT_ROOT = BASE_DIR.parent

# database/
DB_DIR = PROJECT_ROOT / "database"
DB_DIR.mkdir(exist_ok=True)

# database/rccar.db (reálná SQLite databáze)
DB_PATH = DB_DIR / "rccar.db"

# database/schema.sql (SQL skript se schématem – zdroj pravdy)
SCHEMA_PATH = DB_DIR / "schema.sql"


# ---------------------------------------------------------------------
# 2) FLASK APP (templates + static)
# ---------------------------------------------------------------------

# template_folder necháváme default ("templates") vedle app.py
# static_folder nastavujeme na "static" (vedle app.py)
# static_url_path="/static" => CSS bude na /static/style.css
app = Flask(
    __name__,
    static_folder="static",
    static_url_path="/static",
)

# Secret key:
# - nutné pro session (Flask podepisuje cookie)
# - pro školní projekt OK natvrdo, v reálu do ENV proměnných
app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"


# ---------------------------------------------------------------------
# 3) DB HELPERY
# ---------------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    """
    Vytvoří nové připojení k SQLite databázi.

    DŮLEŽITÉ PRO SQLITE:
    - foreign_keys jsou defaultně OFF, takže FK pravidla nefungují,
      dokud nezapneš: PRAGMA foreign_keys = ON
    - tohle je potřeba udělat pro každé nové připojení

    row_factory = sqlite3.Row:
    - výsledky SELECTu budou "dict-like", takže row["username"] funguje
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """
    Inicializace DB.

    Místo vytváření tabulek natvrdo v Pythonu používáme schema.sql,
    aby se ti časem nerozjel SQL soubor a Python kód.

    schema.sql typicky obsahuje:
    - CREATE TABLE users (...)
    - CREATE TABLE rides (...)
    - indexy, check constrainty atd.
    """
    if not SCHEMA_PATH.exists():
        # Když schema.sql chybí, radši to hned řekneme
        # (jinak by se aplikace chovala nejasně)
        raise FileNotFoundError(f"Chybí soubor schématu DB: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = get_db_connection()
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


# Zavoláme při startu serveru (vytvoří tabulky pokud nejsou)
init_db()


# ---------------------------------------------------------------------
# 4) AUTH HELPERY
# ---------------------------------------------------------------------

def current_user() -> Optional[Dict[str, Any]]:
    """
    Vrátí informace o přihlášeném uživateli ze session,
    nebo None pokud nikdo přihlášený není.
    """
    if "user_id" not in session:
        return None

    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
    }


def login_required() -> bool:
    """True pokud je uživatel přihlášený."""
    return "user_id" in session


def admin_required() -> bool:
    """True pokud je přihlášený admin."""
    return login_required() and session.get("role") == "admin"


# ---------------------------------------------------------------------
# 5) ROUTES – STRÁNKY
# ---------------------------------------------------------------------

@app.route("/")
def index():
    """Hlavní stránka."""
    return render_template("index.html", user=current_user())


@app.route("/info")
def info():
    """Info stránka."""
    return render_template("info.html", user=current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registrace.

    GET: zobrazí formulář
    POST: uloží uživatele do DB (heslo jako hash) a přesměruje na login
    """
    if request.method == "GET":
        return render_template("register.html", user=current_user())

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "").strip().lower()

    # Validace vstupu
    if not username or not password or not role:
        flash("Vyplň všechna pole.", "error")
        return redirect(url_for("register"))

    if role not in ("user", "admin"):
        flash("Role musí být 'user' nebo 'admin'.", "error")
        return redirect(url_for("register"))

    password_hash = generate_password_hash(password)

    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        # Typicky: username už existuje (UNIQUE)
        flash("Uživatel s tímto jménem už existuje.", "error")
        return redirect(url_for("register"))

    flash("Registrace proběhla úspěšně. Teď se přihlas.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login.

    GET: zobrazí formulář
    POST:
      - načte uživatele z DB
      - ověří heslo
      - uloží do session (user_id, username, role)
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

    if not check_password_hash(user_row["password_hash"], password):
        flash("Špatné heslo.", "error")
        return redirect(url_for("login"))

    # Uložení přihlášení do session cookie
    session["user_id"] = user_row["id"]
    session["username"] = user_row["username"]
    session["role"] = user_row["role"]

    flash("Přihlášení OK.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    """Logout = vymazání session."""
    session.clear()
    flash("Odhlášeno.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    """
    Dashboard: výpis jízd.

    Bez přihlášení -> redirect na login.
    Admin vidí všechny jízdy.
    User vidí jen svoje (WHERE rides.user_id = session["user_id"]).
    """
    if not login_required():
        flash("Nejdřív se přihlas.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()

    if admin_required():
        rows = conn.execute("""
            SELECT
                rides.id,
                users.username AS username,
                rides.duration_sec AS duration_sec,
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
                rides.duration_sec AS duration_sec,
                rides.created_at AS created_at
            FROM rides
            JOIN users ON users.id = rides.user_id
            WHERE rides.user_id = ?
            ORDER BY rides.created_at DESC;
        """, (session["user_id"],)).fetchall()

    conn.close()

    rides: List[Dict[str, Any]] = [dict(r) for r in rows]
    return render_template("dashboard.html", rides=rides, user=current_user())


@app.route("/admin")
def admin():
    """
    Volitelná admin stránka.
    Pokud ji nechceš, můžeš route i admin.html klidně smazat.
    """
    if not admin_required():
        abort(403)  # Forbidden
    return render_template("admin.html", user=current_user())


@app.route("/ride/add_demo")
def add_demo_ride():
    """
    Testovací route pro rychlé ověření DB + dashboardu.
    Přidá přihlášenému uživateli jednu jízdu (např. 120 sekund).

    Pozn.: používáme duration_sec (stejný název jako ve schema.sql)
    """
    if not login_required():
        flash("Nejdřív se přihlas, ať víme komu jízdu uložit.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO rides (user_id, duration_sec) VALUES (?, ?)",
        (session["user_id"], 120),
    )
    conn.commit()
    conn.close()

    flash("Demo jízda přidána (120 s).", "success")
    return redirect(url_for("dashboard"))


# ---------------------------------------------------------------------
# 6) RUN
# ---------------------------------------------------------------------
if __name__ == "__main__":
    """
    Spuštění:
      cd web
      python app.py

    debug=True:
      - auto reload při změně kódu
      - detailní error page
    """
    app.run(debug=True, host="0.0.0.0", port=5000)
