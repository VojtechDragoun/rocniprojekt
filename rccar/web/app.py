"""
RCcar – app.py (Flask backend) – Vojtěch
=======================================

Cíl:
- Login/registrace přes SQLite + session
- Dashboard:
  - zobrazení jízd
  - přepínání aktivního auta (bez admina) – jen mezi auty, která má user přiřazená
  - ovládání serva přes Arduino (Serial)
- Admin stránka (volitelné): přehled + mazání

DŮLEŽITÉ (aby nebyly "spousty chyb"):
-----------------------------------
1) Uživatel často nemá přiřazené žádné auto => dashboard by byl mrtvý.
   Proto je tu "auto-assign":
   - existuje DefaultCar (vytvoří se automaticky)
   - při registraci (a i při loginu pro jistotu) se userovi DefaultCar přiřadí,
     pokud nemá žádné auto.

2) Arduino komunikace je volitelná:
   - pokud chybí pyserial/arduino_comm, web pořád běží,
     jen /api/control vrátí čitelnou chybu.

Struktura projektu:
rccar/
  database/
    rccar.db
    schema.sql
  web/
    app.py
    arduino_comm.py   (doporučeno – auto COM detekce)
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


# ------------------------------------------------------------
# 0) Arduino bridge (volitelný import)
# ------------------------------------------------------------
# Když to nejde importovat (např. chybí pyserial), web musí běžet dál.
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
    Otevře připojení k SQLite.
    V SQLite jsou FOREIGN KEY defaultně OFF => musíme zapnout pro každé spojení.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db() -> None:
    """
    Vytvoří tabulky podle schema.sql (zdroj pravdy).

    Poznámka:
    - CREATE TABLE IF NOT EXISTS tabulku nepřepíše.
    - Pokud jsi měnil schéma a DB už existuje, nejčistší je DB smazat a vytvořit znovu.
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
    """Vrátí přihlášeného usera ze session nebo None."""
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
# 5) Auta (M:N) – helpery
# ------------------------------------------------------------
DEFAULT_CAR_NAME = "DefaultCar"


def ensure_default_car_exists(conn: sqlite3.Connection) -> int:
    """
    Zajistí, že v tabulce cars existuje DefaultCar.
    Vrátí jeho id.
    """
    row = conn.execute("SELECT id FROM cars WHERE name = ? LIMIT 1;", (DEFAULT_CAR_NAME,)).fetchone()
    if row:
        return int(row["id"])

    # Vytvoření defaultního auta
    conn.execute(
        """
        INSERT INTO cars (name, servo_pin, servo_center_deg, servo_offset_deg, motor_max_pwm)
        VALUES (?, 3, 90, 45, 255);
        """,
        (DEFAULT_CAR_NAME,),
    )
    conn.commit()

    row2 = conn.execute("SELECT id FROM cars WHERE name = ? LIMIT 1;", (DEFAULT_CAR_NAME,)).fetchone()
    return int(row2["id"])  # type: ignore[arg-type]


def user_has_any_car(conn: sqlite3.Connection, user_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM user_cars WHERE user_id = ? LIMIT 1;",
        (user_id,),
    ).fetchone()
    return row is not None


def assign_car_to_user(conn: sqlite3.Connection, user_id: int, car_id: int) -> None:
    """
    Přiřadí auto uživateli do user_cars (pokud už tam není).
    """
    conn.execute(
        """
        INSERT OR IGNORE INTO user_cars (user_id, car_id, access_role)
        VALUES (?, ?, 'driver');
        """,
        (user_id, car_id),
    )
    conn.commit()


def ensure_user_has_default_car(user_id: int) -> None:
    """
    Blbuvzdorný helper:
    - pokud user nemá žádné auto -> vytvoří DefaultCar (když chybí) a přiřadí mu ho.
    """
    conn = get_db_connection()
    if not user_has_any_car(conn, user_id):
        default_car_id = ensure_default_car_exists(conn)
        assign_car_to_user(conn, user_id, default_car_id)
    conn.close()


def get_user_cars(user_id: int) -> List[Dict[str, Any]]:
    """
    Vrátí seznam aut, ke kterým má user přístup.
    """
    conn = get_db_connection()
    rows = conn.execute(
        """
        SELECT
            cars.id,
            cars.name,
            cars.servo_pin,
            cars.servo_center_deg,
            cars.servo_offset_deg,
            cars.motor_max_pwm
        FROM user_cars
        JOIN cars ON cars.id = user_cars.car_id
        WHERE user_cars.user_id = ?
        ORDER BY cars.name;
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def user_has_car_access(user_id: int, car_id: int) -> bool:
    conn = get_db_connection()
    row = conn.execute(
        "SELECT 1 FROM user_cars WHERE user_id = ? AND car_id = ? LIMIT 1;",
        (user_id, car_id),
    ).fetchone()
    conn.close()
    return row is not None


def ensure_active_car_in_session(user_id: int) -> Optional[int]:
    """
    Zajistí, že session["active_car_id"] je validní a user k němu má přístup.
    Pokud ne, nastaví první dostupné auto uživatele.
    Vrátí active_car_id nebo None, pokud user nemá žádné auto (to by se ale nemělo stát).
    """
    cars = get_user_cars(user_id)
    if not cars:
        # fallback: auto-assign (mělo by to vyřešit)
        ensure_user_has_default_car(user_id)
        cars = get_user_cars(user_id)

    if not cars:
        session.pop("active_car_id", None)
        return None

    active = session.get("active_car_id")
    try:
        active_int = int(active) if active is not None else None
    except Exception:
        active_int = None

    if active_int is not None and user_has_car_access(user_id, active_int):
        return active_int

    # nastavíme první auto
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
    - uloží usera do users
    - AUTOMATICKY mu přiřadí DefaultCar (pokud nemá žádné auto)
      => aby dashboard fungoval hned a bez admin zásahu.
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

    password_hash = generate_password_hash(password)

    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            (username, password_hash, role),
        )
        conn.commit()

        # zjistíme id nového usera
        new_user = conn.execute("SELECT id FROM users WHERE username = ? LIMIT 1;", (username,)).fetchone()
        new_user_id = int(new_user["id"])  # type: ignore[index]

        # auto-assign (DefaultCar)
        default_car_id = ensure_default_car_exists(conn)
        assign_car_to_user(conn, new_user_id, default_car_id)

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
    - pro jistotu udělá auto-assign (když user nemá žádné auto)
    - nastaví session["active_car_id"]
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
        "SELECT id, username, password_hash, role FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    conn.close()

    if row is None or not check_password_hash(row["password_hash"], password):
        flash("Špatné uživatelské jméno nebo heslo.", "error")
        return redirect(url_for("login"))

    session["user_id"] = int(row["id"])
    session["username"] = row["username"]
    session["role"] = row["role"]

    # auto-assign, ať dashboard není prázdný
    ensure_user_has_default_car(int(row["id"]))
    ensure_active_car_in_session(int(row["id"]))

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

    user = current_user()
    assert user is not None
    user_id = int(user["id"])

    # zajistíme auto + aktivní auto
    ensure_user_has_default_car(user_id)
    active_car_id = ensure_active_car_in_session(user_id)

    cars = get_user_cars(user_id)

    # jízdy: admin všechny, user svoje
    conn = get_db_connection()
    if admin_required():
        rows = conn.execute(
            """
            SELECT
                rides.id,
                users.username AS username,
                cars.name AS car_name,
                rides.duration_sec AS duration_sec,
                rides.created_at AS created_at
            FROM rides
            JOIN users ON users.id = rides.user_id
            JOIN cars  ON cars.id  = rides.car_id
            ORDER BY rides.created_at DESC;
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT
                rides.id,
                users.username AS username,
                cars.name AS car_name,
                rides.duration_sec AS duration_sec,
                rides.created_at AS created_at
            FROM rides
            JOIN users ON users.id = rides.user_id
            JOIN cars  ON cars.id  = rides.car_id
            WHERE rides.user_id = ?
            ORDER BY rides.created_at DESC;
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
    )


@app.route("/ride/add_demo")
def add_demo_ride():
    """
    Přidá demo jízdu (120 s) aktuálnímu uživateli a jeho aktivnímu autu.
    """
    if not login_required():
        flash("Nejdřív se přihlas.", "error")
        return redirect(url_for("login"))

    user_id = int(session["user_id"])
    ensure_user_has_default_car(user_id)
    car_id = ensure_active_car_in_session(user_id)

    if car_id is None:
        flash("Nemáš žádné auto (tohle by se už nemělo stát).", "error")
        return redirect(url_for("dashboard"))

    if not user_has_car_access(user_id, int(car_id)):
        flash("Nemáš přístup k aktivnímu autu.", "error")
        return redirect(url_for("dashboard"))

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, ?)",
        (user_id, int(car_id), 120),
    )
    conn.commit()
    conn.close()

    flash("Demo jízda přidána (120 s).", "success")
    return redirect(url_for("dashboard"))


# ------------------------------------------------------------
# 7) API – výběr auta + ovládání serva
# ------------------------------------------------------------
@app.route("/api/select_car", methods=["POST"])
def api_select_car():
    """
    Nastaví aktivní auto do session.
    Uživatel si přepíná sám – ale jen mezi auty, která má přiřazená (user_cars).
    """
    if not login_required():
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    car_id = data.get("car_id")

    try:
        car_id_int = int(car_id)
    except Exception:
        return jsonify({"error": "Invalid car_id"}), 400

    user_id = int(session["user_id"])

    # auto-assign (pro jistotu, když je DB rozbitá / nový user)
    ensure_user_has_default_car(user_id)

    if not user_has_car_access(user_id, car_id_int):
        return jsonify({"error": "No access to this car"}), 403

    session["active_car_id"] = car_id_int
    return jsonify({"ok": True, "active_car_id": car_id_int})


@app.route("/api/control", methods=["POST"])
def api_control():
    """
    Ovládání serva přes Arduino.
    Příkazy:
      STEER:L  (vlevo)
      STEER:R  (vpravo)
      STEER:C  (střed)

    Bezpečnost:
    - jen přihlášený
    - jen povolené příkazy
    - musí mít přístup k aktivnímu autu (M:N kontrola)
    """
    if not login_required():
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()

    allowed = {"STEER:L", "STEER:R", "STEER:C"}
    if cmd not in allowed:
        return jsonify({"error": "Command not allowed"}), 400

    user_id = int(session["user_id"])
    ensure_user_has_default_car(user_id)
    car_id = ensure_active_car_in_session(user_id)

    if car_id is None:
        return jsonify({"error": "No active car selected"}), 400

    if not user_has_car_access(user_id, int(car_id)):
        return jsonify({"error": "No access to this car"}), 403

    if not ARDUINO_AVAILABLE:
        return jsonify({"error": f"Arduino komunikace není dostupná: {ARDUINO_IMPORT_ERROR}"}), 500

    try:
        # odešleme řádek do Arduino (Serial)
        arduino_comm.send_line(cmd)  # type: ignore[union-attr]
    except Exception as e:
        return jsonify({"error": f"Arduino send failed: {e}"}), 500

    return jsonify({"ok": True, "sent": cmd, "car_id": int(car_id)})


# ------------------------------------------------------------
# 8) ADMIN – volitelné
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
        """
        SELECT id, name, servo_pin, servo_center_deg, servo_offset_deg, motor_max_pwm, created_at
        FROM cars ORDER BY id;
        """
    ).fetchall()

    user_cars_rows = conn.execute(
        """
        SELECT
            users.username AS username,
            cars.name AS car_name,
            user_cars.access_role,
            user_cars.created_at
        FROM user_cars
        JOIN users ON users.id = user_cars.user_id
        JOIN cars  ON cars.id  = user_cars.car_id
        ORDER BY cars.name, users.username;
        """
    ).fetchall()

    rides_rows = conn.execute(
        """
        SELECT
            rides.id,
            users.username AS username,
            cars.name AS car_name,
            rides.duration_sec,
            rides.created_at
        FROM rides
        JOIN users ON users.id = rides.user_id
        JOIN cars  ON cars.id  = rides.car_id
        ORDER BY rides.created_at DESC;
        """
    ).fetchall()

    conn.close()

    return render_template(
        "admin.html",
        user=current_user(),
        users=[dict(u) for u in users_rows],
        cars=[dict(c) for c in cars_rows],
        user_cars=[dict(x) for x in user_cars_rows],
        rides=[dict(r) for r in rides_rows],
        arduino_available=ARDUINO_AVAILABLE,
        arduino_error=ARDUINO_IMPORT_ERROR,
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

    # admin nesmí smazat sám sebe
    if int(session.get("user_id", -1)) == user_id:
        flash("Nemůžeš smazat sám sebe.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection()
    cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

    flash("Uživatel smazán." if cur.rowcount else "Uživatel nenalezen.", "success" if cur.rowcount else "error")
    return redirect(url_for("admin"))


# ------------------------------------------------------------
# 9) RUN
# ------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)