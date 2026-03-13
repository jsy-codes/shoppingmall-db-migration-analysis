## P01 Implicit Type Cast

Oracle Pattern:

```
WHERE member_id = '123'
```

MySQL Result:
Implicit type conversion may occur, causing index not to be used.

Risk:
MEDIUM

Reason:
String to numeric casting can disable index usage.

Fix:

```
WHERE member_id = 123
```

---

## P02 Function on Indexed Column

Oracle Pattern:

```
WHERE UPPER(name) = 'KIM'
```

MySQL Result:
Index not used, full table scan occurs.

Risk:
HIGH

Reason:
Applying a function on indexed column prevents index usage.

Fix:

```
WHERE name = 'KIM'
```

or create proper index / generated column

---

## P03 ROWNUM Pagination

Oracle Pattern:

```
WHERE ROWNUM <= 10
```

MySQL Result:
Query returns all rows if LIMIT not applied.

Risk:
HIGH

Reason:
Oracle ROWNUM is not compatible with MySQL LIMIT.

Fix:

```
LIMIT 10
```

---

## P04 NVL vs IFNULL

Oracle Pattern:

```
NVL(col, 0)
```

MySQL Result:
Function not supported.

Risk:
LOW

Reason:
MySQL uses IFNULL instead of NVL.

Fix:

```
IFNULL(col, 0)
```

---

## P05 DATE vs DATETIME Difference

Oracle Pattern:
DATE

MySQL Result:
DATETIME or TIMESTAMP required.

Risk:
MEDIUM

Reason:
Oracle DATE includes time, MySQL DATE does not.

Fix:
Use DATETIME or TIMESTAMP in MySQL.

---

## P06 VARCHAR2 vs VARCHAR Difference

Oracle Pattern:
VARCHAR2

MySQL Result:
VARCHAR

Risk:
LOW

Reason:
Different length / padding / comparison behavior.

Fix:
Check column length and charset explicitly.

---

## P07 CHAR Padding Issue

Oracle Pattern:
CHAR(10)

MySQL Result:
Trailing spaces may affect comparison.

Risk:
LOW

Reason:
CHAR type pads with spaces.

Fix:
Use VARCHAR or TRIM()

---

## P08 Function-Based Index Loss

Oracle Pattern:

```
CREATE INDEX idx ON t(UPPER(name))
```

MySQL Result:
Function-based index not supported directly.

Risk:
HIGH

Reason:
MySQL requires generated column for function index.

Fix:
Use generated column + index.

---

## P09 JOIN Without Index

Oracle Pattern:
JOIN without index

MySQL Result:
Full scan / slow join

Risk:
HIGH

Reason:
MySQL optimizer depends heavily on index.

Fix:
Add index on join column.

---

## P10 Nested Subquery Performance Issue

Oracle Pattern:
Nested subquery

MySQL Result:
Slow execution

Risk:
MEDIUM

Reason:
Optimizer behavior differs between Oracle and MySQL.

Fix:
Rewrite using JOIN.

```
```
