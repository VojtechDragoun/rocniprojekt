PRAGMA foreign_keys = ON;

-- USERS
CREATE TABLE IF NOT EXISTS users (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  username      TEXT    NOT NULL UNIQUE,
  password_hash TEXT    NOT NULL,
  role          TEXT    NOT NULL DEFAULT 'user',
  created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- CARS (nastavení konkrétního auta)
CREATE TABLE IF NOT EXISTS cars (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  name             TEXT    NOT NULL UNIQUE,

  servo_pin        INTEGER NOT NULL DEFAULT 3,
  servo_center_deg INTEGER NOT NULL DEFAULT 90,
  servo_offset_deg INTEGER NOT NULL DEFAULT 45,

  motor_max_pwm    INTEGER NOT NULL DEFAULT 255,

  created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- USER_CARS (M:N: kdo smí řídit které auto)
CREATE TABLE IF NOT EXISTS user_cars (
  user_id     INTEGER NOT NULL,
  car_id      INTEGER NOT NULL,
  access_role TEXT    NOT NULL DEFAULT 'driver',
  created_at  TEXT    NOT NULL DEFAULT (datetime('now')),

  PRIMARY KEY (user_id, car_id),

  FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,

  FOREIGN KEY (car_id) REFERENCES cars(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
);

-- RIDES (jízdy patří userovi + autu)
CREATE TABLE IF NOT EXISTS rides (
  id           INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id      INTEGER NOT NULL,
  car_id       INTEGER NOT NULL,
  duration_sec INTEGER NOT NULL CHECK(duration_sec >= 0),
  created_at   TEXT    NOT NULL DEFAULT (datetime('now')),

  FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE,

  FOREIGN KEY (car_id) REFERENCES cars(id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
);

-- INDEXY
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON rides(user_id);
CREATE INDEX IF NOT EXISTS idx_rides_car_id  ON rides(car_id);
CREATE INDEX IF NOT EXISTS idx_rides_created ON rides(created_at);