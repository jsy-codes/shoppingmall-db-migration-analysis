// ─── API 호출 함수 모음 ──────────────────────────────────────────
// 백엔드 /diagnose 엔드포인트 호출
// 요청 형식: { "sql": "입력한 SQL 문자열" }
// 응답 형식: { rule_id, risk_level, reason, recommended_ddl,
//              estimated_improvement, risk_score, matched_pattern_ids }

const API_URL = import.meta.env.VITE_API_URL || 'https://shoppingmall-db-migration-analysis.onrender.com';

export async function fetchDiagnose(sql) {
  const res = await fetch(`${API_URL}/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql }),
    credentials: 'include',
    signal: AbortSignal.timeout(30000),
  });

  if (!res.ok) throw new Error('서버 오류');

  const data = await res.json();

  if (data.error) throw new Error(data.error);

  return data;
}

function detectCacheKey(sql) {
  const upper = sql.toUpperCase();
  if (/CONNECT\s+BY|START\s+WITH/.test(upper)) return 'HIGH';
  if (/TO_DATE|TO_CHAR|SYSDATE|SYSTIMESTAMP|TRUNC/.test(upper)) return 'MEDIUM';
  return 'LOW';
}

export async function getOfflineCache(sql) {
  const mod = await import('../data/mock_diagnose_result.json');
  const cache = mod.default;
  const key = detectCacheKey(sql);
  return cache[key];
}
