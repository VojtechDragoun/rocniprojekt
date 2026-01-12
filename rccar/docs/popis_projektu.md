# RemoteCarControl – popis projektu

## 1. Základní informace
- Název projektu: RCcar
- Programovací jazyk: Python
- Webová část: Flask, HTML, CSS
- Databáze: SQLite
- Hardware: ESP32 + motory 

---

## 2. Cíl projektu
- Vytvořit systém pro dálkové ovládání autíčka(motorů) z počítače
- Zajistit komunikaci mezi PC aplikací a ESP32 přes Wi-Fi
- Ukládat a zobrazovat data o jízdách v databázi (kdo řídí(uživatel), délka jízdy)
- Webové rozhraní pro uživatele / administrátora
- Propojit Python aplikaci, databázi, web a hardware

---

## 3. Architektura projektu
- Projekt je rozdělen na tři hlavní části:
  - Python desktopová aplikace
  - Webová aplikace
  - Hardware (ESP32)

- Průběh Komunikace:
  - Python aplikace odesílá příkazy na ESP32 přes Wi-Fi (HTTP, JSON)
  - Python aplikace zapisuje data do SQLite databáze
  - Webová aplikace čte data ze stejné databáze

---

## 4. Python aplikace (PC)
- Aplikace je napsaná v jazyce Python + knihovy 
- Obsahuje grafické uživatelské rozhraní (PyQt)
- Umožňuje:
  - ovládání směru jízdy (dopředu, dozadu, vlevo, vpravo)
  - (nastavení rychlosti pomocí posuvníku)
  - spuštění a ukončení jízdy
  - zobrazení stavu připojení k ESP32


---

## 5. Komunikace s ESP32
- ESP32 funguje jako klient připojený k PC
- Komunikace probíhá pomocí HTTP požadavků
- Přenášená data jsou ve formátu JSON
- ESP32:
  - přijímá příkazy z PC aplikace
  - ovládá motory pomocí PWM signálu
  - odesílá zpět stavové informace

---

## 6. Ukládání dat
### 6.1 Databáze (SQLite)
- Projekt využívá databázi SQLite
- Do databáze se ukládají:
  - uživatelé systému
  - jednotlivé jízdy
  - (odeslané příkazy)

### 6.2 Ukládání do souboru
- Uživatelská nastavení jsou ukládána do souboru `config.json`
- Soubor obsahuje například:
  - IP adresu ESP32
  - poslední použité nastavení rychlosti

---

## 7. Webová aplikace
- Webová aplikace je vytvořena pomocí Flask
- Web využíváHTML a CSS
- Stránky webu:
  - `index.html` – úvodní stránka s popisem projektu
  - `login.html` – přihlášení uživatele
  - `register.html` – registrace nového uživatele
  - `dashboard.html` – přehled dat pro přihlášeného uživatele
  - `admin.html` – administrační rozhraní

---

## 8. Přihlášení a role uživatelů
- Webová aplikace podporuje:
  - registraci uživatelů
  - přihlášení a odhlášení
- Uživatelé mají role:
  - USER – běžný uživatel
  - (ADMIN – administrátor systému)
- Obsah webu se liší podle nepřihlášeného/přihlášeného uživatele

---

## 9. Práce s databází přes web
- Přihlášený uživatel může:
  - zobrazit seznam svých jízd
  - zobrazit statistiky a historii příkazů
- (Administrátor může:
  - mazat jízdy
  - mazat uživatele
  - mazat příkazy z databáze)

---

## 10. Databázový návrh
- K databázi je vytvořen ER diagram
- Databáze obsahuje vztahy:
  - 1 : N (uživatel – jízdy)
  - 1 : N (jízda – příkazy)

---

## 12. Dokumentace a algoritmy
- Zdrojový kód je dokumentován pomocí komentářů
- Součástí dokumentace jsou:
  - popisy použitých algoritmů
  - vývojové diagramy
  - ER diagram databáze

---

## 14. Shrnutí
- Projekt propojuje:
  - Python desktopovou aplikaci
  - webové rozhraní
  - databázi
  - fyzické zařízení (ESP32)
- Výsledkem je komplexní systém splňující všechny požadavky zadání
- Projekt je navržen tak, aby byl dále rozšiřitelný 