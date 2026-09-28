// ─── 예제 쿼리 ────────────────────────────────────────────────
const EXAMPLE_QUERIES = [
  { label: 'ROWNUM 페이징',  sql: 'SELECT * FROM orders WHERE ROWNUM <= 10' },
  { label: 'NVL 널 처리',    sql: "SELECT NVL(username, '익명') FROM users" },
  { label: 'SYSDATE 날짜',   sql: 'SELECT SYSDATE FROM DUAL' },
  { label: 'SEQUENCE 채번',  sql: 'SELECT seq_order.NEXTVAL FROM DUAL' },
  { label: 'DECODE 분기',    sql: "SELECT DECODE(status, 'Y', '활성', '비활성') FROM members" },
  { label: '묵시적 형변환',  sql: "SELECT * FROM products WHERE product_id = '100'" },
];

export { EXAMPLE_QUERIES };
