-- Gaps and islands: consecutive days share the same (day - row number).
WITH days AS (
  SELECT DISTINCT user, day FROM logins
),
islands AS (
  SELECT user,
         julianday(day) - ROW_NUMBER() OVER (PARTITION BY user ORDER BY day) AS island
  FROM days
),
streaks AS (
  SELECT user, COUNT(*) AS length
  FROM islands
  GROUP BY user, island
)
SELECT user, MAX(length) AS longest
FROM streaks
GROUP BY user
ORDER BY longest DESC, user;
