-- Demo data for /recommendations/meeting-times
-- Safe to run multiple times; it resets only demo rows for these demo users.

BEGIN;

-- 1) Ensure demo users exist.
INSERT INTO users (first_name, last_name, email, is_active)
VALUES
  ('Alice', 'Demo', 'alice.demo@example.com', TRUE),
  ('Bob', 'Demo', 'bob.demo@example.com', TRUE),
  ('Carol', 'Demo', 'carol.demo@example.com', TRUE)
ON CONFLICT (email) DO NOTHING;

-- 2) Ensure each demo user has a personal calendar.
WITH demo_users AS (
  SELECT id, email
  FROM users
  WHERE email IN ('alice.demo@example.com', 'bob.demo@example.com', 'carol.demo@example.com')
)
INSERT INTO calendars (name, owner_type, owner_id)
SELECT du.email || ' calendar', 'user', du.id
FROM demo_users du
WHERE NOT EXISTS (
  SELECT 1
  FROM calendars c
  WHERE c.owner_type = 'user' AND c.owner_id = du.id
);

-- 3) Reset demo preferences for these users.
DELETE FROM time_slot_preferences
WHERE user_id IN (
  SELECT id FROM users WHERE email IN ('alice.demo@example.com', 'bob.demo@example.com', 'carol.demo@example.com')
);

-- Alice: Mon-Fri, 09:00-17:00
INSERT INTO time_slot_preferences (user_id, day_of_week, start_time, end_time)
SELECT u.id, d.day_of_week, TIME '09:00', TIME '17:00'
FROM users u
CROSS JOIN (VALUES (1), (2), (3), (4), (5)) AS d(day_of_week)
WHERE u.email = 'alice.demo@example.com';

-- Bob: Mon-Fri, 10:00-18:00
INSERT INTO time_slot_preferences (user_id, day_of_week, start_time, end_time)
SELECT u.id, d.day_of_week, TIME '10:00', TIME '18:00'
FROM users u
CROSS JOIN (VALUES (1), (2), (3), (4), (5)) AS d(day_of_week)
WHERE u.email = 'bob.demo@example.com';

-- Carol: Tue-Thu, 08:00-12:00 and 13:00-16:00
INSERT INTO time_slot_preferences (user_id, day_of_week, start_time, end_time)
SELECT u.id, d.day_of_week, TIME '08:00', TIME '12:00'
FROM users u
CROSS JOIN (VALUES (2), (3), (4)) AS d(day_of_week)
WHERE u.email = 'carol.demo@example.com';

INSERT INTO time_slot_preferences (user_id, day_of_week, start_time, end_time)
SELECT u.id, d.day_of_week, TIME '13:00', TIME '16:00'
FROM users u
CROSS JOIN (VALUES (2), (3), (4)) AS d(day_of_week)
WHERE u.email = 'carol.demo@example.com';

-- 4) Remove old demo meetings and attendees.
DELETE FROM meeting_attendees
WHERE meeting_id IN (
  SELECT m.id
  FROM meetings m
  WHERE m.title LIKE 'Demo Recommender:%'
);

DELETE FROM meetings
WHERE title LIKE 'Demo Recommender:%';

-- 5) Add demo conflicting meetings for tomorrow.
WITH tomorrow_anchor AS (
  SELECT date_trunc('day', now()) + interval '1 day' AS t0
),
alice_calendar AS (
  SELECT c.id AS calendar_id
  FROM calendars c
  JOIN users u ON u.id = c.owner_id
  WHERE c.owner_type = 'user' AND u.email = 'alice.demo@example.com'
  LIMIT 1
),
bob_calendar AS (
  SELECT c.id AS calendar_id
  FROM calendars c
  JOIN users u ON u.id = c.owner_id
  WHERE c.owner_type = 'user' AND u.email = 'bob.demo@example.com'
  LIMIT 1
),
carol_calendar AS (
  SELECT c.id AS calendar_id
  FROM calendars c
  JOIN users u ON u.id = c.owner_id
  WHERE c.owner_type = 'user' AND u.email = 'carol.demo@example.com'
  LIMIT 1
)
INSERT INTO meetings (calendar_id, title, location, start_time, end_time)
SELECT ac.calendar_id, 'Demo Recommender: Alice Busy', 'Zoom', t.t0 + interval '10 hours', t.t0 + interval '11 hours'
FROM alice_calendar ac CROSS JOIN tomorrow_anchor t
UNION ALL
SELECT bc.calendar_id, 'Demo Recommender: Bob Busy', 'Room 101', t.t0 + interval '14 hours', t.t0 + interval '15 hours'
FROM bob_calendar bc CROSS JOIN tomorrow_anchor t
UNION ALL
SELECT cc.calendar_id, 'Demo Recommender: Carol Busy', 'Teams', t.t0 + interval '9 hours', t.t0 + interval '10 hours'
FROM carol_calendar cc CROSS JOIN tomorrow_anchor t;

COMMIT;
