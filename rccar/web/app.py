"""
RCcar – app.py (Flask backend)
==============================

Hlavní backend celého projektu.

Tenhle soubor řeší hlavně:
- spuštění Flask aplikace
- připojení k SQLite databázi
- registraci a login uživatelů
- session přihlášeného uživatele
- dashboard
- komunikaci s Arduinem přes serial
- start a stop jízdy
- admin sekci a mazání dat
- ukládání a načítání posledního ovládacího příkazu ze souboru JSON

Databáze používá 3 hlavní tabulky:
- users
- cars
- rides

Poznámka:
Frontend stránky jsou v templates/
CSS a další statické soubory jsou ve static/
Komunikace s Arduinem je řešená přes soubor arduino_comm.py
"""

from __future__ import annotations
# dovolí modernější práci s typy v Pythonu
# díky tomu můžeme lépe používat anotace návratových typů funkcí

import json
# práce s JSON soubory
# tady se používá hlavně pro last_command.json

import logging
# knihovna pro logování do konzole
# logy se hodí při testování i při ukázce projektu

import sqlite3
# vestavěná knihovna pro SQLite databázi

import sys
# používá se tady hlavně kvůli stdout pro logging
# tedy aby se logy vypisovaly do konzole

from datetime import datetime
# používá se pro uložení času posledního příkazu do JSON souboru

from pathlib import Path
# pohodlná práce s cestami k souborům
# díky Path nemusíme ručně spojovat cesty jako stringy

from typing import Any, Dict, List, Optional
# typové anotace pro lepší čitelnost kódu
# Any = libovolný typ
# Dict = slovník
# List = seznam
# Optional = hodnota může být i None

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
# hlavní věci z Flasku:
# - Flask = samotná aplikace
# - render_template = vrací HTML šablony z templates/
# - request = přístup k datům z formulářů a JSONu
# - redirect = přesměrování na jinou route
# - url_for = generování URL podle názvu route
# - session = přihlášení uživatele / ukládání dat do session
# - flash = jednorázové zprávy pro uživatele
# - abort = vyhození HTTP chyby, např. 403
# - jsonify = vrácení JSON odpovědi pro JS / API endpointy

from werkzeug.security import generate_password_hash, check_password_hash
# hashování a kontrola hesel
# hesla se neukládají přímo jako text, ale bezpečně jako hash


# ------------------------------------------------------------
# 0) Arduino bridge
# ------------------------------------------------------------
# tady se zkouší načíst modul pro komunikaci s Arduinem
# když to nepůjde, aplikace pořád poběží, ale bez ovládání hardwaru
# to je výhodné hlavně při testování webu bez připojeného Arduina

ARDUINO_AVAILABLE = True
# předpokládáme, že Arduino modul půjde načíst
# pokud import selže, tahle hodnota se změní na False

ARDUINO_IMPORT_ERROR = ""
# sem se případně uloží text chyby
# potom se dá zobrazit v dashboardu nebo adminu

try:
    import arduino_comm  # web/arduino_comm.py
    # pokud se import povede, můžeme později používat arduino_comm.send_line(...)
    # samotná komunikace s COM portem tedy není v app.py, ale v odděleném souboru
except Exception as e:
    # když se import nepovede, aplikace nespadne
    # jen si poznamená, že Arduino není dostupné
    ARDUINO_AVAILABLE = False
    ARDUINO_IMPORT_ERROR = str(e)
    arduino_comm = None  # type: ignore
    # nastavíme proměnnou aspoň na None, aby existovala i v případě chyby


# ------------------------------------------------------------
# 1) Cesty k databázi a schema.sql
# ------------------------------------------------------------

# složka, ve které je app.py
BASE_DIR = Path(__file__).resolve().parent
# typicky tedy složka web/

# root projektu = o úroveň výš
PROJECT_ROOT = BASE_DIR.parent
# tím se dostaneme na hlavní složku projektu RCcar

# cesta k SQLite databázi
DB_PATH = PROJECT_ROOT / "database" / "rccar.db"
# databáze je mimo web/, konkrétně ve složce database/

# cesta k SQL schématu
SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"
# schema.sql obsahuje SQL příkazy pro vytvoření tabulek


# ------------------------------------------------------------
# 1.1) Cesta k JSON souboru s posledním příkazem
# ------------------------------------------------------------
# tenhle soubor slouží jako jednoduché ukládání a načítání dat ze souboru
# konkrétně se do něj ukládá poslední odeslaný příkaz auta a čas

LAST_COMMAND_PATH = BASE_DIR / "last_command.json"
# soubor bude uložený přímo vedle app.py ve složce web/


# ------------------------------------------------------------
# 2) Flask aplikace
# ------------------------------------------------------------

# vytvoření Flask app
# static_folder="static" znamená, že Flask bude hledat statické soubory ve složce static
# static_url_path="/static" znamená, že se budou načítat přes adresy typu /static/style.css
app = Flask(__name__, static_folder="static", static_url_path="/static")

# tajný klíč pro session
# session ukládá informace o přihlášeném uživateli
# v reálné aplikaci by měl být složitější a neměl by být natvrdo v kódu
app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"


# ------------------------------------------------------------
# 2.1) Logging
# ------------------------------------------------------------

def setup_logging() -> None:
    # tahle funkce nastaví logování Flask aplikace do konzole
    # logování je užitečné pro ladění i dokumentaci toho, co aplikace dělá

    # handler bude vypisovat logy do konzole
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    # formát logu
    # %(asctime)s = čas
    # %(levelname)s = úroveň logu (INFO/WARNING/ERROR)
    # %(module)s = modul, odkud log přišel
    # %(message)s = samotná zpráva
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    handler.setFormatter(formatter)

    # nastavíme úroveň logování pro Flask app
    app.logger.setLevel(logging.INFO)

    # při debug reloadu by se jinak mohlo přidat víc handlerů
    # a logy by se vypisovaly duplicitně
    if not app.logger.handlers:
        app.logger.addHandler(handler)


# zavolání nastavení logování
setup_logging()

# několik úvodních logů po startu aplikace
# díky tomu v konzoli hned vidíme, že se app správně spustila
app.logger.info("Aplikace RCcar startuje.")
app.logger.info(f"DB_PATH = {DB_PATH}")
app.logger.info(f"SCHEMA_PATH = {SCHEMA_PATH}")
app.logger.info(f"LAST_COMMAND_PATH = {LAST_COMMAND_PATH}")

if ARDUINO_AVAILABLE:
    # když se podařilo načíst Arduino modul
    app.logger.info("Arduino modul byl úspěšně načten.")
else:
    # když se nepodařilo
    app.logger.warning(f"Arduino modul není dostupný: {ARDUINO_IMPORT_ERROR}")


# ------------------------------------------------------------
# 3) Helpery pro databázi
# ------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    # vytvoří nové připojení k SQLite databázi
    # používá se ve více route i helper funkcích

    conn = sqlite3.connect(DB_PATH)

    # díky row_factory půjdou řádky číst třeba jako row["id"]
    # bez toho by se muselo přistupovat přes indexy row[0], row[1], ...
    conn.row_factory = sqlite3.Row

    # zapnutí cizích klíčů
    # SQLite je má defaultně vypnuté, takže je musíme ručně povolit
    conn.execute("PRAGMA foreign_keys = ON;")

    return conn


def init_db() -> None:
    # tahle funkce načte schema.sql a vytvoří / aktualizuje tabulky
    # spouští se při startu aplikace

    if not SCHEMA_PATH.exists():
        # když schema.sql chybí, je to problém
        # bez schématu nevíme, jak má databáze vypadat
        app.logger.error(f"Chybí schema.sql: {SCHEMA_PATH}")
        raise FileNotFoundError(f"Chybí schema.sql: {SCHEMA_PATH}")

    app.logger.info("Inicializuji databázi ze schema.sql")

    # načtení SQL schématu
    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    # připojení k DB
    conn = get_db_connection()

    # spuštění celého SQL skriptu
    # executescript umí provést víc SQL příkazů najednou
    conn.executescript(schema_sql)

    # uložení změn
    conn.commit()

    # zavření spojení
    conn.close()

    app.logger.info("Databáze inicializována.")


# databázi inicializujeme hned při startu appky
# tím se zajistí, že tabulky existují ještě před první prací s nimi
init_db()


# ------------------------------------------------------------
# 3.1) Helpery pro práci se souborem last_command.json
# ------------------------------------------------------------
# tady jsou funkce pro ukládání a načítání posledního příkazu auta
# soubor slouží jako jednoduchý příklad práce se souborem mimo databázi

def ensure_last_command_file() -> None:
    """
    Zajistí, že existuje soubor last_command.json
    a že obsahuje platný základní JSON.

    Když soubor neexistuje nebo je prázdný/rozbitý,
    vytvoří se výchozí obsah.
    """
    default_data = {
        "cmd": None,
        "time": None,
    }
    # výchozí stav:
    # - cmd = poslední příkaz není známý
    # - time = čas posledního příkazu není známý

    try:
        # když soubor neexistuje, rovnou ho vytvoříme
        if not LAST_COMMAND_PATH.exists():
            LAST_COMMAND_PATH.write_text(
                json.dumps(default_data, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )
            app.logger.info("Vytvořen nový soubor last_command.json")
            return

        # načtení existujícího obsahu
        raw = LAST_COMMAND_PATH.read_text(encoding="utf-8").strip()

        # když je soubor prázdný, opravíme ho
        if not raw:
            LAST_COMMAND_PATH.write_text(
                json.dumps(default_data, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )
            app.logger.warning("Soubor last_command.json byl prázdný, byl opraven.")
            return

        # kontrola, že je obsah validní JSON
        data = json.loads(raw)

        # když to není dict, také opravíme
        # očekáváme objekt typu:
        # { "cmd": "...", "time": "..." }
        if not isinstance(data, dict):
            raise ValueError("last_command.json nemá objekt JSON")

        # doplnění chybějících klíčů
        # kdyby soubor obsahoval jen část dat, dopočítáme minimum
        if "cmd" not in data:
            data["cmd"] = None
        if "time" not in data:
            data["time"] = None

        # soubor znovu uložíme v pěkném formátu
        LAST_COMMAND_PATH.write_text(
            json.dumps(data, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )

    except Exception as e:
        # když je soubor poškozený, přepíšeme ho výchozí verzí
        # aplikace tak nespadne jen kvůli špatnému JSON souboru
        app.logger.warning(f"Soubor last_command.json byl poškozený, obnovuji ho: {e}")
        LAST_COMMAND_PATH.write_text(
            json.dumps(default_data, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )


def load_last_command() -> Dict[str, Any]:
    """
    Načte poslední příkaz ze souboru last_command.json.

    Vrací slovník ve tvaru:
    {
        "cmd": "STEER:L" nebo None,
        "time": "2026-03-23 21:10:00" nebo None
    }
    """
    # nejdřív si ověříme, že soubor existuje a má správný formát
    ensure_last_command_file()

    try:
        # načtení JSON dat do Python slovníku
        data = json.loads(LAST_COMMAND_PATH.read_text(encoding="utf-8"))

        # pojistka, kdyby v JSON něco chybělo
        return {
            "cmd": data.get("cmd"),
            "time": data.get("time"),
        }

    except Exception as e:
        # když by se načtení nepovedlo, vrátíme aspoň bezpečný výchozí stav
        app.logger.error(f"Nepodařilo se načíst last_command.json: {e}")
        return {
            "cmd": None,
            "time": None,
        }


def save_last_command(cmd: str) -> None:
    """
    Uloží poslední odeslaný příkaz auta do JSON souboru.

    Tohle je ta část projektu, která ukládá data do souboru.
    """
    data = {
        "cmd": cmd,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # ukládá se:
    # - samotný příkaz
    # - aktuální datum a čas jeho odeslání

    LAST_COMMAND_PATH.write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )

    app.logger.info(f"Uložen poslední příkaz do souboru: {data}")


# zajistíme existenci souboru hned při startu aplikace
ensure_last_command_file()


# ------------------------------------------------------------
# 4) Helpery pro přihlášení a role
# ------------------------------------------------------------

def current_user() -> Optional[Dict[str, Any]]:
    # vrátí základní info o právě přihlášeném uživateli
    # nebo None, pokud nikdo přihlášený není
    # tahle funkce se hodí hlavně do šablon, aby se v navbaru vědělo,
    # jestli je uživatel přihlášený a jakou má roli

    if "user_id" not in session:
        return None

    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
    }


def login_required() -> bool:
    # jednoduchá kontrola, jestli je uživatel přihlášený
    # funguje podle toho, jestli session obsahuje user_id
    return "user_id" in session


def admin_required() -> bool:
    # kontrola, jestli je uživatel přihlášený a zároveň admin
    # používá se hlavně u /admin a mazacích route
    return login_required() and session.get("role") == "admin"


# ------------------------------------------------------------
# 5) Helpery pro auta
# ------------------------------------------------------------

def get_all_cars() -> List[Dict[str, Any]]:
    # načte všechna auta z databáze
    # data se potom používají v dashboardu a při výběru aktivního auta

    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT id, name, power_limit_percent, steer_angle_deg, created_at
        FROM cars
        ORDER BY id;
        """
    ).fetchall()
    # ORDER BY id zajistí stabilní pořadí aut

    conn.close()

    # převede sqlite rows na obyčejné dicty
    # s dicty se pak lépe pracuje v Pythonu i v Jinja šablonách
    return [dict(r) for r in rows]


def car_exists(car_id: int) -> bool:
    # ověří, jestli auto s daným id existuje
    # používá se třeba při výběru auta přes API

    conn = get_db_connection()

    row = conn.execute(
        "SELECT 1 FROM cars WHERE id = ? LIMIT 1;",
        (car_id,)
    ).fetchone()

    conn.close()
    return row is not None


def ensure_active_car_in_session() -> Optional[int]:
    # zajistí, že v session bude vybrané nějaké aktivní auto
    # pokud žádné není, nastaví první auto z databáze
    # to se hodí po loginu i při otevření dashboardu

    cars = get_all_cars()

    if not cars:
        # když v databázi nejsou žádná auta
        # session active_car_id smažeme
        session.pop("active_car_id", None)
        app.logger.warning("V databázi nejsou žádná auta.")
        return None

    # zkusíme načíst aktuálně uložené active_car_id ze session
    active = session.get("active_car_id")

    try:
        active_int = int(active) if active is not None else None
    except Exception:
        # kdyby bylo v session něco neplatného, ignorujeme to
        active_int = None

    # pokud je uložené validní existující auto, vrátíme ho
    if active_int is not None and car_exists(active_int):
        return active_int

    # jinak nastavíme první auto v databázi jako výchozí
    session["active_car_id"] = int(cars[0]["id"])
    app.logger.info(f"Nastavuji výchozí active_car_id = {cars[0]['id']}")
    return int(cars[0]["id"])


# ------------------------------------------------------------
# 6) ROUTES – stránky
# ------------------------------------------------------------

@app.route("/")
def index():
    # hlavní stránka projektu
    # typicky domovská stránka s úvodními informacemi
    app.logger.info("Návštěva stránky /")
    return render_template("index.html", user=current_user())
    # do šablony se posílá i user, aby šlo v HTML poznat,
    # jestli je někdo přihlášený


@app.route("/info")
def info():
    # info stránka o projektu
    # může obsahovat popis funkce projektu, technologie apod.
    app.logger.info("Návštěva stránky /info")
    return render_template("info.html", user=current_user())


@app.route("/register", methods=["GET", "POST"])
def register():
    # registrační stránka
    # GET = zobrazí formulář
    # POST = zpracuje registraci

    if request.method == "GET":
        app.logger.info("Návštěva stránky /register [GET]")
        return render_template("register.html", user=current_user())

    # načtení dat z formuláře
    # request.form obsahuje data z HTML formuláře
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""
    role = (request.form.get("role") or "user").strip().lower()

    app.logger.info(f"Pokus o registraci: username='{username}', role='{role}'")

    # kontrola vyplnění
    if not username or not password:
        app.logger.warning("Registrace selhala: chybí username nebo password.")
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("register"))

    # povolené role
    # tím se omezí, co může formulář uložit do DB
    if role not in ("user", "admin"):
        app.logger.warning(f"Registrace selhala: neplatná role '{role}'")
        flash("Role musí být 'user' nebo 'admin'.", "error")
        return redirect(url_for("register"))

    # vytvoření hashe hesla
    # heslo se tedy do databáze neukládá přímo
    pw_hash = generate_password_hash(password)

    try:
        conn = get_db_connection()

        # vložení nového uživatele
        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            (username, pw_hash, role),
        )

        conn.commit()
        conn.close()

        app.logger.info(f"Registrace úspěšná: username='{username}', role='{role}'")

    except sqlite3.IntegrityError:
        # nejčastěji když už stejné username existuje
        # typicky kvůli UNIQUE omezení v databázi
        app.logger.warning(f"Registrace selhala: uživatel '{username}' už existuje.")
        flash("Uživatel s tímto jménem už existuje.", "error")
        return redirect(url_for("register"))

    flash("Registrace OK. Teď se přihlas.", "success")
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    # přihlášení uživatele
    # GET = formulář
    # POST = kontrola údajů

    if request.method == "GET":
        app.logger.info("Návštěva stránky /login [GET]")
        return render_template("login.html", user=current_user())

    # data z formuláře
    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    app.logger.info(f"Pokus o login: username='{username}'")

    if not username or not password:
        app.logger.warning("Login selhal: chybí username nebo password.")
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()

    # hledání uživatele podle username
    row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?;",
        (username,),
    ).fetchone()

    conn.close()

    # když uživatel neexistuje nebo nesedí heslo
    if row is None or not check_password_hash(row["password_hash"], password):
        app.logger.warning(f"Login selhal pro username='{username}'")
        flash("Špatné uživatelské jméno nebo heslo.", "error")
        return redirect(url_for("login"))

    # uložení uživatele do session
    # session si Flask drží mezi requesty, takže uživatel zůstane přihlášený
    session["user_id"] = int(row["id"])
    session["username"] = row["username"]
    session["role"] = row["role"]

    # po loginu se zajistí aktivní auto
    ensure_active_car_in_session()

    app.logger.info(
        f"Login úspěšný: user_id={row['id']}, username='{row['username']}', role='{row['role']}'"
    )

    flash(f"Přihlášen jako {row['username']}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    # odhlášení uživatele
    # session se kompletně vymaže

    username = session.get("username")
    user_id = session.get("user_id")

    app.logger.info(f"Logout: user_id={user_id}, username='{username}'")

    # vymazání celé session
    session.clear()

    flash("Odhlášeno.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    # dashboard je dostupný jen přihlášenému uživateli
    # nepřihlášený uživatel bude přesměrován na login

    if not login_required():
        app.logger.warning("Přístup na /dashboard bez přihlášení.")
        flash("Nejdřív se přihlas.", "error")
        return redirect(url_for("login"))

    user = current_user()
    assert user is not None
    # assert je tu pojistka pro typovou kontrolu
    # logicky by user už neměl být None, protože login_required prošel

    user_id = int(user["id"])

    app.logger.info(f"Návštěva dashboardu: user_id={user_id}, username='{user['username']}'")

    # načtení aut a aktivního auta
    cars = get_all_cars()
    active_car_id = ensure_active_car_in_session()

    # načtení posledního příkazu ze souboru JSON
    # tady je vidět část projektu "načítání dat ze souboru"
    last_command = load_last_command()

    conn = get_db_connection()

    if admin_required():
        # admin vidí všechny jízdy
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
        # běžný uživatel vidí jen svoje jízdy
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

    # převod výsledků z DB na obyčejné slovníky
    rides = [dict(r) for r in rows]

    return render_template(
        "dashboard.html",
        user=user,
        cars=cars,
        active_car_id=active_car_id,
        rides=rides,
        arduino_available=ARDUINO_AVAILABLE,
        arduino_error=ARDUINO_IMPORT_ERROR,
        last_command=last_command,
    )
    # dashboard.html potom dostane:
    # - přihlášeného uživatele
    # - seznam aut
    # - aktivní auto
    # - seznam jízd
    # - informaci, jestli je dostupné Arduino
    # - případnou chybu Arduina
    # - poslední příkaz načtený ze souboru


@app.route("/api/select_car", methods=["POST"])
def api_select_car():
    # API endpoint pro změnu aktivního auta
    # volá ho frontend JS, ne klasický HTML formulář

    if not login_required():
        app.logger.warning("api/select_car: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    # načtení JSON těla requestu
    # silent=True znamená, že při špatném JSON request nespadne
    data = request.get_json(silent=True) or {}
    car_id = data.get("car_id")

    try:
        car_id_int = int(car_id)
    except Exception:
        app.logger.warning(f"api/select_car: neplatné car_id='{car_id}'")
        return jsonify({"error": "Invalid car_id"}), 400

    if not car_exists(car_id_int):
        app.logger.warning(f"api/select_car: auto neexistuje, car_id={car_id_int}")
        return jsonify({"error": "Car not found"}), 404

    # uložení auta do session
    # tím se zapamatuje vybrané auto i pro další requesty
    session["active_car_id"] = car_id_int

    app.logger.info(
        f"Uživatel user_id={session.get('user_id')} vybral active_car_id={car_id_int}"
    )

    return jsonify({"ok": True, "active_car_id": car_id_int})


@app.route("/api/control", methods=["POST"])
def api_control():
    """
    Ovládání serva a motoru přes Arduino.

    Povolené příkazy:
      STEER:L
      STEER:R
      STEER:C
      THROTTLE:ON
      THROTTLE:OFF
    """

    # jen pro přihlášené
    if not login_required():
        app.logger.warning("api/control: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    # JSON data z frontend JS
    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()

    # whitelist povolených příkazů
    # tím omezíme, co smí frontend poslat dál do Arduina
    allowed = {
        "STEER:L",
        "STEER:R",
        "STEER:C",
        "THROTTLE:ON",
        "THROTTLE:OFF",
    }

    if cmd not in allowed:
        app.logger.warning(f"api/control: nepovolený příkaz '{cmd}'")
        return jsonify({"error": "Command not allowed"}), 400

    # pokud není dostupný Arduino modul
    if not ARDUINO_AVAILABLE:
        app.logger.error(f"api/control: Arduino není dostupné: {ARDUINO_IMPORT_ERROR}")
        return jsonify({"error": f"Arduino není dostupné: {ARDUINO_IMPORT_ERROR}"}), 500

    try:
        # odeslání příkazu do Arduina
        # samotné posílání přes serial řeší arduino_comm.py
        arduino_comm.send_line(cmd)  # type: ignore[union-attr]

        # po úspěšném odeslání příkazu si ten příkaz uložíme do JSON souboru
        # tohle je část "ukládání dat do souboru"
        save_last_command(cmd)

        app.logger.info(
            f"api/control: user_id={session.get('user_id')} poslal příkaz '{cmd}'"
        )
    except Exception as e:
        app.logger.error(f"api/control: Arduino send failed: {e}")
        return jsonify({"error": f"Arduino send failed: {e}"}), 500

    return jsonify({"ok": True, "sent": cmd})


@app.route("/api/ride/start", methods=["POST"])
def api_ride_start():
    # start nové jízdy
    # vytvoří nový záznam v tabulce rides
    # duration_sec je na začátku NULL, protože jízda ještě běží

    if not login_required():
        app.logger.warning("api/ride/start: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    user_id = int(session["user_id"])
    car_id = ensure_active_car_in_session()

    if car_id is None:
        # bez auta nemá smysl jízdu zakládat
        app.logger.warning(f"api/ride/start: user_id={user_id}, žádné auto v databázi.")
        return jsonify({"error": "No cars in database"}), 400

    conn = get_db_connection()

    # kontrola, jestli už uživatel nemá aktivní nedokončenou jízdu
    # tím zabráníme tomu, aby měl zároveň spuštěných víc jízd
    active = conn.execute(
        "SELECT id FROM rides WHERE user_id = ? AND duration_sec IS NULL ORDER BY id DESC LIMIT 1;",
        (user_id,),
    ).fetchone()

    if active:
        conn.close()
        app.logger.warning(
            f"api/ride/start: user_id={user_id} už má aktivní jízdu ride_id={active['id']}"
        )
        return jsonify({"error": "Ride already running", "ride_id": int(active["id"])}), 409

    # vložení nové jízdy
    # started_at se typicky doplní v DB default hodnotou
    cur = conn.execute(
        "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, NULL);",
        (user_id, int(car_id)),
    )

    conn.commit()

    # id nově vytvořené jízdy
    ride_id = int(cur.lastrowid)

    conn.close()

    app.logger.info(
        f"api/ride/start: user_id={user_id} spustil jízdu ride_id={ride_id}, car_id={car_id}"
    )

    return jsonify({"ok": True, "ride_id": ride_id, "car_id": int(car_id)})


@app.route("/api/ride/stop", methods=["POST"])
def api_ride_stop():
    # ukončení aktivní jízdy
    # najde poslední běžící jízdu uživatele a dopočítá její délku

    if not login_required():
        app.logger.warning("api/ride/stop: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    user_id = int(session["user_id"])
    conn = get_db_connection()

    # najdeme poslední nedokončenou jízdu uživatele
    row = conn.execute(
        """
        SELECT id
        FROM rides
        WHERE user_id = ? AND duration_sec IS NULL
        ORDER BY id DESC
        LIMIT 1;
        """,
        (user_id,),
    ).fetchone()

    if not row:
        conn.close()
        app.logger.warning(f"api/ride/stop: user_id={user_id} nemá aktivní jízdu.")
        return jsonify({"error": "No running ride"}), 404

    ride_id = int(row["id"])

    # dopočet délky jízdy v sekundách
    # julianday('now') vrátí aktuální čas
    # odečte se started_at a výsledek se přepočítá na sekundy
    conn.execute(
        """
        UPDATE rides
        SET duration_sec = CAST((julianday('now') - julianday(started_at)) * 86400 AS INTEGER)
        WHERE id = ?;
        """,
        (ride_id,),
    )

    conn.commit()

    # načtení uložené délky
    duration_row = conn.execute(
        "SELECT duration_sec FROM rides WHERE id = ?;",
        (ride_id,),
    ).fetchone()

    conn.close()

    duration = int(duration_row["duration_sec"]) if duration_row and duration_row["duration_sec"] is not None else 0

    # pojistka pro případ záporné hodnoty
    # teoreticky by neměla nastat, ale je lepší ji ošetřit
    if duration < 0:
        duration = 0

    app.logger.info(
        f"api/ride/stop: user_id={user_id} ukončil jízdu ride_id={ride_id}, duration_sec={duration}"
    )

    return jsonify({"ok": True, "ride_id": ride_id, "duration_sec": duration})


@app.route("/admin")
def admin():
    # admin panel je jen pro admina
    # běžný uživatel sem nesmí

    if not admin_required():
        app.logger.warning(
            f"Pokus o přístup na /admin bez oprávnění. user_id={session.get('user_id')}"
        )
        abort(403)

    app.logger.info(f"Admin panel otevřen user_id={session.get('user_id')}")

    conn = get_db_connection()

    # načtení všech uživatelů
    users_rows = conn.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY id;"
    ).fetchall()

    # načtení všech aut
    cars_rows = conn.execute(
        "SELECT id, name, power_limit_percent, steer_angle_deg, created_at FROM cars ORDER BY id;"
    ).fetchall()

    # načtení všech jízd
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
    # admin.html tak dostane kompletní přehled celé aplikace:
    # - seznam uživatelů
    # - seznam aut
    # - seznam jízd
    # - stav Arduino modulu


@app.route("/admin/ride/<int:ride_id>/delete", methods=["POST"])
def admin_delete_ride(ride_id: int):
    # smazání jízdy adminem
    # route bere id jízdy přímo z URL

    if not admin_required():
        app.logger.warning(
            f"Pokus o smazání ride bez oprávnění. ride_id={ride_id}, user_id={session.get('user_id')}"
        )
        abort(403)

    conn = get_db_connection()

    cur = conn.execute("DELETE FROM rides WHERE id = ?;", (ride_id,))
    conn.commit()
    conn.close()

    if cur.rowcount:
        # rowcount > 0 znamená, že se opravdu něco smazalo
        app.logger.info(f"Admin smazal jízdu ride_id={ride_id}")
    else:
        # jinak ride s tímto id neexistovala
        app.logger.warning(f"Admin mazal neexistující jízdu ride_id={ride_id}")

    flash(
        "Jízda smazána." if cur.rowcount else "Jízda nenalezena.",
        "success" if cur.rowcount else "error"
    )
    return redirect(url_for("admin"))


@app.route("/admin/user/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id: int):
    # smazání uživatele adminem

    if not admin_required():
        app.logger.warning(
            f"Pokus o smazání user bez oprávnění. target_user_id={user_id}, actor={session.get('user_id')}"
        )
        abort(403)

    # admin nemůže smazat sám sebe
    # tím si nezruší vlastní přístup do aplikace
    if int(session.get("user_id", -1)) == user_id:
        app.logger.warning(f"Admin se pokusil smazat sám sebe. user_id={user_id}")
        flash("Nemůžeš smazat sám sebe.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection()

    cur = conn.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    conn.commit()
    conn.close()

    if cur.rowcount:
        app.logger.info(f"Admin smazal uživatele user_id={user_id}")
    else:
        app.logger.warning(f"Admin mazal neexistujícího uživatele user_id={user_id}")

    flash(
        "Uživatel smazán." if cur.rowcount else "Uživatel nenalezen.",
        "success" if cur.rowcount else "error"
    )
    return redirect(url_for("admin"))


@app.route("/admin/car/<int:car_id>/delete", methods=["POST"])
def admin_delete_car(car_id: int):
    # smazání auta adminem

    if not admin_required():
        app.logger.warning(
            f"Pokus o smazání auta bez oprávnění. car_id={car_id}, actor={session.get('user_id')}"
        )
        abort(403)

    conn = get_db_connection()

    cur = conn.execute("DELETE FROM cars WHERE id = ?;", (car_id,))
    conn.commit()
    conn.close()

    if cur.rowcount:
        app.logger.info(f"Admin smazal auto car_id={car_id}")
    else:
        app.logger.warning(f"Admin mazal neexistující auto car_id={car_id}")

    flash(
        "Auto smazáno." if cur.rowcount else "Auto nenalezeno.",
        "success" if cur.rowcount else "error"
    )
    return redirect(url_for("admin"))


if __name__ == "__main__":
    # přímé spuštění Flask app
    # tenhle blok se vykoná jen tehdy, když se app.py spustí přímo

    # při startu ještě jednou ověříme, že soubor pro poslední příkaz existuje
    ensure_last_command_file()

    app.logger.info("Spouštím Flask server na 0.0.0.0:5000 v debug režimu.")
    app.run(debug=True, host="0.0.0.0", port=5000)
    # debug=True = automatický reload při změně kódu + detailnější chybové hlášky
    # host="0.0.0.0" = server je dostupný i z jiné zařízení v síti
    # port=5000 = standardní port pro Flask