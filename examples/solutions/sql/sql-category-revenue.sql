SELECT category,
       COUNT(DISTINCT order_id) AS orders,
       SUM(quantity * unit_price) AS revenue
FROM order_items
GROUP BY category
HAVING SUM(quantity * unit_price) >= 100
ORDER BY revenue DESC, category;
