-- A booking starts a new block when it begins after every earlier booking of
-- the room has ended (running MAX, not just the previous row's end).
WITH ordered AS (
  SELECT room, start_min, end_min,
         MAX(end_min) OVER (PARTITION BY room ORDER BY start_min, end_min, id
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS reach,
         ROW_NUMBER() OVER (PARTITION BY room ORDER BY start_min, end_min, id) AS pos
  FROM bookings
),
flagged AS (
  SELECT room, start_min, end_min, pos,
         CASE WHEN reach IS NULL OR start_min > reach THEN 1 ELSE 0 END AS starts_block
  FROM ordered
),
blocks AS (
  SELECT room, start_min, end_min,
         SUM(starts_block) OVER (PARTITION BY room ORDER BY pos) AS block
  FROM flagged
)
SELECT room, MIN(start_min) AS block_start, MAX(end_min) AS block_end, COUNT(*) AS bookings
FROM blocks
GROUP BY room, block
ORDER BY room, block_start;
