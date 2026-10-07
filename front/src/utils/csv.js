// ─── CSV에서 SQL 쿼리 추출 ──────────────────────────────────────
function parseCSV(text) {
  const rows = [];
  let row = [], field = '', inQuotes = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (inQuotes) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; }
        else inQuotes = false;
      } else {
        field += c;
      }
    } else {
      if (c === '"') inQuotes = true;
      else if (c === ',') { row.push(field); field = ''; }
      else if (c === '\n' || c === '\r') {
        if (c === '\r' && text[i + 1] === '\n') i++;
        row.push(field); field = '';
        rows.push(row);
        row = [];
      } else field += c;
    }
  }
  if (field !== '' || row.length) { row.push(field); rows.push(row); }
  return rows.filter(r => r.some(c => c.trim() !== ''));
}

// 헤더에 sql / query_sql / query 컬럼이 있으면 그 컬럼만 사용.
// 없으면 각 행의 첫 번째 칸을 쿼리로 취급 (헤더 없는 CSV 대응).
function extractSQLFromCSV(text) {
  const rows = parseCSV(text);
  if (rows.length === 0) return '';

  const header = rows[0].map(h => h.trim().toLowerCase());
  const sqlColIdx = header.findIndex(h => ['sql', 'query_sql', 'query'].includes(h));

  const dataRows = sqlColIdx !== -1 ? rows.slice(1) : rows;
  const colIdx = sqlColIdx !== -1 ? sqlColIdx : 0;

  return dataRows
    .map(r => (r[colIdx] || '').trim())
    .filter(Boolean)
    .map(s => (s.endsWith(';') ? s : s + ';'))
    .join('\n');
}

export { parseCSV, extractSQLFromCSV };
