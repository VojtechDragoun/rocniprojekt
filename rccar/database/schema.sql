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
-- rides propojuje uživatele a auta,
-- protože říká, který uživatel jel s jakým autem.
--
-- Důležité:
-- - hesla se sem přímo nepíšou ručně
-- - do users se ukládá password_hash, ne normální heslo
-- - ukázková data vkládá init_db.py

-- zapnutí podpory cizích klíčů
PRAGMA foreign_keys = ON;


-- ------------------------------------------------------------
-- USERS
-- ------------------------------------------------------------
-- tabulka uživatelů aplikace

CREATE TABLE IF NOT EXISTS users (
  -- primární klíč uživatele
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- uživatelské jméno
  -- musí být jedinečné
  username TEXT NOT NULL UNIQUE,

  -- hash hesla
  -- neukládá se normální heslo, ale jen jeho hash
  password_hash TEXT NOT NULL,

  -- role uživatele
  -- typicky user nebo admin
  role TEXT NOT NULL DEFAULT 'user',

  -- čas vytvoření účtu
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);


-- ------------------------------------------------------------
-- CARS
-- ------------------------------------------------------------
-- tabulka aut
-- ukládá základní vlastnosti auta,
-- které jsou důležité pro dashboard a Arduino

CREATE TABLE IF NOT EXISTS cars (
  -- primární klíč auta
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- název auta
  name TEXT NOT NULL UNIQUE,

  -- barva auta
  color TEXT NOT NULL DEFAULT 'nezadano',

  -- úhel zatáčení pro servo
  -- podle této hodnoty se řídí zatáčení konkrétního auta
  steer_angle_deg INTEGER NOT NULL DEFAULT 45,

  -- čas vytvoření záznamu
  created_at TEXT NOT NULL DEFAULT (datetime('now')),

  -- kontrola rozsahu úhlu
  CHECK (steer_angle_deg >= 0 AND steer_angle_deg <= 90)
);


-- ------------------------------------------------------------
-- RIDES
-- ------------------------------------------------------------
-- tabulka jízd
-- každý záznam znamená jednu jízdu určitého uživatele s určitým autem

CREATE TABLE IF NOT EXISTS rides (
  -- primární klíč jízdy
  id INTEGER PRIMARY KEY AUTOINCREMENT,

  -- uživatel, který jel
  user_id INTEGER NOT NULL,

  -- auto, se kterým jel
  car_id INTEGER NOT NULL,

  -- čas začátku jízdy
  started_at TEXT NOT NULL DEFAULT (datetime('now')),

  -- délka jízdy v sekundách
  -- NULL znamená, že jízda ještě neskončila nebo nebyla správně ukončena
  duration_sec INTEGER NULL,

  -- cizí klíč na tabulku users
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

  -- cizí klíč na tabulku cars
  FOREIGN KEY (car_id) REFERENCES cars(id) ON DELETE CASCADE
);


-- ------------------------------------------------------------
-- INDEXY
-- ------------------------------------------------------------
-- indexy zrychlují hledání a filtrování v tabulce rides

-- hledání jízd podle uživatele
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);

-- hledání jízd podle auta
CREATE INDEX IF NOT EXISTS idx_rides_car_id ON rides(car_id);

-- hledání a řazení jízd podle času
CREATE INDEX IF NOT EXISTS idx_rides_started_at ON rides(started_at);