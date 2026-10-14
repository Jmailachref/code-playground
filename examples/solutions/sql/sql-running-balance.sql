-- Running sum per account. Order the window by (day, id): ordering by day alone
-- would give every same-day transaction the day's total (the default frame
-- includes peer rows).
SELECT account, id,
       SUM(amount) OVER (PARTITION BY account ORDER BY day, id) AS balance
FROM transactions
ORDER BY account, day, id;
