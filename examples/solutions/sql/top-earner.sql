SELECT department, name, salary
FROM (
  SELECT department, name, salary,
         RANK() OVER (PARTITION BY department ORDER BY salary DESC) AS pos
  FROM employees
)
WHERE pos = 1
ORDER BY department, name;
