-- schema.sql
-- =========
--
-- Tenhle soubor obsahuje strukturu databáze pro projekt RCcar.
--
-- Jsou tu 3 hlavní tabulky:
-- 1) users  = uživatelé aplikace
-- 2) cars   = auta a jejich nastavení
-- 3) rides  = jednotlivé jízdy
--
-- rides je vlastně spojení mezi users a cars,
-- protože říká který uživatel jel s jakým autem.
--
-- Důležité:
-- - hesla se sem přímo nepíšou ručně
-- - do users se ukládá password_hash, ne normální heslo
-- - demo data vkládá až init_db.py

-- zapnutí cizích klíčů
-- to je důležité hlavně pro vztahy mezi tabulkami
PRAGMA foreign_keys = ON;


-- ------------------------------------------------------------
-- USERS
-- ------------------------------------------------------------
-- tabulka uživatelů
-- používá se hlavně pro login / registraci / role

CREATE TABLE IF NOT EXISTS users (

  -- primární klíč uživatele
  -- AUTOINCREMENT = každému novému uživateli se přidělí nové id
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- uživatelské jméno
  -- musí být vyplněné a zároveň jedinečné
  username TEXT NOT NULL UNIQUE,

  -- hash hesla
  -- neukládá se sem normální heslo, ale jen jeho hash
  password_hash TEXT NOT NULL,

  -- role uživatele
  -- typicky user nebo admin
  -- když se nic neuvede, nastaví se automaticky user
  role TEXT NOT NULL DEFAULT 'user',

  -- datum a čas vytvoření uživatele
  -- datetime('now') vezme aktuální čas při vložení záznamu
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ------------------------------------------------------------
-- CARS
-- ------------------------------------------------------------
-- tabulka aut
-- ukládají se sem základní parametry auta,
-- které se pak mohou zobrazovat v aplikaci nebo používat při jízdě

CREATE TABLE IF NOT EXISTS cars (

  -- primární klíč auta
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- název auta
  -- musí být jedinečný, aby se dvě auta nejmenovala stejně
  name TEXT NOT NULL UNIQUE,

  -- omezení výkonu v procentech
  -- třeba 10 znamená nízký výkon
  -- 100 by byl maximální výkon
  power_limit_percent INTEGER NOT NULL DEFAULT 10,

  -- maximální úhel zatáčení
  -- např. 45 znamená, že servo může jít o 45° od středu
  steer_angle_deg INTEGER NOT NULL DEFAULT 45,

  -- čas vytvoření záznamu auta
  created_at TEXT NOT NULL DEFAULT (datetime('now')),

  -- kontrola, aby výkon nebyl mimo rozumný rozsah
  CHECK (power_limit_percent >= 0 AND power_limit_percent <= 100),

  -- kontrola, aby úhel zatáčení nebyl mimo rozumný rozsah
  CHECK (steer_angle_deg >= 0 AND steer_angle_deg <= 90)
);


-- ------------------------------------------------------------
-- RIDES
-- ------------------------------------------------------------
-- tabulka jízd
--
-- tahle tabulka spojuje users a cars
-- každý záznam znamená jednu jízdu:
-- kdo jel, s jakým autem, kdy začal a jak dlouho jel

CREATE TABLE IF NOT EXISTS rides (

  -- primární klíč jízdy
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- id uživatele, který jel
  user_id INTEGER NOT NULL,

  -- id auta, se kterým jel
  car_id INTEGER NOT NULL,

  -- čas začátku jízdy
  -- když se nic neuvede, uloží se aktuální čas
  started_at TEXT NOT NULL DEFAULT (datetime('now')),

  -- délka jízdy v sekundách
  -- může být NULL
  -- to se hodí třeba když jízda ještě neskončila
  -- nebo uživatel zavřel stránku bez korektního ukončení
  duration_sec INTEGER NULL,

  -- cizí klíč na users(id)
  -- ON DELETE CASCADE znamená:
  -- když smažu uživatele, smažou se i jeho jízdy
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

  -- cizí klíč na cars(id)
  -- když smažu auto, smažou se i jízdy navázané na to auto
  FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
);


-- ------------------------------------------------------------
-- INDEXY
-- ------------------------------------------------------------
-- indexy zrychlují vyhledávání
-- hodí se hlavně když bude v databázi víc dat
-- např. pro dashboard, historii jízd nebo filtrování

-- rychlejší hledání jízd podle uživatele
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);

-- rychlejší hledání jízd podle auta
CREATE INDEX IF NOT EXISTS idx_rides_car_id ON rides(car_id);

-- rychlejší řazení / hledání jízd podle času začátku
CREATE INDEX IF NOT EXISTS idx_rides_started_at ON rides(started_at);