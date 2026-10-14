-- Every (manager, report) pair at any distance, built top down from each employee.
WITH RECURSIVE chain(boss, member) AS (
  SELECT manager_id, id FROM employees WHERE manager_id IS NOT NULL
  UNION ALL
  SELECT c.boss, e.id
  FROM chain c
  JOIN employees e ON e.manager_id = c.member
),
depth(id, level) AS (
  SELECT id, 0 FROM employees WHERE manager_id IS NULL
  UNION ALL
  SELECT e.id, d.level + 1
  FROM depth d
  JOIN employees e ON e.manager_id = d.id
)
SELECT e.name, d.level, COUNT(c.member) AS team
FROM employees e
JOIN depth d ON d.id = e.id
LEFT JOIN chain c ON c.boss = e.id
GROUP BY e.id
ORDER BY team DESC, e.name;
