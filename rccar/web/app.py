"""
RCcar – app.py (Flask backend) – Vojtěch
=======================================

Verze pro DB se 3 tabulkami:
- users
- cars
- rides
(+ sqlite_sequence interně)

Funkce:
- Login / registrace přes SQLite + session
- Dashboard:
  - výběr aktivního auta (dropdown)
  - ovládání serva přes Arduino (Serial) pomocí /api/control
  - start/stop jízdy (zápis do rides)
    - při startu se vytvoří ride se started_at a duration_sec = NULL
    - při stopu se doplní duration_sec
    - při zavření stránky zůstane duration_sec NULL = "nedojel" (OK)
- Admin:
  - přehled users, cars, rides
  - mazání (DELETE) – díky ON DELETE CASCADE se smažou navázané rides

Poznámka k Arduino:
- Import arduino_comm je volitelný (když chybí pyserial, web běží dál)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
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


# ------------------------------------------------------------
# 0) Arduino bridge (volitelný import)
# ------------------------------------------------------------
ARDUINO_AVAILABLE = True
ARDUINO_IMPORT_ERROR = ""
try:
    import arduino_comm  # web/arduino_comm.py
except Exception as e:
    ARDUINO_AVAILABLE = False
    ARDUINO_IMPORT_ERROR = str(e)
    arduino_comm = None  # type: ignore


# ------------------------------------------------------------
# 1) Cesty k DB + schématu
# ------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent          # .../rccar/web
PROJECT_ROOT = BASE_DIR.parent                      # .../rccar
DB_PATH = PROJECT_ROOT / "database" / "rccar.db"
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"


# ------------------------------------------------------------
# 2) Flask app
# ------------------------------------------------------------
app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"


# ------------------------------------------------------------
# 3) DB helpery
# ------------------------------------------------------------
def get_db_connection() -> sqlite3.Connection:
    """
    Otevře připojení k SQLite DB.

    DŮLEŽITÉ: SQLite má FK defaultně vypnuté => zapínáme pro každé spojení.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """
    Aplikuje schema.sql.

    Pozn.: CREATE TABLE IF NOT EXISTS tabulky nepřepisuje.
    Pokud jsi měnil schéma, nejčistší je smazat rccar.db a spustit init_db.py z database/.
    """
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(f"Chybí schema.sql: {SCHEMA_PATH}")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_db_connection()
    conn.executescript(schema_sql)
    conn.commit()
    conn.close()


init_db()


# ------------------------------------------------------------
# 4) Auth helpery
# ------------------------------------------------------------
def current_user() -> Optional[Dict[str, Any]]:
    """Vrátí přihlášeného uživatele ze session, nebo None."""
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


# ------------------------------------------------------------
# 5) Cars helpery (teď už bez user_cars)
# ------------------------------------------------------------
def get_all_cars() -> List[Dict[str, Any]]:
    """Vrátí všechna auta (pro dropdown)."""
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT id, name, power_limit_percent, steer_angle_deg, created_at
        FROM cars
        ORDER BY id;
        """
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def car_exists(car_id: int) -> bool:
    conn = get_db_connection()
    row = conn.execute("SELECT 1 FROM cars WHERE id = ? LIMIT 1;", (car_id,)).fetchone()
    conn.close()
    return row is not None


def ensure_active_car_in_session() -> Optional[int]:
    """
    Zajistí, že session['active_car_id'] existuje a ukazuje na existující auto.
    Když není nastavené, nastaví se první auto v DB.
    """
    cars = get_all_cars()
    if not cars:
        session.pop("active_car_id", None)
        return None

    active = session.get("active_car_id")
    try:
        active_int = int(active) if active is not None else None
    except Exception:
        active_int = None

    if active_int is not None and car_exists(active_int):
        return active_int

    session["active_car_id"] = int(cars[0]["id"])
    return int(cars[0]["id"])


# ------------------------------------------------------------
# 6) ROUTES – stránky
# ------------------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html", user=current_user())


@app.route("/info")
def info():
    return render_template("info.html", user=current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Registrace:
    - vytvoří řádek v users
    """
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

    pw_hash = generate_password_hash(password)

    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            (username, pw_hash, role),
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
    """
    Login:
    - ověří username + password
    - nastaví session
    """
    if request.method == "GET":
        return render_template("login.html", user=current_user())

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    if not username or not password:
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()
    row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?;",
        (username,),
    ).fetchone()
    conn.close()

    # Schválně jedna hláška pro obě chyby -> bezpečnější (neprozrazuje, jestli user existuje)
    if row is None or not check_password_hash(row["password_hash"], password):
        flash("Špatné uživatelské jméno nebo heslo.", "error")
        return redirect(url_for("login"))

    session["user_id"] = int(row["id"])
    session["username"] = row["username"]
    session["role"] = row["role"]

    # nastavíme aktivní auto (první existující), aby dashboard hned fungoval
    ensure_active_car_in_session()

    flash(f"Přihlášen jako {row['username']}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("Odhlášeno.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    """
    Dashboard:
    - jen pro přihlášené
    - dropdown aut (všechny cars)
    - jízdy:
      - user vidí svoje jízdy
      - admin může vidět všechny (tady necháme pro admina všechny, jinak jen svoje)
    """
    if not login_required():
        flash("Nejdřív se přihlas.", "error")
        return redirect(url_for("login"))

    user = current_user()
    assert user is not None
    user_id = int(user["id"])

    cars = get_all_cars()
    active_car_id = ensure_active_car_in_session()

    conn = get_db_connection()
    if admin_required():
        rows = conn.execute(
            """
            SELECT
              rides.id,
              users.username AS username,
              cars.name AS car_name,
              rides.started_at,
              rides.duration_sec
            FROM rides
            JOIN users ON users.id = rides.user_id
            JOIN cars  ON cars.id  = rides.car_id
            ORDER BY rides.started_at DESC;
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
              rides.id,
              users.username AS username,
              cars.name AS car_name,
              rides.started_at,
              rides.duration_sec
            FROM rides
            JOIN users ON users.id = rides.user_id
            JOIN cars  ON cars.id  = rides.car_id
            WHERE rides.user_id = ?
            ORDER BY rides.started_at DESC;
            """,
            (user_id,),
        ).fetchall()
    conn.close()

    rides = [dict(r) for r in rows]

    return render_template(
        "dashboard.html",
        user=user,
        cars=cars,
        active_car_id=active_car_id,
        rides=rides,
        arduino_available=ARDUINO_AVAILABLE,
        arduino_error=ARDUINO_IMPORT_ERROR,
    )


# ------------------------------------------------------------
# 7) API – výběr auta + ovládání serva + start/stop jízdy
# ------------------------------------------------------------
@app.route("/api/select_car", methods=["POST"])
def api_select_car():
    """
    Uloží aktivní auto do session.
    Protože už nemáme user_cars, může si user vybrat libovolné auto z cars.
    """
    if not login_required():
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    car_id = data.get("car_id")

    try:
        car_id_int = int(car_id)
    except Exception:
        return jsonify({"error": "Invalid car_id"}), 400

    if not car_exists(car_id_int):
        return jsonify({"error": "Car not found"}), 404

    session["active_car_id"] = car_id_int
    return jsonify({"ok": True, "active_car_id": car_id_int})


@app.route("/api/control", methods=["POST"])
def api_control():
    """
    Ovládání serva přes Arduino.

    Povolené příkazy:
      STEER:L
      STEER:R
      STEER:C
    """
    if not login_required():
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()

    allowed = {"STEER:L", "STEER:R", "STEER:C"}
    if cmd not in allowed:
        return jsonify({"error": "Command not allowed"}), 400

    if not ARDUINO_AVAILABLE:
        return jsonify({"error": f"Arduino není dostupné: {ARDUINO_IMPORT_ERROR}"}), 500

    try:
        arduino_comm.send_line(cmd)  # type: ignore[union-attr]
    except Exception as e:
        return jsonify({"error": f"Arduino send failed: {e}"}), 500

    return jsonify({"ok": True, "sent": cmd})


@app.route("/api/ride/start", methods=["POST"])
def api_ride_start():
    """
    Start jízdy:
    - vytvoří nový záznam v rides:
      user_id, car_id, started_at (default), duration_sec = NULL
    - vrátí ride_id

    Pozn.: active_car_id musí být vybrané (dropdown).
    """
    if not login_required():
        return jsonify({"error": "Not logged in"}), 401

    user_id = int(session["user_id"])
    car_id = ensure_active_car_in_session()

    if car_id is None:
        return jsonify({"error": "No cars in database"}), 400

    # nepovolíme start, pokud user už má rozjetou jízdu (duration_sec IS NULL)
    conn = get_db_connection()
    active = conn.execute(
        "SELECT id FROM rides WHERE user_id = ? AND duration_sec IS NULL ORDER BY id DESC LIMIT 1;",
        (user_id,),
    ).fetchone()
    if active:
        conn.close()
        return jsonify({"error": "Ride already running", "ride_id": int(active["id"])}), 409

    cur = conn.execute(
        "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, NULL);",
        (user_id, int(car_id)),
    )
    conn.commit()
    ride_id = int(cur.lastrowid)
    conn.close()

    return jsonify({"ok": True, "ride_id": ride_id, "car_id": int(car_id)})


@app.route("/api/ride/stop", methods=["POST"])
def api_ride_stop():
    """
    Stop jízdy:
    - najde poslední aktivní jízdu usera (duration_sec IS NULL)
    - spočítá duration_sec jako (teď - started_at)
    - uloží duration_sec

    Pokud žádná aktivní jízda není, vrátí 404.
    """
    if not login_required():
        return jsonify({"error": "Not logged in"}), 401

    user_id = int(session["user_id"])

    conn = get_db_connection()
    row = conn.execute(
        """
        SELECT id, started_at
        FROM rides
        WHERE user_id = ? AND duration_sec IS NULL
        ORDER BY id DESC
        LIMIT 1;
        """,
        (user_id,),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "No running ride"}), 404

    # SQLite started_at je text datetime('now') -> typicky "YYYY-MM-DD HH:MM:SS"
    # Spočítáme rozdíl v sekundách na Python straně (je to nejjednodušší).
    started_str = str(row["started_at"])
    try:
        started_dt = datetime.strptime(started_str, "%Y-%m-%d %H:%M:%S")
        now_dt = datetime.now()
        duration = int((now_dt - started_dt).total_seconds())
        if duration < 0:
            duration = 0
    except Exception:
        # když by formát neseděl, dáme aspoň 0 a projekt běží dál
        duration = 0

    conn.execute(
        "UPDATE rides SET duration_sec = ? WHERE id = ?;",
        (duration, int(row["id"])),
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "ride_id": int(row["id"]), "duration_sec": duration})


# ------------------------------------------------------------
# 8) ADMIN
# ------------------------------------------------------------
@app.route("/admin")
def admin():
    if not admin_required():
        abort(403)

    conn = get_db_connection()
    users_rows = conn.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY id;"
    ).fetchall()
    cars_rows = conn.execute(
        "SELECT id, name, power_limit_percent, steer_angle_deg, created_at FROM cars ORDER BY id;"
    ).fetchall()
    rides_rows = conn.execute(
        """
        SELECT
          rides.id,
          users.username AS username,
          cars.name AS car_name,
          rides.started_at,
          rides.duration_sec
        FROM rides
        JOIN users ON users.id = rides.user_id
        JOIN cars  ON cars.id  = rides.car_id
        ORDER BY rides.started_at DESC;
        """
    ).fetchall()
    conn.close()

    return render_template(
        "admin.html",
        user=current_user(),
        users=[dict(u) for u in users_rows],
        cars=[dict(c) for c in cars_rows],
        rides=[dict(r) for r in rides_rows],
        arduino_available=ARDUINO_AVAILABLE,
        arduino_error=ARDUINO_IMPORT_ERROR,
    )


@app.route("/admin/ride/<int:ride_id>/delete", methods=["POST"])
def admin_delete_ride(ride_id: int):
    if not admin_required():
        abort(403)

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM rides WHERE id = ?;", (ride_id,))
    conn.commit()
    conn.close()

    flash("Jízda smazána." if cur.rowcount else "Jízda nenalezena.", "success" if cur.rowcount else "error")
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id: int):
    if not admin_required():
        abort(403)

    if int(session.get("user_id", -1)) == user_id:
        flash("Nemůžeš smazat sám sebe.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()
    conn.close()

    flash("Uživatel smazán." if cur.rowcount else "Uživatel nenalezen.", "success" if cur.rowcount else "error")
    return redirect(url_for("admin"))


@app.route("/admin/car/<int:car_id>/delete", methods=["POST"])
def admin_delete_car(car_id: int):
    if not admin_required():
        abort(403)

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM cars WHERE id = ?;", (car_id,))
    conn.commit()
    conn.close()

    flash("Auto smazáno." if cur.rowcount else "Auto nenalezeno.", "success" if cur.rowcount else "error")
    return redirect(url_for("admin"))


# ------------------------------------------------------------
# 9) RUN
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)