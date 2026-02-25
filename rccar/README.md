pip instal ....
2popsat jak stáhnout knihovny + ctrl +c +ctrlv

py -m pip install pyserial     | Instalace knihovny

Stránka se spoští přes soubor app.py, který je ve složce web, která je ve složce projektu rccar.
Po spuštění app.py se vygeneruje odkaz na stránku.
V navbaru je jsou odkazy na další stránky, domů - domovská stránka; dashboard - ovládání auta (motorů) ; info - informace o projektu, admin pro admina.
V navbaru je také dropdown menu, kde je přihlášení a registrace. (admin login ) Uživatelské jméno: vd ; heslo:12345
Úspěšná registrace se zapíše i s zahashovaným heslem do databáze rccar.db, která je ve složce database, která je ve složce projektu.
Složka database také obsahuje init_db.py, který je pro znovuvytvoření tabulek, ale tabulky budou prázdné.
po přihlášení, jako uživatel nebo admin se zpřístupní stránka dash board, kde se pomocí kláves/ stisknutí talčítka ovládá auto(motory od auta - pohon "W" a zatáčení pomocí serva "A" nebo "D")

Jazyky
- Python – backend (Flask server + práce s databází)
- HTML – frontend šablony 
- CSS – stylování společné pro všechny stránky 
- SQL – databázové schéma 
- c++ - ovládání esp32

Databáze
- SQLite – lokální souborová databáze Uživatelské jméno

Standardní knihovny Pythonu 
- sqlite3 – práce se SQLite databází
- pathlib – cesty k souborům
- typing – xxxx

Flask - je potřeba stáhnout
- Werkzeug 
- Jinja2 
- ItsDangerous
- Click 
- Blinker
