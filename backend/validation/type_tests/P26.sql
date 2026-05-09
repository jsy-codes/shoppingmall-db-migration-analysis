-- ❌ Oracle 계층 쿼리
SELECT id, parent_id
FROM tree
CONNECT BY NOCYCLE PRIOR id = parent_id;

-- ✅ MySQL WITH RECURSIVE
WITH RECURSIVE tree_cte AS (
    SELECT id, parent_id FROM tree WHERE parent_id IS NULL
    UNION ALL
    SELECT t.id, t.parent_id
    FROM tree t
    JOIN tree_cte c ON t.parent_id = c.id
)
SELECT * FROM tree_cte;