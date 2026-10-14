SELECT name, price
FROM products
WHERE in_stock = 1 AND price < 20
ORDER BY price, name;
