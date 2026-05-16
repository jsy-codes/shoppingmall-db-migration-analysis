DROP TABLE IF EXISTS tree;

CREATE TABLE tree (
    id        INT PRIMARY KEY,
    name      VARCHAR(100),
    parent_id INT
);

INSERT INTO tree VALUES
(1, '본사',   NULL),
(2, '영업팀', 1),
(3, '개발팀', 1),
(4, '프론트', 3),
(5, '백엔드', 3);

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