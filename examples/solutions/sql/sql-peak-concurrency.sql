-- Sweep line: +1 at each start, -1 at each end, net per instant, running total.
WITH events(server, t, delta) AS (
  SELECT server, start_sec, 1 FROM calls
  UNION ALL
  SELECT server, end_sec, -1 FROM calls
),
net AS (
  SELECT server, t, SUM(delta) AS delta
  FROM events
  GROUP BY server, t
),
running AS (
  SELECT server, t,
         SUM(delta) OVER (PARTITION BY server ORDER BY t) AS active
  FROM net
),
peaks AS (
  SELECT server, MAX(active) AS peak FROM running GROUP BY server
)
SELECT p.server, p.peak, MIN(r.t) AS first_at
FROM peaks p
JOIN running r ON r.server = p.server AND r.active = p.peak
GROUP BY p.server, p.peak
ORDER BY p.peak DESC, p.server;
