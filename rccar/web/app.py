"""
app.py – Flask backend pro RCcar (Vojtěch)
=========================================

Umí:
- Stránky: index, info, register, login, dashboard, admin
- Autentizace: session (login/logout)
- DB: users + rides (admin vidí vše, user jen svoje)
- API: /api/control (jen pro přihlášené) -> pošle příkaz do Arduino (servo)

Struktura projektu:
rccar/
  database/
    rccar.db
    schema.sql
  web/
    app.py
    arduino_comm.py
    templates/
    static/
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
    jsonify,
)

from werkzeug.security import generate_password_hash, check_password_hash

# Serial bridge (pyserial) – musí existovat soubor web/arduino_comm.py
import arduino_comm


# ---------------------------------------------------------------------
# 1) CESTY
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent          # .../rccar/web
PROJECT_ROOT = BASE_DIR.parent                      # .../rccar
DB_PATH = PROJECT_ROOT / "database" / "rccar.db"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"


# ---------------------------------------------------------------------
# 2) FLASK APP
# ---------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")

# Pro session cookie (podepisování) – v reálu do env, tady natvrdo OK
app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"


# ---------------------------------------------------------------------
# 3) DB HELPERY
# ---------------------------------------------------------------------
def get_db_connection() -> sqlite3.Connection:
    """
    Otevře SQLite spojení.
    DŮLEŽITÉ: SQLite má foreign keys defaultně vypnuté -> zapneme PRAGMA.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """
    Vytvoří tabulky ze schema.sql (pokud neexistují).
    schema.sql je zdroj pravdy.
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Chybí schema.sql: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = get_db_connection()
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


# vytvoří tabulky při startu serveru
init_db()


# ---------------------------------------------------------------------
# 4) AUTH HELPERY
# ---------------------------------------------------------------------
def current_user() -> Optional[Dict[str, Any]]:
    """Vrátí dict o přihlášeném uživateli nebo None."""
    if "user_id" not in session:
        return None
    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
    }


def login_required() -> bool:
    return "user_id" in session


def admin_required() -> bool:
    return login_required() and session.get("role") == "admin"


# ---------------------------------------------------------------------
# 5) ROUTES – PAGES
# ---------------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", user=current_user())


@app.route("/info")
def info():
    return render_template("info.html", user=current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html", user=current_user())

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "user").strip().lower()

    if not username or not password:
        flash("Vyplň uživatelské jméno i heslo.", "error")
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
        flash("Uživatel s tímto jménem už existuje.", "error")
        return redirect(url_for("register"))

    flash("Registrace OK. Teď se přihlas.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html", user=current_user())

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    # jedna společná hláška (bezpečnější)
    if row is None or not check_password_hash(row["password_hash"], password):
        flash("Špatné uživatelské jméno nebo heslo.", "error")
        return redirect(url_for("login"))

    session["user_id"] = row["id"]
    session["username"] = row["username"]
    session["role"] = row["role"]

    flash(f"Přihlášen jako {row['username']}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Odhlášeno.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
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


@app.route("/ride/add_demo")
def add_demo_ride():
    if not login_required():
        flash("Nejdřív se přihlas.", "error")
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
# 6) ADMIN (volitelné)
# ---------------------------------------------------------------------
@app.route("/admin")
def admin():
    if not admin_required():
        abort(403)

    conn = get_db_connection()
    users_rows = conn.execute("SELECT id, username, role, created_at FROM users ORDER BY id;").fetchall()
    rides_rows = conn.execute("""
        SELECT rides.id, rides.user_id, users.username AS username, rides.duration_sec, rides.created_at
        FROM rides
        JOIN users ON users.id = rides.user_id
        ORDER BY rides.created_at DESC;
    """).fetchall()
    conn.close()

    return render_template(
        "admin.html",
        user=current_user(),
        users=[dict(u) for u in users_rows],
        rides=[dict(r) for r in rides_rows],
    )


@app.route("/admin/ride/<int:ride_id>/delete", methods=["POST"])
def admin_delete_ride(ride_id: int):
    if not admin_required():
        abort(403)

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM rides WHERE id = ?", (ride_id,))
    conn.commit()
    conn.close()

    flash("Jízda smazána." if cur.rowcount else "Jízda nenalezena.", "success" if cur.rowcount else "error")
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id: int):
    if not admin_required():
        abort(403)

    # zabrání adminovi smazat sám sebe
    if session.get("user_id") == user_id:
        flash("Nemůžeš smazat sám sebe.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("Uživatel smazán." if cur.rowcount else "Uživatel nenalezen.", "success" if cur.rowcount else "error")
    return redirect(url_for("admin"))


# ---------------------------------------------------------------------
# 7) API – OVLÁDÁNÍ SERVA (A/D drž, pust = střed)
# ---------------------------------------------------------------------
@app.route("/api/control", methods=["POST"])
def api_control():
    """
    Přijme { "cmd": "STEER:L" } a pošle to přes serial do Arduino.

    Bezpečnost:
    - jen přihlášený
    - povolíme jen konkrétní příkazy
    """
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()

    allowed = {"STEER:L", "STEER:R", "STEER:C"}
    if cmd not in allowed:
        return jsonify({"error": "Command not allowed"}), 400

    try:
        arduino_comm.send_line(cmd)
    except Exception as e:
        return jsonify({"error": f"Arduino send failed: {e}"}), 500

    return jsonify({"ok": True, "sent": cmd})


# ---------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)