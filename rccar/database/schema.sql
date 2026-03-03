-- schema.sql
-- =========
-- Schéma DB pro RCcar (3 tabulky):
--   users  (login/registrace)
--   cars   (parametry aut)
--   rides  (jízdy = asociativní entita users<->cars + čas)
--
-- Poznámka:
-- - Hesla do users nevkládáme tady, protože musí být hash.
-- - Seed data (3 záznamy do každé tabulky) udělá Python skript init_db.py.

PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- USERS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'user',
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ------------------------------------------------------------
-- CARS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS cars (
  id                  INTEGER PRIMARY KEY AUTOINCREMENT,
  name                TEXT NOT NULL UNIQUE,
  power_limit_percent INTEGER NOT NULL DEFAULT 10,   -- 0..100 (omezení výkonu)
  steer_angle_deg     INTEGER NOT NULL DEFAULT 45,   -- např. 45° doleva/doprava
  created_at          TEXT NOT NULL DEFAULT (datetime('now')),

  -- jednoduchá kontrola rozsahu
  CHECK (power_limit_percent >= 0 AND power_limit_percent <= 100),
  CHECK (steer_angle_deg >= 0 AND steer_angle_deg <= 90)
);

-- ------------------------------------------------------------
-- RIDES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS rides (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL,
  car_id       INTEGER NOT NULL,
  started_at   TEXT NOT NULL DEFAULT (datetime('now')),
  duration_sec INTEGER NULL, -- NULL = nedokončeno (uživatel zavřel stránku / nedal stop)

  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (car_id)  REFERENCES cars(id)  ON DELETE CASCADE
);

-- Indexy (rychlejší SELECTy pro dashboard)
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);
CREATE INDEX IF NOT EXISTS idx_rides_car_id  ON rides(car_id);
CREATE INDEX IF NOT EXISTS idx_rides_started_at ON rides(started_at);