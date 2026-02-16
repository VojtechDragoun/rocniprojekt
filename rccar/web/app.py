"""
app.py – Flask backend pro projekt RCcar
======================================

Navíc oproti základní verzi:
- /admin stránka (jen pro admina)
- admin vidí tabulky users + rides
- admin může mazat:
  - jízdy (DELETE ride)
  - uživatele (DELETE user) -> smaže i jeho jízdy díky ON DELETE CASCADE

Bezpečnost:
- Mazání děláme přes POST (ne přes GET).
- Route /admin* je chráněná admin_required().
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
# CESTY
# ---------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent          # web/
PROJECT_ROOT = BASE_DIR.parent                      # rccar/
DB_PATH = PROJECT_ROOT / "database" / "rccar.db"    # rccar/database/rccar.db


# ---------------------------------------------------------------------
# FLASK APP
# ---------------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"


# ---------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------
def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """
    Vytvoří tabulky, pokud neexistují (safe).
    Pokud už tabulky máš, nic to nepřepíše.
    """
    conn = get_db_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role          TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin')),
            created_at    TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS rides (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            duration_sec INTEGER NOT NULL CHECK(duration_sec >= 0),
            created_at   TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);
    """)
    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------
# AUTH HELPERY
# ---------------------------------------------------------------------
def current_user() -> Optional[Dict[str, Any]]:
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
# ROUTES – veřejné stránky
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

    flash("Registrace proběhla úspěšně. Teď se přihlas.", "success")
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

    # schválně jedna hláška pro obě chyby (bezpečnější)
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
# ADMIN – zobrazení DB + mazání
# ---------------------------------------------------------------------
@app.route("/admin")
def admin():
    """
    Admin dashboard:
    - jen admin
    - ukáže:
      - seznam users
      - seznam rides (včetně username)
    """
    if not admin_required():
        abort(403)

    conn = get_db_connection()

    users_rows = conn.execute("""
        SELECT id, username, role, created_at
        FROM users
        ORDER BY id ASC;
    """).fetchall()

    rides_rows = conn.execute("""
        SELECT
            rides.id,
            rides.user_id,
            users.username AS username,
            rides.duration_sec,
            rides.created_at
        FROM rides
        JOIN users ON users.id = rides.user_id
        ORDER BY rides.created_at DESC;
    """).fetchall()

    conn.close()

    users = [dict(r) for r in users_rows]
    rides = [dict(r) for r in rides_rows]

    return render_template(
        "admin.html",
        user=current_user(),
        users=users,
        rides=rides,
    )


@app.route("/admin/ride/<int:ride_id>/delete", methods=["POST"])
def admin_delete_ride(ride_id: int):
    """
    Smaže konkrétní jízdu podle ID.
    """
    if not admin_required():
        abort(403)

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM rides WHERE id = ?", (ride_id,))
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        flash("Jízda nenalezena (nic se nesmazalo).", "error")
    else:
        flash(f"Jízda ID {ride_id} smazána.", "success")

    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id: int):
    """
    Smaže uživatele podle ID.
    Díky ON DELETE CASCADE se smažou i jeho jízdy.
    """
    if not admin_required():
        abort(403)

    # ochrana: admin si nesmaže svůj vlastní účet omylem
    if session.get("user_id") == user_id:
        flash("Nemůžeš smazat sám sebe (přihlášený admin účet).", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    if cur.rowcount == 0:
        flash("Uživatel nenalezen (nic se nesmazalo).", "error")
    else:
        flash(f"Uživatel ID {user_id} smazán (a jeho jízdy taky).", "success")

    return redirect(url_for("admin"))


# ---------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
