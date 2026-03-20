import React, { useState } from 'react';
import { Search, Copy, Check, AlertTriangle, Shield, Info, Sun, Moon } from 'lucide-react';
import rules from '../../backend/validation/pattern_rules.json';

const riskConfig = {
  HIGH:   { label: 'HIGH',   bg: 'bg-red-500/20',    border: 'border-red-500/40',    text: 'text-red-400',    icon: <AlertTriangle size={16} /> },
  MEDIUM: { label: 'MEDIUM', bg: 'bg-yellow-500/20', border: 'border-yellow-500/40', text: 'text-yellow-400', icon: <Shield size={16} /> },
  LOW:    { label: 'LOW',    bg: 'bg-green-500/20',  border: 'border-green-500/40',  text: 'text-green-400',  icon: <Info size={16} /> },
};

const dummyDdl = {
  'P01': `-- CAST 명시로 타입 정렬\nSELECT * FROM orders WHERE member_id = 123`,
  'P02': `-- 생성 컬럼 + 인덱스 사용\nALTER TABLE members ADD name_upper VARCHAR(100) GENERATED ALWAYS AS (UPPER(name));\nCREATE INDEX idx_members_name_upper ON members(name_upper);\nSELECT * FROM members WHERE name_upper = 'KIM'`,
  'P03': `-- LIMIT/OFFSET 으로 변환\nSELECT * FROM orders\nWHERE status = 'COMPLETE'\nLIMIT 10`,
  'P04': `-- NVL → IFNULL 변환\nSELECT IFNULL(price, 0) FROM products`,
  'P05': `-- DATE → DATETIME 변환\nALTER TABLE orders MODIFY created_at DATETIME`,
  'P06': `-- VARCHAR2 → VARCHAR 변환\nALTER TABLE members MODIFY name VARCHAR(100)`,
  'P07': `-- CHAR → VARCHAR 변환\nALTER TABLE members MODIFY code VARCHAR(10)`,
  'P08': `-- 생성 컬럼 + 인덱스 사용\nALTER TABLE members ADD name_upper VARCHAR(100) GENERATED ALWAYS AS (UPPER(name));\nCREATE INDEX idx_name_upper ON members(name_upper)`,
  'P09': `-- 조인 키 인덱스 추가\nCREATE INDEX idx_orders_member_id ON orders(member_id);\nCREATE INDEX idx_orders_product_id ON orders(product_id)`,
  'P10': `-- 중첩 서브쿼리 → JOIN 재작성\nSELECT o.*, m.name\nFROM orders o\nJOIN members m ON o.member_id = m.id\nWHERE o.status = 'COMPLETE'`,
  'P11': `-- DECODE → CASE WHEN 변환\nSELECT CASE status WHEN 'Y' THEN '활성' WHEN 'N' THEN '비활성' ELSE '미정' END FROM members`,
  'P12': `-- CONNECT BY → WITH RECURSIVE 변환\nWITH RECURSIVE cte AS (\n  SELECT id, name, parent_id FROM categories WHERE parent_id IS NULL\n  UNION ALL\n  SELECT c.id, c.name, c.parent_id FROM categories c\n  JOIN cte ON c.parent_id = cte.id\n)\nSELECT * FROM cte`,
  'P13': `-- START WITH → recursive CTE base case\nWITH RECURSIVE cte AS (\n  SELECT id, name, parent_id FROM categories WHERE id = 1\n  UNION ALL\n  SELECT c.id, c.name, c.parent_id FROM categories c\n  JOIN cte ON c.parent_id = cte.id\n)\nSELECT * FROM cte`,
  'P14': `-- Oracle (+) → LEFT JOIN 변환\nSELECT o.*, m.name\nFROM orders o\nLEFT JOIN members m ON o.member_id = m.id`,
  'P15': `-- SYSDATE → NOW() 변환\nSELECT * FROM orders WHERE created_at > NOW()`,
  'P16': `-- SYSTIMESTAMP → CURRENT_TIMESTAMP 변환\nSELECT CURRENT_TIMESTAMP(6) FROM orders`,
  'P17': `-- MERGE INTO → INSERT ON DUPLICATE KEY UPDATE\nINSERT INTO orders (id, status) VALUES (1, 'COMPLETE')\nON DUPLICATE KEY UPDATE status = 'COMPLETE'`,
  'P18': `-- MINUS → NOT EXISTS 변환\nSELECT id FROM orders o\nWHERE NOT EXISTS (\n  SELECT 1 FROM returns r WHERE r.order_id = o.id\n)`,
  'P19': `-- FROM DUAL 제거\nSELECT NOW()`,
  'P20': `-- TO_CHAR → DATE_FORMAT 변환\nSELECT DATE_FORMAT(created_at, '%Y-%m-%d') FROM orders`,
  'P21': `-- TO_DATE → STR_TO_DATE 변환\nSELECT STR_TO_DATE('2024-01-01', '%Y-%m-%d')`,
  'P22': `-- TRUNC → DATE() 변환\nSELECT DATE(created_at) FROM orders`,
};

function matchPatterns(sql) {
  const matched = [];
  for (const rule of rules) {
    if (rule.type === 'regex' && rule.pattern) {
      if (new RegExp(rule.pattern, 'i').test(sql)) matched.push(rule);
    } else if (rule.type === 'heuristic') {
      if (rule.heuristic === 'implicit_cast') {
        if (/\b[A-Z_][A-Z0-9_]*\s*=\s*'\d+'/i.test(sql)) matched.push(rule);
      } else if (rule.heuristic === 'join_without_index') {
        if (/JOIN/i.test(sql) && !/USE INDEX|FORCE INDEX|CREATE INDEX/i.test(sql)) matched.push(rule);
      } else if (rule.heuristic === 'nested_subquery') {
        if ((sql.match(/SELECT/gi) || []).length >= 2) matched.push(rule);
      }
    }
  }
  return matched;
}

function getHighestRisk(matched) {
  const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };
  return matched.reduce((prev, curr) =>
    (rank[curr.risk] || 0) > (rank[prev.risk] || 0) ? curr : prev
  );
}

export default function App() {
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [query, setQuery] = useState('');
  const [topRule, setTopRule] = useState(null);
  const [matchedAll, setMatchedAll] = useState([]);
  const [hasResult, setHasResult] = useState(false);

  const theme = {
    bg:      isDarkMode ? 'bg-[#121212]' : 'bg-zinc-200',
    card:    isDarkMode ? 'bg-[#1e1e1e] border-zinc-800' : 'bg-white border-zinc-200',
    text:    isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    button:  isDarkMode ? 'bg-zinc-100 text-zinc-900 hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700',
  };

  const runDiagnose = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setTopRule(null);
    setMatchedAll([]);
    setHasResult(true);

    await new Promise(r => setTimeout(r, 600));

    try {
      const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      const res = await fetch(`${apiUrl}/diagnose`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sql: query }),
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) throw new Error('서버 오류');
      const data = await res.json();
      const found = rules.find(r => r.id === data.rule_id);
      setTopRule(found ? { ...found, recommended_ddl: data.recommended_ddl } : null);
      setMatchedAll(found ? [found] : []);
    } catch (e) {
      const matched = matchPatterns(query);
      if (matched.length === 0) {
        setTopRule({
          id: '-',
          name: '감지된 패턴 없음',
          risk: 'LOW',
          failure_type: '-',
          description: '감지된 위험 패턴이 없습니다.',
          impact: '이관 시 큰 문제가 없을 것으로 보입니다.',
          fix: null,
          recommended_ddl: null,
          quant_signal: '현재 쿼리를 그대로 사용해도 무방합니다.',
        });
        setMatchedAll([]);
      } else {
        const top = getHighestRisk(matched);
        setTopRule({ ...top, recommended_ddl: null });
        setMatchedAll(matched);
      }
    } finally {
      setLoading(false);
    }
  };

  const copyDdl = () => {
    const ddl = topRule?.recommended_ddl || dummyDdl[topRule?.id] || '';
    if (!ddl) return;
    navigator.clipboard.writeText(ddl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const risk = topRule ? (riskConfig[topRule.risk] || riskConfig.LOW) : null;

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} font-sans transition-colors duration-700`}>

      {/* 우측 상단 다크모드 토글 */}
      <div className="fixed top-4 right-4 z-50">
        <button
          onClick={() => setIsDarkMode(!isDarkMode)}
          className={`p-2 rounded-full transition-all hover:scale-110 ${
            isDarkMode ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-zinc-300 hover:bg-zinc-400'
          }`}
        >
          {isDarkMode ? <Sun size={18} /> : <Moon size={18} className="text-zinc-600" />}
        </button>
      </div>

      {/* 결과 없을 때: 입력창 화면 정중앙 */}
      {!hasResult && (
        <div className="min-h-screen flex flex-col items-center justify-center px-6">
          <div className="w-full max-w-3xl">
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-bold mb-2">AI 쿼리 진단</h1>
              <p className={`text-sm ${theme.subText}`}>
                Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다
              </p>
            </div>

            {/* 입력창 1 — 가운데 화면 */}
            <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
              <textarea
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => { if (e.ctrlKey && e.key === 'Enter') runDiagnose(); }}
                placeholder={`분석할 Oracle SQL 쿼리를 입력하세요...\n\n예시) SELECT * FROM orders WHERE ROWNUM <= 10`}
                className={`w-full h-44 p-6 outline-none font-mono text-sm resize-none ${
                  isDarkMode
                    ? 'bg-[#1e1e1e] text-zinc-100 placeholder:text-zinc-600'
                    : 'bg-white text-zinc-800 placeholder:text-zinc-400'
                }`}
              />
              <div className={`flex items-center justify-between px-6 py-3 border-t ${
                isDarkMode ? 'border-zinc-800 bg-[#1a1a1a]' : 'border-zinc-200 bg-zinc-50'
              }`}>
                <span className="text-xs font-mono opacity-40">Oracle → MySQL · Ctrl+Enter</span>
                <button
                  onClick={runDiagnose}
                  disabled={loading || !query.trim()}
                  className={`flex items-center gap-2 px-6 py-2 rounded-full font-bold text-xs uppercase tracking-widest transition-all hover:scale-105 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed ${theme.button}`}
                >
                  <Search size={14} />
                  {loading ? 'Analyzing...' : 'Run Diagnose'}
                </button>
              </div>
            </div>

          </div>
        </div>
      )}

      {/* 결과 있을 때 */}
      {hasResult && (
        <div className="max-w-3xl mx-auto px-6 py-10">

          {/* 타이틀 */}
          <div className="mb-6">
            <h1 className="text-3xl font-bold mb-2">AI 쿼리 진단</h1>
            <p className={`text-sm ${theme.subText}`}>
              Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다
            </p>
          </div>

          {/* 입력창 2 — 결과 화면 */}
          <div className={`rounded-2xl border ${theme.card} overflow-hidden mb-6`}>
            <textarea
              value={query}
              onChange={e => setQuery(e.target.value)}
              onKeyDown={e => { if (e.ctrlKey && e.key === 'Enter') runDiagnose(); }}
              placeholder="분석할 Oracle SQL 쿼리를 입력하세요..."
              className={`w-full h-32 p-6 outline-none font-mono text-sm resize-none ${
                isDarkMode
                  ? 'bg-[#1e1e1e] text-zinc-100 placeholder:text-zinc-600'
                  : 'bg-white text-zinc-800 placeholder:text-zinc-400'
              }`}
            />
            <div className={`flex items-center justify-between px-6 py-3 border-t ${
              isDarkMode ? 'border-zinc-800 bg-[#1a1a1a]' : 'border-zinc-200 bg-zinc-50'
            }`}>
              <span className="text-xs font-mono opacity-40">Oracle → MySQL · Ctrl+Enter</span>
              <button
                onClick={runDiagnose}
                disabled={loading || !query.trim()}
                className={`flex items-center gap-2 px-6 py-2 rounded-full font-bold text-xs uppercase tracking-widest transition-all hover:scale-105 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed ${theme.button}`}
              >
                <Search size={14} />
                {loading ? 'Analyzing...' : 'Run Diagnose'}
              </button>
            </div>
          </div>

          {/* 로딩 */}
          {loading && (
            <div className={`rounded-2xl border ${theme.card} p-12 flex flex-col items-center gap-4`}>
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-zinc-200 rounded-full animate-spin" />
              <p className={`text-sm ${theme.subText}`}>Analyzing...</p>
            </div>
          )}

          {/* 결과 카드들 */}
          {topRule && !loading && (
            <div className="flex flex-col gap-4">

              {/* 카드 1: 위험도 + 문제설명 + 영향 + 권고 방향 */}
              <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
                <div className={`flex items-center gap-3 px-6 py-5 border-b ${
                  isDarkMode ? 'border-zinc-800' : 'border-zinc-200'
                } ${risk.bg}`}>
                  <span className={risk.text}>{risk.icon}</span>
                  <span className={`text-lg font-bold ${risk.text}`}>{risk.label} RISK</span>
                  <span className={`text-xs font-mono px-2 py-0.5 rounded ${
                    isDarkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-zinc-200 text-zinc-600'
                  }`}>{topRule.id}</span>
                  <span className="text-sm font-medium ml-1">{topRule.name}</span>
                  <span className={`ml-auto text-xs ${theme.subText}`}>{topRule.failure_type}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2">
                  <div className={`p-6 border-b md:border-b-0 md:border-r ${
                    isDarkMode ? 'border-zinc-800' : 'border-zinc-200'
                  }`}>
                    <p className={`text-xs font-bold mb-2 ${theme.subText}`}>문제 설명</p>
                    <p className="text-sm leading-relaxed">{topRule.description}</p>
                  </div>
                  <div className="p-6">
                    <p className={`text-xs font-bold mb-2 ${theme.subText}`}>영향</p>
                    <p className="text-sm leading-relaxed">{topRule.impact}</p>
                  </div>
                </div>
                {topRule.fix && (
                  <div className={`px-6 py-4 border-t ${
                    isDarkMode ? 'border-zinc-800 bg-zinc-900/30' : 'border-zinc-200 bg-zinc-50'
                  }`}>
                    <p className={`text-xs font-bold mb-2 ${theme.subText}`}>권고 방향</p>
                    <p className="text-sm font-mono text-green-400">{topRule.fix}</p>
                  </div>
                )}
              </div>

              {/* 카드 2: 권고 DDL */}
              <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
                <div className={`flex items-center justify-between px-6 py-4 border-b ${
                  isDarkMode ? 'border-zinc-800' : 'border-zinc-200'
                }`}>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold">권고 DDL 예시</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                      topRule.risk === 'HIGH'   ? 'bg-red-500/20 text-red-400' :
                      topRule.risk === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                                                  'bg-green-500/20 text-green-400'
                    }`}>
                      {topRule.risk}
                    </span>
                  </div>
                  <button
                    onClick={copyDdl}
                    disabled={!topRule.recommended_ddl && !dummyDdl[topRule.id]}
                    className={`flex items-center gap-2 text-xs px-3 py-1.5 rounded-lg transition-all disabled:opacity-30 disabled:cursor-not-allowed ${
                      isDarkMode
                        ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300'
                        : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-600'
                    }`}
                  >
                    {copied ? <Check size={12} /> : <Copy size={12} />}
                    {copied ? '복사됨!' : '복사'}
                  </button>
                </div>
                <pre className="px-6 py-5 font-mono text-sm text-green-400 overflow-x-auto bg-zinc-900 min-h-16">
                  {topRule.recommended_ddl || dummyDdl[topRule.id] || ''}
                </pre>
              </div>

              {/* 카드 3: 예상 개선 효과 — API 연동 후 사용 */}
              <div className={`rounded-2xl border ${theme.card} p-6`}>
                <p className={`text-xs font-bold mb-2 ${theme.subText}`}>예상 개선 효과</p>
                <p className={`text-sm ${theme.subText}`}>...</p>
              </div>

              {/* 카드 4: 추가 감지 패턴 */}
              {matchedAll.length > 1 && (
                <div className={`rounded-2xl border ${theme.card} p-6`}>
                  <p className={`text-xs font-bold mb-3 ${theme.subText}`}>
                    추가 감지된 패턴 ({matchedAll.length - 1}개)
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {matchedAll.slice(1).map(r => (
                      <span key={r.id} className={`text-xs px-3 py-1 rounded-full font-mono ${
                        r.risk === 'HIGH'   ? 'bg-red-500/20 text-red-400' :
                        r.risk === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                                              'bg-green-500/20 text-green-400'
                      }`}>
                        {r.id} {r.name}
                      </span>
                    ))}
                  </div>
                </div>
              )}

            </div>
          )}

        </div>
      )}

    </div>
  );
}