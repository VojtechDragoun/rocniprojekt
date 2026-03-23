# RC Car Project

Popis projektu
Tento projekt umožňuje ovládání RC auta přes webovou aplikaci.

- Backend běží na Flasku (Python)
- Komunikace probíhá mezi webem a Arduinem přes USB (serial)
- Arduino ovládá:
  - motor (pohon)
  - servo (zatáčení)

Uživatel se přihlásí do aplikace a následně může auto ovládat přes dashboard pomocí klávesnice.

---

Instalace

Instalace Python knihoven

pip install flask
pip install pytest
pip install pyserial

Arduino část

Je potřeba:

Mít nainstalovaný program Arduino IDE
Také je potřeba mít stáhnutou knihovnu Servo pro Arduino

Nahrání kódu do Arduino desky

Postup:
1. Otevři soubor car.ino a zkopíruj kód do Arduino IDE
2. Připoj Arduino k PC přes USB
3. Vyber COM port, kam je Arduino připojené
4. Nahraj kód do Arduino

Důležité:
Arduino musí být připojené k PC ještě před spuštěním webu.

---

Zapojení

Arduino + motor a servo musí být zapojené podle schématu:
/docs/ (viz schéma zapojení)

---

Spuštění aplikace

Aplikace se spouští ze složky:
/web/app.py

Spuštění:
python app.py

Po spuštění se v konzoli zobrazí odkaz (např. http://127.0.0.1:5000)

---

Webové rozhraní

Navigace (navbar):
Domů – hlavní stránka
Dashboard – ovládání auta
Info – informace o projektu
Admin – správa (jen pro admina)

---

Přihlášení

Admin účet:
Uživatelské jméno: admin
Heslo: Admin123

---

Funkce aplikace

- registrace uživatele
- přihlášení / odhlášení
- role:
    user
    admin
- dashboard dostupný pouze po přihlášení
- admin má přístup k rozšířeným funkcím (mazání v databázi)

---

Ovládání auta

Na stránce dashboard:

W  pohyb dopředu
A  zatáčení doleva
D  zatáčení doprava

---

Databáze

Použitá databáze:
SQLite (rccar.db)

Umístění:
/database/rccar.db

Obsah:
- uživatelé (včetně hashovaných hesel)
- data aplikace

---

Inicializace databáze

Soubor:
/database/init_db.py

Spuštění:
python init_db.py

Tím se vytvoří nové tabulky (původní data budou smazána).

---

Použité technologie

Backend
- Python (Flask)
- SQLite

Frontend
- HTML (Jinja2 šablony)
- CSS

Hardware
- Arduino (C++)
- Servo + motor

---

Použité knihovny

Python
- flask – webový server
- pyserial – komunikace s Arduinem
- pytest – testování

Flask závislosti
- Werkzeug
- Jinja2
- ItsDangerous
- Click
- Blinker

Standardní knihovny
- sqlite3 – databáze
- pathlib – práce s cestami
- typing – typování

---

Struktura projektu

rccar/
│
├── arduino/
│   └── car/
│       └── car.ino
│
├── database/
│   ├── init_db.py
│   ├── rccar.db
│   └── schema.sql
│
├── docs/
│   ├── ER_diagram.drawio
│   ├── ER_diagram.drawio.bkp
│   └── Schéma k zapojení servo motoru a arduino.png
│
├── web/
│   ├── __pycache__/
│   │   └── arduino_comm.cpython-313.pyc
│   │
│   ├── static/
│   │   ├── style.css
│   │   └── images/
│   │       └── er_diagram.png
│   │
│   ├── templates/
│   │   ├── base.html
│   │   ├── index.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── admin.html
│   │   └── info.html
│   │
│   ├── app.py
│   └── arduino_comm.py
│
└── README.md

---

Autor
Vojtěch Dragoun

---

Poznámky

Projekt vyžaduje připojené Arduino během běhu.
Bez Arduino nebude ovládání funkční.