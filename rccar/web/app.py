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
- ukládání a načítání času poslední akce ze souboru JSON
- synchronizaci úhlu zatáčení podle právě vybraného auta
- změnu hodnoty motoru MOTOR_ON v rozsahu 1200 až 1300

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
# v praxi to znamená, že třeba Optional[int] nebo Dict[str, Any]
# fungují pohodlněji i v novějších stylech psaní kódu

import json
# práce s JSON soubory
# tady se používá hlavně pro last_command.json
# do toho souboru se ukládá čas poslední akce

import logging
# knihovna pro logování do konzole
# logy se hodí při testování i při ukázce projektu
# můžeme v nich sledovat, co backend právě dělá

import sqlite3
# vestavěná knihovna pro SQLite databázi
# přes ni čteme a zapisujeme uživatele, auta a jízdy

import sys
# používá se tady hlavně kvůli stdout pro logging
# tedy aby se logy vypisovaly do konzole / terminálu

from datetime import datetime
# používá se pro uložení času poslední akce do JSON souboru
# čas ukládáme jako text ve formátu YYYY-MM-DD HH:MM:SS

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
# generate_password_hash() vytvoří hash
# check_password_hash() porovná zadané heslo s hashem z databáze


# ------------------------------------------------------------
# 0) Arduino bridge
# ------------------------------------------------------------
# Tahle část se snaží načíst modul pro komunikaci s Arduinem.
# Když import selže, web se úplně nezastaví.
# Jen si poznamená, že Arduino momentálně není dostupné.

ARDUINO_AVAILABLE = True
# předpokládáme, že Arduino modul půjde načíst
# pokud import selže, přepne se to na False

ARDUINO_IMPORT_ERROR = ""
# sem se uloží text chyby importu
# potom se může zobrazit v dashboardu nebo v adminu

try:
    import arduino_comm  # web/arduino_comm.py
    # pokud se import povede, máme k dispozici funkci send_line()
    # a další logiku z arduino_comm.py
except Exception as e:
    # když import selže, aplikace nespadne
    # jen si uloží, že Arduino není dostupné
    ARDUINO_AVAILABLE = False
    ARDUINO_IMPORT_ERROR = str(e)
    arduino_comm = None  # type: ignore
    # nastavíme proměnnou aspoň na None,
    # aby existovala i v případě chyby


# ------------------------------------------------------------
# 1) Cesty k databázi a schema.sql
# ------------------------------------------------------------
# Tady si připravíme absolutní cesty k důležitým souborům projektu.

BASE_DIR = Path(__file__).resolve().parent
# složka, ve které je app.py
# typicky tedy /web

PROJECT_ROOT = BASE_DIR.parent
# root projektu = o úroveň výš
# tím se dostaneme z /web na hlavní složku projektu

DB_PATH = PROJECT_ROOT / "database" / "rccar.db"
# cesta k SQLite databázi
# databáze je uložená ve složce /database

SCHEMA_PATH = PROJECT_ROOT / "database" / "schema.sql"
# cesta k SQL schématu
# schema.sql obsahuje CREATE TABLE a indexy


# ------------------------------------------------------------
# 1.1) Cesta k JSON souboru s časem poslední akce
# ------------------------------------------------------------

LAST_COMMAND_PATH = BASE_DIR / "last_command.json"
# soubor je uložený vedle app.py ve složce /web
# přestože se jmenuje last_command.json,
# v aktuální verzi už neukládá poslední příkaz,
# ale jen čas poslední akce


# ------------------------------------------------------------
# 1.2) Výchozí hodnota zapnutí motoru
# ------------------------------------------------------------
# tahle hodnota se bude zobrazovat na dashboardu jako předvyplněná
# a zároveň ji posíláme do Arduina při otevření dashboardu nebo po loginu

DEFAULT_MOTOR_ON_VALUE = 1200
# základní hodnota pro zapnutí motoru
# uživatel si ji může změnit v rozsahu 1200 až 1300


# ------------------------------------------------------------
# 2) Flask aplikace
# ------------------------------------------------------------

app = Flask(__name__, static_folder="static", static_url_path="/static")
# vytvoření Flask aplikace
# static_folder="static" znamená, že statické soubory jsou ve složce /web/static
# static_url_path="/static" znamená, že budou dostupné přes URL /static/...

app.config["SECRET_KEY"] = "CHANGE_ME_TO_SOMETHING_RANDOM_AND_SECRET"
# tajný klíč pro session
# Flask ho používá pro podepisování session cookies
# v ostrém provozu by měl být dlouhý, náhodný a neveřejný


# ------------------------------------------------------------
# 2.1) Logging
# ------------------------------------------------------------

def setup_logging() -> None:
    # tahle funkce nastaví logování Flask aplikace do konzole
    # chceme mít pěkně formátované výpisy o tom,
    # co aplikace dělá

    handler = logging.StreamHandler(sys.stdout)
    # StreamHandler vypisuje logy do proudu
    # tady konkrétně do stdout = terminálu / konzole

    handler.setLevel(logging.INFO)
    # od této úrovně výš se budou zprávy vypisovat
    # INFO, WARNING, ERROR...

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
    )
    # formát logu:
    # - čas
    # - úroveň
    # - modul
    # - samotná zpráva

    handler.setFormatter(formatter)
    # handler bude používat tento formát

    app.logger.setLevel(logging.INFO)
    # nastavíme úroveň logování i pro Flask logger

    if not app.logger.handlers:
        app.logger.addHandler(handler)
        # přidáme handler jen tehdy,
        # když tam ještě žádný není
        # tím se vyhneme duplicitním logům při reloadu


setup_logging()
# zavoláme nastavení logování hned při startu aplikace

app.logger.info("Aplikace RCcar startuje.")
app.logger.info(f"DB_PATH = {DB_PATH}")
app.logger.info(f"SCHEMA_PATH = {SCHEMA_PATH}")
app.logger.info(f"LAST_COMMAND_PATH = {LAST_COMMAND_PATH}")
# úvodní logy nám pomůžou při ladění
# hned vidíme, s jakými cestami aplikace pracuje

if ARDUINO_AVAILABLE:
    app.logger.info("Arduino modul byl úspěšně načten.")
else:
    app.logger.warning(f"Arduino modul není dostupný: {ARDUINO_IMPORT_ERROR}")
# podle výsledku importu vypíšeme informaci nebo varování


# ------------------------------------------------------------
# 3) Helpery pro databázi
# ------------------------------------------------------------

def get_db_connection() -> sqlite3.Connection:
    # vytvoří nové připojení k SQLite databázi
    # tuhle funkci používáme téměř všude,
    # kde potřebujeme sahat do DB

    conn = sqlite3.connect(DB_PATH)
    # otevření připojení k souboru databáze

    conn.row_factory = sqlite3.Row
    # díky tomu se výsledky SQL dají číst přes názvy sloupců
    # např. row["id"] místo row[0]

    conn.execute("PRAGMA foreign_keys = ON;")
    # zapnutí cizích klíčů
    # ve SQLite bývají defaultně vypnuté,
    # takže to radši aktivujeme při každém spojení

    return conn


def init_db() -> None:
    # tahle funkce načte schema.sql a vytvoří / aktualizuje tabulky
    # volá se při startu aplikace

    if not SCHEMA_PATH.exists():
        # pokud schema.sql neexistuje,
        # nemá backend z čeho vytvořit tabulky
        app.logger.error(f"Chybí schema.sql: {SCHEMA_PATH}")
        raise FileNotFoundError(f"Chybí schema.sql: {SCHEMA_PATH}")

    app.logger.info("Inicializuji databázi ze schema.sql")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    # načteme celý obsah schema.sql jako text

    conn = get_db_connection()
    # otevřeme spojení do databáze

    conn.executescript(schema_sql)
    # executescript umí spustit více SQL příkazů najednou
    # typicky CREATE TABLE a CREATE INDEX

    conn.commit()
    # uloží změny

    conn.close()
    # zavře spojení

    app.logger.info("Databáze inicializována.")


init_db()
# databázi inicializujeme hned při startu aplikace
# takže tabulky existují dřív,
# než přijde první request od uživatele


# ------------------------------------------------------------
# 3.1) Helpery pro práci se souborem last_command.json
# ------------------------------------------------------------

def ensure_last_command_file() -> None:
    """
    Zajistí, že existuje soubor last_command.json
    a že obsahuje platný základní JSON.
    """
    default_data = {
        "time": None,
    }
    # výchozí obsah souboru
    # zatím neznáme čas poslední akce

    try:
        if not LAST_COMMAND_PATH.exists():
            # když soubor neexistuje, vytvoříme nový
            LAST_COMMAND_PATH.write_text(
                json.dumps(default_data, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )
            app.logger.info("Vytvořen nový soubor last_command.json")
            return

        raw = LAST_COMMAND_PATH.read_text(encoding="utf-8").strip()
        # načteme obsah souboru jako text a ořízneme mezery

        if not raw:
            # pokud je soubor prázdný, přepíšeme ho výchozím JSONem
            LAST_COMMAND_PATH.write_text(
                json.dumps(default_data, indent=4, ensure_ascii=False),
                encoding="utf-8"
            )
            app.logger.warning("Soubor last_command.json byl prázdný, byl opraven.")
            return

        data = json.loads(raw)
        # pokusíme se text převést na Python objekt

        if not isinstance(data, dict):
            # očekáváme JSON objekt / slovník
            raise ValueError("last_command.json nemá objekt JSON")

        if "time" not in data:
            # pokud chybí klíč time, doplníme ho
            data["time"] = None

        if "cmd" in data:
            # z dřívější verze mohl v souboru zůstat klíč "cmd"
            # ten už nechceme používat, tak ho smažeme
            del data["cmd"]

        LAST_COMMAND_PATH.write_text(
            json.dumps(data, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )
        # soubor znovu uložíme pěkně zformátovaný

    except Exception as e:
        # když je soubor poškozený nebo nečitelný,
        # obnovíme ho do výchozího stavu
        app.logger.warning(f"Soubor last_command.json byl poškozený, obnovuji ho: {e}")
        LAST_COMMAND_PATH.write_text(
            json.dumps(default_data, indent=4, ensure_ascii=False),
            encoding="utf-8"
        )


def load_last_action() -> Dict[str, Any]:
    """
    Načte čas poslední akce ze souboru last_command.json.
    """
    ensure_last_command_file()
    # nejdřív se ujistíme, že soubor existuje a má správný formát

    try:
        data = json.loads(LAST_COMMAND_PATH.read_text(encoding="utf-8"))
        # načteme JSON do Python slovníku

        return {
            "time": data.get("time"),
        }
        # vrátíme slovník se stejným klíčem,
        # jaký se očekává v dashboardu

    except Exception as e:
        # kdyby načítání selhalo, vrátíme bezpečný výchozí stav
        app.logger.error(f"Nepodařilo se načíst last_command.json: {e}")
        return {
            "time": None,
        }


def save_last_action_time() -> None:
    """
    Uloží čas poslední akce do JSON souboru.
    """
    data = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    # vytvoříme nový slovník s aktuálním časem

    LAST_COMMAND_PATH.write_text(
        json.dumps(data, indent=4, ensure_ascii=False),
        encoding="utf-8"
    )
    # uložíme JSON do souboru

    app.logger.info(f"Uložen čas poslední akce do souboru: {data}")
    # vypíšeme informaci do logu


ensure_last_command_file()
# zajistíme existenci souboru už při startu aplikace


# ------------------------------------------------------------
# 4) Helpery pro přihlášení a role
# ------------------------------------------------------------

def current_user() -> Optional[Dict[str, Any]]:
    # vrátí základní info o právě přihlášeném uživateli
    # nebo None, pokud nikdo přihlášený není

    if "user_id" not in session:
        return None
        # když session neobsahuje user_id,
        # uživatel není přihlášený

    return {
        "id": session.get("user_id"),
        "username": session.get("username"),
        "role": session.get("role"),
    }
    # vrátíme malý slovník s informacemi o uživateli
    # ten se pak hodí třeba do šablon


def login_required() -> bool:
    # jednoduchá kontrola, jestli je uživatel přihlášený
    return "user_id" in session


def admin_required() -> bool:
    # kontrola, jestli je uživatel přihlášený a zároveň admin
    return login_required() and session.get("role") == "admin"


# ------------------------------------------------------------
# 5) Helpery pro auta
# ------------------------------------------------------------

def get_all_cars() -> List[Dict[str, Any]]:
    # načte všechna auta z databáze

    conn = get_db_connection()

    rows = conn.execute(
        """
        SELECT id, name, color, steer_angle_deg, created_at
        FROM cars
        ORDER BY id;
        """
    ).fetchall()
    # načteme všechna auta
    # ORDER BY id zajistí stabilní pořadí

    conn.close()

    return [dict(r) for r in rows]
    # sqlite Row převedeme na obyčejné slovníky,
    # se kterými se lépe pracuje v Pythonu i v Jinja


def get_car_by_id(car_id: int) -> Optional[Dict[str, Any]]:
    # načte jedno konkrétní auto podle id

    conn = get_db_connection()

    row = conn.execute(
        """
        SELECT id, name, color, steer_angle_deg, created_at
        FROM cars
        WHERE id = ?
        LIMIT 1;
        """,
        (car_id,),
    ).fetchone()
    # parametrizovaný dotaz chrání proti SQL injection
    # LIMIT 1 znamená, že čekáme maximálně jeden řádek

    conn.close()

    return dict(row) if row else None
    # pokud auto existuje, vrátíme slovník
    # jinak vrátíme None


def car_exists(car_id: int) -> bool:
    # ověří, jestli auto s daným id existuje

    conn = get_db_connection()

    row = conn.execute(
        "SELECT 1 FROM cars WHERE id = ? LIMIT 1;",
        (car_id,)
    ).fetchone()
    # SELECT 1 je rychlý způsob,
    # jak jen ověřit existenci řádku

    conn.close()
    return row is not None


def ensure_active_car_in_session() -> Optional[int]:
    # zajistí, že v session bude vybrané nějaké aktivní auto
    # když tam žádné není, nastaví první dostupné

    cars = get_all_cars()

    if not cars:
        # pokud v databázi nejsou žádná auta
        session.pop("active_car_id", None)
        app.logger.warning("V databázi nejsou žádná auta.")
        return None

    active = session.get("active_car_id")
    # zkusíme vzít id auta ze session

    try:
        active_int = int(active) if active is not None else None
        # převedeme hodnotu na int
    except Exception:
        active_int = None
        # když je ve session něco divného, ignorujeme to

    if active_int is not None and car_exists(active_int):
        return active_int
        # pokud je session validní a auto existuje, vrátíme ho

    session["active_car_id"] = int(cars[0]["id"])
    # jinak nastavíme první auto jako výchozí

    app.logger.info(f"Nastavuji výchozí active_car_id = {cars[0]['id']}")
    return int(cars[0]["id"])


def sync_active_car_to_arduino(car_id: Optional[int]) -> bool:
    """
    Pošle do Arduina aktuální úhel zatáčení podle vybraného auta.
    """

    if car_id is None:
        return False
        # bez id auta nemáme co synchronizovat

    if not ARDUINO_AVAILABLE:
        return False
        # když Arduino není dostupné, nemá smysl pokračovat

    car = get_car_by_id(int(car_id))
    if not car:
        return False
        # pokud auto v DB neexistuje, končíme

    angle = int(car["steer_angle_deg"])
    # vezmeme úhel zatáčení daného auta

    try:
        arduino_comm.send_line(f"STEER_ANGLE:{angle}")  # type: ignore[union-attr]
        # pošleme do Arduina textový příkaz,
        # aby si nastavilo úhel zatáčení pro dané auto

        app.logger.info(
            f"Synchronizován úhel zatáčení do Arduina: car_id={car_id}, steer_angle_deg={angle}"
        )
        return True
    except Exception as e:
        app.logger.error(f"Nepodařilo se synchronizovat úhel zatáčení do Arduina: {e}")
        return False


def get_motor_on_value() -> int:
    """
    Vrátí aktuálně nastavenou hodnotu pro zapnutí motoru.

    Hodnota se drží v session, aby si ji uživatel mohl změnit za běhu.
    Pokud tam není nebo je neplatná, vrátí se výchozí 1200.
    """
    raw = session.get("motor_on_value", DEFAULT_MOTOR_ON_VALUE)
    # vezmeme hodnotu ze session
    # nebo výchozí 1200, pokud tam nic není

    try:
        value = int(raw)
    except Exception:
        value = DEFAULT_MOTOR_ON_VALUE
        # když je ve session neplatná hodnota, vrátíme default

    if value < 1200 or value > 1300:
        value = DEFAULT_MOTOR_ON_VALUE
        # mimo rozsah nepovolíme

    session["motor_on_value"] = value
    # uložíme zpět už očištěnou / zvalidovanou hodnotu

    return value


def sync_motor_on_value_to_arduino(value: int) -> bool:
    """
    Pošle do Arduina aktuální hodnotu pro MOTOR_ON.

    Povolený rozsah:
    1200 až 1300
    """

    if not ARDUINO_AVAILABLE:
        return False
        # bez Arduina nic neposíláme

    if value < 1200 or value > 1300:
        return False
        # ochrana rozsahu i na backendu

    try:
        arduino_comm.send_line(f"MOTOR_ON_VALUE:{value}")  # type: ignore[union-attr]
        # pošleme hodnotu do Arduina,
        # které si podle ní nastaví sílu / hodnotu motoru

        app.logger.info(f"Synchronizována hodnota MOTOR_ON do Arduina: {value}")
        return True
    except Exception as e:
        app.logger.error(f"Nepodařilo se synchronizovat MOTOR_ON_VALUE do Arduina: {e}")
        return False


# ------------------------------------------------------------
# 6) ROUTES – stránky
# ------------------------------------------------------------
# Tady začínají jednotlivé URL adresy aplikace.

@app.route("/")
def index():
    # hlavní stránka projektu
    app.logger.info("Návštěva stránky /")
    return render_template("index.html", user=current_user())
    # do šablony posíláme i current_user(),
    # aby base.html věděl, zda je někdo přihlášený


@app.route("/info")
def info():
    # info stránka o projektu
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

    username = (request.form.get("username") or "").strip()
    # načtení username z formuláře
    # or "" chrání před None
    # strip() odstraní mezery okolo

    password = request.form.get("password") or ""
    # načtení hesla

    role = (request.form.get("role") or "user").strip().lower()
    # načtení role
    # když nepřijde nic, použije se "user"
    # lower() sjednotí zápis třeba ADMIN -> admin

    app.logger.info(f"Pokus o registraci: username='{username}', role='{role}'")

    if not username or not password:
        # bez username a hesla nemá smysl pokračovat
        app.logger.warning("Registrace selhala: chybí username nebo password.")
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("register"))

    if role not in ("user", "admin"):
        # ochrana, aby do DB nešla neplatná role
        app.logger.warning(f"Registrace selhala: neplatná role '{role}'")
        flash("Role musí být 'user' nebo 'admin'.", "error")
        return redirect(url_for("register"))

    pw_hash = generate_password_hash(password)
    # heslo převedeme na hash
    # do DB tedy nepůjde otevřený text

    try:
        conn = get_db_connection()

        conn.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?);",
            (username, pw_hash, role),
        )
        # vložení nového uživatele do databáze

        conn.commit()
        # uloží změny

        conn.close()

        app.logger.info(f"Registrace úspěšná: username='{username}', role='{role}'")

    except sqlite3.IntegrityError:
        # typicky když už username existuje
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

    username = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    app.logger.info(f"Pokus o login: username='{username}'")

    if not username or not password:
        app.logger.warning("Login selhal: chybí username nebo password.")
        flash("Vyplň uživatelské jméno i heslo.", "error")
        return redirect(url_for("login"))

    conn = get_db_connection()

    row = conn.execute(
        "SELECT id, username, password_hash, role FROM users WHERE username = ?;",
        (username,),
    ).fetchone()
    # najdeme uživatele podle username

    conn.close()

    if row is None or not check_password_hash(row["password_hash"], password):
        # pokud uživatel neexistuje
        # nebo nesedí heslo
        app.logger.warning(f"Login selhal pro username='{username}'")
        flash("Špatné uživatelské jméno nebo heslo.", "error")
        return redirect(url_for("login"))

    session["user_id"] = int(row["id"])
    session["username"] = row["username"]
    session["role"] = row["role"]
    # uložíme informace do session
    # od teď je uživatel považovaný za přihlášeného

    active_car_id = ensure_active_car_in_session()
    # po loginu zajistíme, že existuje aktivní auto

    sync_active_car_to_arduino(active_car_id)
    # pošleme do Arduina úhel aktivního auta

    sync_motor_on_value_to_arduino(get_motor_on_value())
    # po loginu se do Arduina pošle i aktuální hodnota motoru

    app.logger.info(
        f"Login úspěšný: user_id={row['id']}, username='{row['username']}', role='{row['role']}'"
    )

    flash(f"Přihlášen jako {row['username']}.", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    # odhlášení uživatele

    username = session.get("username")
    user_id = session.get("user_id")
    # uložíme si info do logu ještě před vymazáním session

    app.logger.info(f"Logout: user_id={user_id}, username='{username}'")

    session.clear()
    # smažeme celou session

    flash("Odhlášeno.", "info")
    return redirect(url_for("index"))


@app.route("/dashboard")
def dashboard():
    # dashboard je dostupný jen přihlášenému uživateli

    if not login_required():
        app.logger.warning("Přístup na /dashboard bez přihlášení.")
        flash("Nejdřív se přihlas.", "error")
        return redirect(url_for("login"))

    user = current_user()
    assert user is not None
    # assert je tu hlavně pro typovou jistotu
    # logicky už víme, že uživatel je přihlášený

    user_id = int(user["id"])

    app.logger.info(f"Návštěva dashboardu: user_id={user_id}, username='{user['username']}'")

    cars = get_all_cars()
    # načteme auta do dropdownu

    active_car_id = ensure_active_car_in_session()
    # zajistíme, že nějaké aktivní auto existuje

    sync_active_car_to_arduino(active_car_id)
    # při otevření dashboardu znovu synchronizujeme úhel

    motor_on_value = get_motor_on_value()
    # načteme aktuální hodnotu motoru ze session

    sync_motor_on_value_to_arduino(motor_on_value)
    # a pošleme ji do Arduina

    last_action = load_last_action()
    # načteme čas poslední akce z JSON souboru

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

    rides = [dict(r) for r in rows]
    # výsledky převedeme na obyčejné slovníky

    return render_template(
        "dashboard.html",
        user=user,
        cars=cars,
        active_car_id=active_car_id,
        rides=rides,
        arduino_available=ARDUINO_AVAILABLE,
        arduino_error=ARDUINO_IMPORT_ERROR,
        last_action=last_action,
        motor_on_value=motor_on_value,
    )
    # dashboard dostane vše potřebné pro vykreslení stránky


@app.route("/api/select_car", methods=["POST"])
def api_select_car():
    # API endpoint pro změnu aktivního auta
    # volá ho JavaScript z dashboardu

    if not login_required():
        app.logger.warning("api/select_car: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    # načteme JSON tělo requestu
    # silent=True zabrání pádu při špatném JSON

    car_id = data.get("car_id")

    try:
        car_id_int = int(car_id)
    except Exception:
        app.logger.warning(f"api/select_car: neplatné car_id='{car_id}'")
        return jsonify({"error": "Invalid car_id"}), 400

    car = get_car_by_id(car_id_int)
    if not car:
        app.logger.warning(f"api/select_car: auto neexistuje, car_id={car_id_int}")
        return jsonify({"error": "Car not found"}), 404

    session["active_car_id"] = car_id_int
    # nové auto si uložíme do session

    synced = sync_active_car_to_arduino(car_id_int)
    # a pošleme jeho úhel do Arduina

    app.logger.info(
        f"Uživatel user_id={session.get('user_id')} vybral active_car_id={car_id_int}"
    )

    return jsonify({
        "ok": True,
        "active_car_id": car_id_int,
        "steer_angle_deg": int(car["steer_angle_deg"]),
        "synced_to_arduino": synced,
    })
    # vrátíme JSON odpověď pro frontend


@app.route("/api/set_motor_on_value", methods=["POST"])
def api_set_motor_on_value():
    """
    API endpoint pro změnu hodnoty MOTOR_ON.

    Povolený rozsah:
    1200 až 1300
    """

    if not login_required():
        app.logger.warning("api/set_motor_on_value: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    value = data.get("value")
    # načteme hodnotu poslanou z JavaScriptu

    try:
        value_int = int(value)
    except Exception:
        app.logger.warning(f"api/set_motor_on_value: neplatná hodnota '{value}'")
        return jsonify({"error": "Hodnota musí být celé číslo."}), 400

    if value_int < 1200 or value_int > 1300:
        app.logger.warning(f"api/set_motor_on_value: hodnota mimo rozsah '{value_int}'")
        return jsonify({"error": "Hodnota musí být v rozsahu 1200 až 1300."}), 400

    session["motor_on_value"] = value_int
    # uložíme si hodnotu do session

    synced = sync_motor_on_value_to_arduino(value_int)
    # pošleme ji i do Arduina

    if not synced and ARDUINO_AVAILABLE:
        # pokud je Arduino dostupné,
        # ale synchronizace selhala, vrátíme chybu
        return jsonify({"error": "Nepodařilo se odeslat hodnotu do Arduina."}), 500

    save_last_action_time()
    # změna motoru je také akce,
    # takže uložíme čas poslední akce

    app.logger.info(
        f"api/set_motor_on_value: user_id={session.get('user_id')} nastavil MOTOR_ON_VALUE={value_int}"
    )

    return jsonify({
        "ok": True,
        "value": value_int,
        "sent_to_arduino": synced,
    })


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

    if not login_required():
        app.logger.warning("api/control: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    data = request.get_json(silent=True) or {}
    cmd = (data.get("cmd") or "").strip()
    # načteme příkaz z JSONu
    # strip() odstraní mezery a konce řádků

    allowed = {
        "STEER:L",
        "STEER:R",
        "STEER:C",
        "THROTTLE:ON",
        "THROTTLE:OFF",
    }
    # whitelist povolených příkazů
    # backend tak nepustí do Arduina cokoliv

    if cmd not in allowed:
        app.logger.warning(f"api/control: nepovolený příkaz '{cmd}'")
        return jsonify({"error": "Command not allowed"}), 400

    if not ARDUINO_AVAILABLE:
        app.logger.error(f"api/control: Arduino není dostupné: {ARDUINO_IMPORT_ERROR}")
        return jsonify({"error": f"Arduino není dostupné: {ARDUINO_IMPORT_ERROR}"}), 500

    try:
        if cmd.startswith("STEER:"):
            # před zatáčením pošleme aktivní úhel
            # tím zajistíme, že Arduino ví, o kolik má zatáčet
            sync_active_car_to_arduino(session.get("active_car_id"))

        if cmd == "THROTTLE:ON":
            # před zapnutím motoru pošleme aktuální hodnotu MOTOR_ON
            sync_motor_on_value_to_arduino(get_motor_on_value())

        arduino_comm.send_line(cmd)  # type: ignore[union-attr]
        # pošleme samotný příkaz do Arduina

        save_last_action_time()
        # uložíme čas poslední akce do JSON souboru

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

    if not login_required():
        app.logger.warning("api/ride/start: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    user_id = int(session["user_id"])
    # id přihlášeného uživatele

    car_id = ensure_active_car_in_session()
    # id aktuálně vybraného auta

    if car_id is None:
        # bez auta nemá smysl jízdu zakládat
        app.logger.warning(f"api/ride/start: user_id={user_id}, žádné auto v databázi.")
        return jsonify({"error": "No cars in database"}), 400

    conn = get_db_connection()

    active = conn.execute(
        "SELECT id FROM rides WHERE user_id = ? AND duration_sec IS NULL ORDER BY id DESC LIMIT 1;",
        (user_id,),
    ).fetchone()
    # zkontrolujeme, jestli už uživatel nemá rozjetou jízdu
    # duration_sec IS NULL znamená, že jízda ještě nebyla ukončena

    if active:
        conn.close()
        app.logger.warning(
            f"api/ride/start: user_id={user_id} už má aktivní jízdu ride_id={active['id']}"
        )
        return jsonify({"error": "Ride already running", "ride_id": int(active["id"])}), 409

    cur = conn.execute(
        "INSERT INTO rides (user_id, car_id, duration_sec) VALUES (?, ?, NULL);",
        (user_id, int(car_id)),
    )
    # založíme novou jízdu
    # duration_sec je zatím NULL, protože běží

    conn.commit()
    ride_id = int(cur.lastrowid)
    # uložíme id nově vytvořené jízdy

    conn.close()

    app.logger.info(
        f"api/ride/start: user_id={user_id} spustil jízdu ride_id={ride_id}, car_id={car_id}"
    )

    return jsonify({"ok": True, "ride_id": ride_id, "car_id": int(car_id)})


@app.route("/api/ride/stop", methods=["POST"])
def api_ride_stop():
    # ukončení aktivní jízdy

    if not login_required():
        app.logger.warning("api/ride/stop: nepřihlášený uživatel.")
        return jsonify({"error": "Not logged in"}), 401

    user_id = int(session["user_id"])
    conn = get_db_connection()

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
    # najdeme poslední nedokončenou jízdu uživatele

    if not row:
        conn.close()
        app.logger.warning(f"api/ride/stop: user_id={user_id} nemá aktivní jízdu.")
        return jsonify({"error": "No running ride"}), 404

    ride_id = int(row["id"])

    conn.execute(
        """
        UPDATE rides
        SET duration_sec = CAST((julianday('now') - julianday(started_at)) * 86400 AS INTEGER)
        WHERE id = ?;
        """,
        (ride_id,),
    )
    # dopočítáme délku jízdy v sekundách
    # julianday('now') - julianday(started_at) = rozdíl v dnech
    # * 86400 = převod na sekundy

    conn.commit()

    duration_row = conn.execute(
        "SELECT duration_sec FROM rides WHERE id = ?;",
        (ride_id,),
    ).fetchone()
    # načteme uloženou délku jízdy

    conn.close()

    duration = int(duration_row["duration_sec"]) if duration_row and duration_row["duration_sec"] is not None else 0
    # jistota, že dostaneme celé číslo

    if duration < 0:
        duration = 0
        # bezpečnostní pojistka

    app.logger.info(
        f"api/ride/stop: user_id={user_id} ukončil jízdu ride_id={ride_id}, duration_sec={duration}"
    )

    return jsonify({"ok": True, "ride_id": ride_id, "duration_sec": duration})


@app.route("/admin")
def admin():
    # admin panel je jen pro admina

    if not admin_required():
        app.logger.warning(
            f"Pokus o přístup na /admin bez oprávnění. user_id={session.get('user_id')}"
        )
        abort(403)
        # 403 = forbidden

    app.logger.info(f"Admin panel otevřen user_id={session.get('user_id')}")

    conn = get_db_connection()

    users_rows = conn.execute(
        "SELECT id, username, role, created_at FROM users ORDER BY id;"
    ).fetchall()
    # načtení všech uživatelů

    cars_rows = conn.execute(
        "SELECT id, name, color, steer_angle_deg, created_at FROM cars ORDER BY id;"
    ).fetchall()
    # načtení všech aut

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
    # načtení všech jízd včetně JOINů,
    # aby se rovnou zobrazovalo jméno uživatele a auta

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
    # smazání jízdy adminem

    if not admin_required():
        app.logger.warning(
            f"Pokus o smazání ride bez oprávnění. ride_id={ride_id}, user_id={session.get('user_id')}"
        )
        abort(403)

    conn = get_db_connection()

    cur = conn.execute("DELETE FROM rides WHERE id = ?;", (ride_id,))
    # smažeme konkrétní jízdu podle id

    conn.commit()
    conn.close()

    if cur.rowcount:
        app.logger.info(f"Admin smazal jízdu ride_id={ride_id}")
    else:
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

    if int(session.get("user_id", -1)) == user_id:
        # admin si nesmí smazat vlastní účet
        app.logger.warning(f"Admin se pokusil smazat sám sebe. user_id={user_id}")
        flash("Nemůžeš smazat sám sebe.", "error")
        return redirect(url_for("admin"))

    conn = get_db_connection()

    cur = conn.execute("DELETE FROM users WHERE id = ?;", (user_id,))
    # smažeme uživatele

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
    # smažeme auto podle id

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
    # tenhle blok se spustí jen při přímém spuštění app.py
    # ne při importu jako modulu

    ensure_last_command_file()
    # ještě jednou zkontrolujeme JSON soubor

    app.logger.info("Spouštím Flask server na 0.0.0.0:5000 v debug režimu.")
    app.run(debug=True, host="0.0.0.0", port=5000)
    # debug=True = automatický reload a detailnější chyby
    # host="0.0.0.0" = dostupné i z jiných zařízení v síti
    # port=5000 = standardní Flask port