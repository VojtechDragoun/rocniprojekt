PRAGMA foreign_keys = ON;

-- USERS (3 kusy)
INSERT INTO users (username, password_hash, role) VALUES
('vojtech', 'HASH_SEM_DOPLN', 'admin'),
('pepa',    'HASH_SEM_DOPLN', 'user'),
('jana',    'HASH_SEM_DOPLN', 'user');

-- CARS (2 kusy – různé servo/motor nastavení)
INSERT INTO cars (name, servo_pin, servo_center_deg, servo_offset_deg, motor_max_pwm) VALUES
('Car_A', 3, 90, 45, 255),
('Car_B', 3, 95, 35, 180);

-- USER_CARS (M:N – kdo smí řídit které auto)
INSERT INTO user_cars (user_id, car_id, access_role) VALUES
(1, 1, 'driver'), -- vojtech -> Car_A
(1, 2, 'driver'), -- vojtech -> Car_B
(2, 1, 'driver'), -- pepa   -> Car_A
(3, 2, 'driver'); -- jana   -> Car_B

-- RIDES (aspoň 3 kusy)
INSERT INTO rides (user_id, car_id, duration_sec) VALUES
(1, 1, 120),
(2, 1, 95),
(1, 2, 150);