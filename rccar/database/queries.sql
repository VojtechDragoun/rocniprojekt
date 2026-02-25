PRAGMA foreign_keys = ON;

-- A) Všechny jízdy s uživatelem a autem (JOIN)
SELECT
  rides.id,
  users.username,
  cars.name AS car_name,
  rides.duration_sec,
  rides.created_at
FROM rides
JOIN users ON users.id = rides.user_id
JOIN cars  ON cars.id  = rides.car_id
ORDER BY rides.created_at DESC;

-- B) Jízdy jen pro konkrétní auto (WHERE + ORDER)
SELECT
  users.username,
  rides.duration_sec,
  rides.created_at
FROM rides
JOIN users ON users.id = rides.user_id
WHERE rides.car_id = 1
ORDER BY rides.duration_sec DESC;

-- C) Kdo má přístup k autu (M:N JOIN)
SELECT
  cars.name AS car_name,
  users.username,
  user_cars.access_role
FROM user_cars
JOIN users ON users.id = user_cars.user_id
JOIN cars  ON cars.id  = user_cars.car_id
WHERE cars.name = 'Car_A'
ORDER BY users.username;

-- D) “Žebříček” – součet času jízd na uživatele (GROUP BY)
SELECT
  users.username,
  SUM(rides.duration_sec) AS total_time,
  COUNT(*) AS ride_count
FROM rides
JOIN users ON users.id = rides.user_id
GROUP BY users.id
ORDER BY total_time DESC;

-- E) Vyhledávání uživatelů (LIKE)
SELECT id, username, role
FROM users
WHERE username LIKE '%vo%'
ORDER BY username;