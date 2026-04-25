// ─── API 호출 함수 모음 ──────────────────────────────────────────
// 백엔드 /diagnose 엔드포인트 호출
// 요청 형식: { "sql": "입력한 SQL 문자열" }
// 응답 형식: { rule_id, risk_level, reason, recommended_ddl,
//              estimated_improvement, risk_score, matched_pattern_ids }

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function fetchDiagnose(sql) {
  const res = await fetch(`${API_URL}/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sql }),
    credentials: 'include',
    signal: AbortSignal.timeout(30000), // 30초 타임아웃
  });

  if (!res.ok) throw new Error('서버 오류');

  const data = await res.json();

  if (data.error) throw new Error(data.error);

  return data;
}