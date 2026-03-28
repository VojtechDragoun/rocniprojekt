# RC Car Project

Popis projektu

Tento projekt umožňuje ovládání RC auta přes webovou aplikaci.

Projekt propojuje:
- Flask backend v Pythonu
- SQLite databázi
- Arduino připojené přes USB serial komunikaci

Arduino ovládá:
- motor (pohon)
- servo (zatáčení)

Uživatel se přihlásí do aplikace a následně může auto ovládat přes dashboard pomocí klávesnice nebo tlačítek na stránce.

Aplikace ukládá data o uživatelích a jízdách do SQLite databáze.
Zároveň ukládá čas poslední akce do souboru last_command.json a při otevření dashboardu ho znovu načítá.

---

Instalace

Instalace Python knihoven

pip install flask
pip install pyserial

Arduino část

Je potřeba:
- mít nainstalovaný program Arduino IDE
- mít dostupnou knihovnu Servo pro Arduino

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

Arduino, motor a servo musí být zapojené podle schématu ve složce:
/docs/

---

Spuštění aplikace

Aplikace se spouští ze složky:
/web/app.py

Spuštění:
python app.py

Po spuštění se v konzoli zobrazí odkaz, například:
http://127.0.0.1:5000

---

Webové rozhraní

Navigace:
- Domů – hlavní stránka
- Dashboard – ovládání auta
- Info – informace o projektu
- Admin – správa databáze, pouze pro admina

---

Přihlášení

Ukázkový admin účet:
- uživatelské jméno: admin
- heslo: Admin123

---

Funkce aplikace

- registrace uživatele
- přihlášení / odhlášení
- role:
  - user
  - admin
- dashboard dostupný pouze po přihlášení
- admin má přístup k rozšířeným funkcím
- ukládání jízd do databáze
- výběr auta v dashboardu
- nastavení úhlu zatáčení podle vybraného auta
- nastavení hodnoty motoru v rozsahu 1200 až 1300
- ukládání času poslední akce do souboru JSON
- načítání času poslední akce ze souboru na dashboardu

---

Ovládání auta

Na stránce dashboard:

- W = pohyb dopředu
- A = zatáčení doleva
- D = zatáčení doprava

Po odeslání akce se do souboru last_command.json uloží čas poslední akce.
Po znovunačtení dashboardu se tento uložený čas zobrazí uživateli.

V dashboardu je také možné:
- vybrat aktivní auto
- změnit hodnotu motoru v rozsahu 1200 až 1300

---

Databáze

Použitá databáze:
SQLite (rccar.db)

Umístění:
/database/rccar.db

Databáze ukládá:
- uživatele
- auta
- jízdy

Do databáze se ukládají hlavně uživatelé a záznamy jízd.

Tabulka cars obsahuje například:
- název auta
- barvu auta
- úhel zatáčení

Tabulka rides propojuje uživatele a auta.

---

Ukládání a načítání dat ze souboru

Použitý soubor:
web/last_command.json

Soubor obsahuje:
- čas poslední akce

Při odeslání akce z dashboardu se tento soubor aktualizuje.
Při otevření dashboardu se data ze souboru načtou a zobrazí na stránce.

Tím je splněno ukládání a načítání dat z/do souboru.

---

Inicializace databáze

Strukturu tabulek vytváří soubor:
/database/schema.sql

Ukázková data doplňuje soubor:
/database/init_db.py

Ten do databáze vloží:
- 3 uživatele
- 3 auta
- 3 jízdy

Spuštění:
python init_db.py

Poznámka:
Pokud chceš vytvořit databázi úplně znovu od nuly,
je nejlepší nejdřív smazat starý soubor rccar.db
a potom spustit init_db.py.

---

Použité technologie

Backend
- Python
- Flask
- SQLite

Frontend
- HTML (Jinja2 šablony)
- CSS
- JavaScript

Hardware
- Arduino
- Servo
- Motor / ESC

---

Použité knihovny

Python
- flask – webový server
- pyserial – komunikace s Arduinem

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
- json – ukládání a načítání dat ze souboru
- datetime – uložení času poslední akce

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
│   ├── arduino_comm.py
│   └── last_command.json
│
└── README.md

---

Autor

Vojtěch Dragoun

---

Poznámky

Projekt vyžaduje připojené Arduino během běhu.
Bez Arduina nebude ovládání hardwaru funkční.

Soubor last_command.json nesmí být prázdný,
protože slouží pro ukládání a načítání času poslední akce.