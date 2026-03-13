DROP TABLE IF EXISTS type_test;

CREATE TABLE type_test (
    id INT,

    int_col INT,
    decimal_col DECIMAL(10,4),

    varchar_col VARCHAR(10),
    varchar_short VARCHAR(3),

    char_col CHAR(5),

    date_col DATE,
    datetime_col DATETIME,

    null_col INT
);