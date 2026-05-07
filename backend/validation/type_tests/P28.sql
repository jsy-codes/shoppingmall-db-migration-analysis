DROP TABLE IF EXISTS sales;

CREATE TABLE sales (
    product VARCHAR(50),
    year INT,
    amount INT
);

INSERT INTO sales VALUES
('A', 2023, 100),
('A', 2024, 200);

-- ❌ Oracle PIVOT
SELECT * FROM sales
PIVOT (
    SUM(amount)
    FOR year IN (2023, 2024)
);

-- ✅ MySQL (CASE)
SELECT
    product,
    SUM(CASE WHEN year = 2023 THEN amount END) AS y2023,
    SUM(CASE WHEN year = 2024 THEN amount END) AS y2024
FROM sales
GROUP BY product;