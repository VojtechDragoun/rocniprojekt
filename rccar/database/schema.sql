PRAGMA foreign_keys = ON;

-- =====================================================
-- USERS (login/registrace)
-- =====================================================
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  role          TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('user','admin')),
  created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- =====================================================
-- RIDES (jízdy)
-- 1 uživatel -> N jízd
-- 1 jízda -> 1 uživatel
-- =====================================================
CREATE TABLE IF NOT EXISTS rides (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL,
  duration_sec INTEGER NOT NULL CHECK(duration_sec >= 0),
  created_at   TEXT NOT NULL DEFAULT (datetime('now')),
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Zrychlí dotazování pro dashboard
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);
