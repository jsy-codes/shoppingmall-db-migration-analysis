import React, { useState } from 'react';
import { Search, Copy, Check, AlertTriangle, Shield, Info, Sun, Moon } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import rules from '../../backend/validation/pattern_rules.json';
import mockData from './data/mock_diagnose_result.json';
import { fetchDiagnose } from './api/diagnose';

// ─── 위험도 설정 ───────────────────────────────────────────────
// risk_level 값(HIGH/MEDIUM/LOW)에 따라 색상, 아이콘, 라벨 매핑
const riskConfig = {
  HIGH:   { label: 'HIGH',   bg: 'bg-red-500/20',    border: 'border-red-500/40',    text: 'text-red-400',    icon: <AlertTriangle size={16} /> },
  MEDIUM: { label: 'MEDIUM', bg: 'bg-yellow-500/20', border: 'border-yellow-500/40', text: 'text-yellow-400', icon: <Shield size={16} /> },
  LOW:    { label: 'LOW',    bg: 'bg-green-500/20',  border: 'border-green-500/40',  text: 'text-green-400',  icon: <Info size={16} /> },
};

// ─── Mock 설정 ─────────────────────────────────────────────
// .env에서 VITE_MOCK=true 설정 시 실제 API 호출 없이 mockData 반환
const IS_MOCK = import.meta.env.VITE_MOCK === 'true';

// ─── Mock 데이터에서 성능/히트맵 데이터 가져오기 ────────────────
// mock_diagnose_result.json에서 통합 관리
// 실제 데이터 수신 후 mock_diagnose_result.json의 해당 배열을 교체하면 됨
const performanceData = IS_MOCK ? mockData.performance_data : [];
const riskScoreData   = IS_MOCK ? mockData.risk_score_data  : [];

// ─── 히트맵 색상 계산 ───────────────────────────────────────────
// score 기준으로 색상 반환
// isMatched=true 이면 이번 쿼리에서 감지된 패턴 → 더 강한 빨간색
const getRiskColor = (score, isMatched = false) => {
  if (isMatched) return { bg: 'bg-red-500/30', text: 'text-red-300', border: 'border-red-500/60', bar: '#ef4444' };
  if (score >= 70) return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30', bar: '#ef4444' };
  if (score >= 40) return { bg: 'bg-yellow-500/20', text: 'text-yellow-400', border: 'border-yellow-500/30', bar: '#eab308' };
  return { bg: 'bg-green-500/20', text: 'text-green-400', border: 'border-green-500/30', bar: '#22c55e' };
};

// ─── 성능 비교 차트 툴팁 ────────────────────────────────────────
// 차트 호버 시 Before/After/개선율 표시
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    const d = performanceData.find(p => p.label === label);
    return (
      <div className="bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm">
        <p className="font-bold text-zinc-100 mb-2">{d?.pattern} {label}</p>
        <p className="text-red-400">Before: {payload.find(p => p.dataKey === 'before')?.value?.toLocaleString()}ms</p>
        <p className="text-green-400">After:  {payload.find(p => p.dataKey === 'after')?.value?.toLocaleString()}ms</p>
        <p className="text-yellow-400 font-bold mt-1">{d?.improvement}% 개선</p>
      </div>
    );
  }
  return null;
};

// ─── 로컬 패턴 매칭 ─────────────────────────────────────────────
// 백엔드 연결 실패 시 프론트에서 직접 SQL을 분석하는 fallback 함수
// pattern_rules.json의 regex/heuristic 규칙으로 패턴 감지
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

// ─── 최고 위험도 패턴 선택 ──────────────────────────────────────
// 여러 패턴 감지 시 HIGH > MEDIUM > LOW 순으로 가장 위험한 것 반환
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
  const [topRule, setTopRule] = useState(null);            // 가장 위험한 패턴 하나
  const [matchedAll, setMatchedAll] = useState([]);        // 감지된 모든 패턴 목록
  const [hasResult, setHasResult] = useState(false);       // 결과 유무 (화면 전환용)
  const [isApiConnected, setIsApiConnected] = useState(false); // 백엔드 연결 여부
  const [matchedPatternIds, setMatchedPatternIds] = useState([]); // 히트맵 강조용 ID 목록
  const [performanceData, setPerformanceData] = useState([]);
  const [riskScoreData, setRiskScoreData] = useState([]);

  const theme = {
    bg:      isDarkMode ? 'bg-[#121212]' : 'bg-zinc-200',
    card:    isDarkMode ? 'bg-[#1e1e1e] border-zinc-800' : 'bg-white border-zinc-200',
    text:    isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    button:  isDarkMode ? 'bg-zinc-100 text-zinc-900 hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700',
  };

  // ─── API 응답 데이터 처리 ──────────────────────────────────────
  // 백엔드 응답 또는 Mock 데이터를 받아서 상태에 저장
  // rule_id로 pattern_rules.json에서 패턴 정보를 찾아 병합
  // 백엔드 응답 필드:
  //   rule_id, risk_level, reason, recommended_ddl,
  //   estimated_improvement, risk_score, matched_pattern_ids
  const processApiData = (data) => {
    if (data.performance_data) setPerformanceData(data.performance_data);
    if (data.risk_score_data) setRiskScoreData(data.risk_score_data);
    const found = rules.find(r => r.id === data.rule_id);
    setMatchedPatternIds(data.matched_pattern_ids || []);
    setTopRule(found ? {
      ...found,                                          // pattern_rules.json 기본 정보
      recommended_ddl:       data.recommended_ddl,      // AI가 생성한 수정 쿼리
      reason:                data.reason,               // AI 분석 원인 설명
      estimated_improvement: data.estimated_improvement, // 예상 개선 효과
      risk_score:            data.risk_score,           // 위험도 점수 (0~100)
      matched_pattern_ids:   data.matched_pattern_ids,  // 감지된 패턴 ID 배열
    } : {
      // rule_id가 pattern_rules.json에 없을 때 fallback
      id: data.rule_id || '-',
      name: '알 수 없는 패턴',
      risk: data.risk_level || 'LOW',
      failure_type: '-',
      description: data.reason || '',
      impact: '',
      fix: null,
      recommended_ddl:       data.recommended_ddl,
      reason:                data.reason,
      estimated_improvement: data.estimated_improvement,
      risk_score:            data.risk_score,
      matched_pattern_ids:   data.matched_pattern_ids,
    });
    setMatchedAll(found ? [found] : []);
  };

  // ─── 진단 실행 ────────────────────────────────────────────────
  // 1. Mock 모드 → mockData 바로 반환
  // 2. 백엔드 연결 성공 → AI 분석 결과 사용
  // 3. 백엔드 연결 실패 → 로컬 패턴 매칭으로 fallback
  const runDiagnose = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setTopRule(null);
    setMatchedAll([]);
    setMatchedPatternIds([]);
    setHasResult(true);

    await new Promise(r => setTimeout(r, 600)); // 로딩 애니메이션용 딜레이

    // Mock 모드
    if (IS_MOCK) {
      setIsApiConnected(true);
      const matched = matchPatterns(query);
      const topId = matched.length > 0 ? getHighestRisk(matched).id : 'P03';

      // 감지된 패턴 ID에 맞는 Mock 결과 찾기
      const mockResult = mockData.results.find(r => r.rule_id === topId)
        || mockData.results[0]; // 없으면 첫 번째 결과 사용

      processApiData(mockResult);
      setLoading(false);
      return;
    }

    try {
      const data = await fetchDiagnose(query); // diagnose.js 함수 호출
      setIsApiConnected(true);
      processApiData(data);

    } catch (e) {
      // 백엔드 연결 실패 시 로컬 패턴 매칭으로 fallback
      setIsApiConnected(false);
      const matched = matchPatterns(query);

      if (matched.length === 0) {
        // 감지된 패턴 없음
        setTopRule({
          id: '-', name: '감지된 패턴 없음', risk: 'LOW', failure_type: '-',
          description: '감지된 위험 패턴이 없습니다.',
          impact: '이관 시 큰 문제가 없을 것으로 보입니다.',
          fix: null, recommended_ddl: null,
          reason: null, estimated_improvement: null,
          risk_score: null, matched_pattern_ids: [],
        });
        setMatchedAll([]);
        setMatchedPatternIds([]);
      } else {
        // 패턴 감지됨 → 가장 위험한 패턴을 카드 1에 표시
        const top = getHighestRisk(matched);
        setTopRule({
          ...top,
          recommended_ddl: null,       // 로컬 분석이므로 DDL 없음
          reason: null,                // 로컬 분석이므로 AI 설명 없음
          estimated_improvement: null, // 로컬 분석이므로 개선 효과 없음
          risk_score: null,
          matched_pattern_ids: matched.map(m => m.id),
        });
        setMatchedAll(matched);
        setMatchedPatternIds(matched.map(m => m.id));
      }
    } finally {
      setLoading(false);
    }
  };

  // ─── DDL 복사 ─────────────────────────────────────────────────
  const copyDdl = () => {
    const ddl = topRule?.recommended_ddl || '';
    if (!ddl) return;
    navigator.clipboard.writeText(ddl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const risk = topRule ? (riskConfig[topRule.risk] || riskConfig.LOW) : null;

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} font-sans transition-colors duration-700`}>

      {/* 우측 상단: API 연결 상태 + 다크모드 토글 */}
      <div className="fixed top-4 right-4 z-50 flex items-center gap-3">
        {hasResult && (
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full ${
            IS_MOCK
               ? 'bg-zinc-800 text-zinc-500'         // 오프라인 
              : isApiConnected
                ? 'bg-green-500/20 text-green-400'    // 백엔드 연결됨
                : 'bg-blue-500/20 text-blue-400'         // 로컬 분석
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${
              IS_MOCK ? 'bg-zinc-600' : isApiConnected ? 'bg-green-400' : 'bg-blue-400'
            }`} />
            {IS_MOCK ? '오프라인(mock)' : isApiConnected ? 'AI 연결됨' : '로컬 분석'}
          </div>
        )}
        <button
          onClick={() => setIsDarkMode(!isDarkMode)}
          className={`p-2 rounded-full transition-all hover:scale-110 ${
            isDarkMode ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-zinc-300 hover:bg-zinc-400'
          }`}
        >
          {isDarkMode ? <Sun size={18} /> : <Moon size={18} className="text-zinc-600" />}
        </button>
      </div>

      {/* ── 초기 화면: 결과 없을 때 입력창 정중앙 표시 ── */}
      {!hasResult && (
        <div className="min-h-screen flex flex-col items-center justify-center px-6">
          <div className="w-full max-w-3xl">
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-bold mb-2">AI 쿼리 진단</h1>
              <p className={`text-sm ${theme.subText}`}>
                Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다
              </p>
            </div>
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

      {/* ── 결과 화면: 진단 실행 후 표시 ── */}
      {hasResult && (
        <div className="max-w-3xl mx-auto px-6 py-10">

          <div className="mb-6">
            <h1 className="text-3xl font-bold mb-2">AI 쿼리 진단</h1>
            <p className={`text-sm ${theme.subText}`}>
              Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다
            </p>
          </div>

          {/* 입력창 (결과 화면에서는 높이 줄임) */}
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

          {/* 로딩 스피너 */}
          {loading && (
            <div className={`rounded-2xl border ${theme.card} p-12 flex flex-col items-center gap-4`}>
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-zinc-200 rounded-full animate-spin" />
              <p className={`text-sm ${theme.subText}`}>Analyzing...</p>
            </div>
          )}

          {/* ── 결과 카드들 ── */}
          {topRule && !loading && (
            <div className="flex flex-col gap-4">

              {/* 카드 1: 위험도 헤더 + 문제 설명 + 영향 + 권고 방향 */}
              {/* reason(AI) 있으면 우선 표시, 없으면 description(로컬) 표시 */}
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
                  {/* risk_score: 백엔드 연결 시에만 표시 */}
                  {topRule.risk_score && (
                    <span className={`text-xs px-2 py-0.5 rounded-full font-bold ml-1 ${
                      topRule.risk_score >= 70 ? 'bg-red-500/20 text-red-400' :
                      topRule.risk_score >= 40 ? 'bg-yellow-500/20 text-yellow-400' :
                                                  'bg-green-500/20 text-green-400'
                    }`}>
                      Score {topRule.risk_score}
                    </span>
                  )}
                  <span className={`ml-auto text-xs ${theme.subText}`}>{topRule.failure_type}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2">
                  <div className={`p-6 border-b md:border-b-0 md:border-r ${
                    isDarkMode ? 'border-zinc-800' : 'border-zinc-200'
                  }`}>
                    <p className={`text-xs font-bold mb-2 ${theme.subText}`}>문제 설명</p>
                    {/* AI 연결 시 reason, 로컬 분석 시 description */}
                    <p className="text-sm leading-relaxed">
                      {topRule.reason || topRule.description}
                    </p>
                  </div>
                  <div className="p-6">
                    <p className={`text-xs font-bold mb-2 ${theme.subText}`}>영향</p>
                    <p className="text-sm leading-relaxed">{topRule.impact}</p>
                  </div>
                </div>
                {/* fix: pattern_rules.json의 권고 방향 텍스트 */}
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
              {/* recommended_ddl: AI가 생성한 실행 가능한 MySQL 쿼리 */}
              {/* 백엔드 미연결 시 비어있음 */}
              <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
                <div className={`flex items-center justify-between px-6 py-4 border-b ${
                  isDarkMode ? 'border-zinc-800' : 'border-zinc-200'
                }`}>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-bold">권고 DDL</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-bold ${
                      topRule.risk === 'HIGH'   ? 'bg-red-500/20 text-red-400' :
                      topRule.risk === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400' :
                                                  'bg-green-500/20 text-green-400'
                    }`}>{topRule.risk}</span>
                    {/* AI 연결 또는 Mock 모드일 때만 'AI 생성' 표시 */}
                    {(isApiConnected || IS_MOCK) && (
                      <span className="text-xs text-green-400 opacity-60">AI 생성</span>
                    )}
                  </div>
                  <button
                    onClick={copyDdl}
                    disabled={!topRule.recommended_ddl}
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
                  {topRule.recommended_ddl || ''}
                </pre>
              </div>

              {/* 카드 3: 예상 개선 효과 */}
              {/* estimated_improvement: AI가 생성한 성능 개선 예측 */}
              {/* 백엔드 연결 시 채워짐, 미연결 시 안내 문구 표시 */}
              <div className={`rounded-2xl border ${theme.card} p-6`}>
                <p className={`text-xs font-bold mb-2 ${theme.subText}`}>예상 개선 효과</p>
                <p className="text-sm leading-relaxed">
                  {topRule.estimated_improvement || 'AI 진단 API 연동 후 표시됩니다'}
                </p>
              </div>

              {/* 카드 4: 성능 비교 차트 */}
              {/* Mock 모드: mockData.performance_data로 차트 표시 */}
              {/* 실제 API 연결: 빈 카드 (데이터 수신 후 mock_diagnose_result.json 교체) */}
              <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
                <div className={`px-6 py-4 border-b ${isDarkMode ? 'border-zinc-800' : 'border-zinc-200'}`}>
                  <p className="text-sm font-bold">성능 비교</p>
                  <p className={`text-xs mt-1 ${theme.subText}`}>패턴별 이관 전/후 실행시간 (ms)</p>
                </div>
                {performanceData.length > 0 ? (
                  <div className="p-6">
                    {/* 요약 수치 3개 */}
                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className={`rounded-xl p-4 ${isDarkMode ? 'bg-zinc-900/50' : 'bg-zinc-50'}`}>
                        <p className={`text-xs mb-1 ${theme.subText}`}>실험 패턴 수</p>
                        <p className="text-2xl font-bold">{performanceData.length}개</p>
                      </div>
                      <div className={`rounded-xl p-4 ${isDarkMode ? 'bg-zinc-900/50' : 'bg-zinc-50'}`}>
                        <p className={`text-xs mb-1 ${theme.subText}`}>평균 개선율</p>
                        <p className="text-2xl font-bold text-green-400">
                          {(performanceData.reduce((a, b) => a + b.improvement, 0) / performanceData.length).toFixed(1)}%
                        </p>
                      </div>
                      <div className={`rounded-xl p-4 ${isDarkMode ? 'bg-zinc-900/50' : 'bg-zinc-50'}`}>
                        <p className={`text-xs mb-1 ${theme.subText}`}>최대 개선</p>
                        <p className="text-2xl font-bold text-green-400">
                          {Math.max(...performanceData.map(d => d.improvement))}%
                        </p>
                      </div>
                    </div>
                    {/* Before/After 바 차트 */}
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart
                        data={performanceData.map(d => ({ ...d, name: `${d.pattern} ${d.label}` }))}
                        margin={{ top: 10, right: 10, left: 10, bottom: 50 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#3f3f46' : '#e4e4e7'} />
                        <XAxis dataKey="name" tick={{ fill: isDarkMode ? '#a1a1aa' : '#52525b', fontSize: 10 }} angle={-15} textAnchor="end" interval={0} />
                        <YAxis tick={{ fill: isDarkMode ? '#a1a1aa' : '#52525b', fontSize: 10 }} tickFormatter={v => `${v.toLocaleString()}ms`} />
                        <Tooltip content={<CustomTooltip />} />
                        <Bar dataKey="before" name="Before" fill="#ef4444" radius={[4, 4, 0, 0]} />
                        <Bar dataKey="after"  name="After"  fill="#22c55e" radius={[4, 4, 0, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <div className="p-6" />
                )}
              </div>

              {/* 카드 5: 위험도 히트맵 */}
              {/* matched_pattern_ids: 이번 쿼리에서 감지된 패턴 → 테두리 강조 + 감지됨 뱃지 */}
              {/* Mock 모드: mockData.risk_score_data로 표시 */}
              {/* 실제 API 연결: 빈 카드 (데이터 수신 후 mock_diagnose_result.json 교체) */}
              <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
                <div className={`px-6 py-4 border-b ${isDarkMode ? 'border-zinc-800' : 'border-zinc-200'}`}>
                  <p className="text-sm font-bold">위험도 스코어</p>
                  <p className={`text-xs mt-1 ${theme.subText}`}>
                    패턴별 Risk Score · 70↑ 위험 · 40~69 주의 · 40↓ 안전
                    {matchedPatternIds.length > 0 && (
                      <span className="text-red-400 ml-2">· 테두리 강조 = 이번 쿼리에서 감지됨</span>
                    )}
                  </p>
                </div>
                {riskScoreData.length > 0 ? (
                  <div className="p-6">
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      {riskScoreData.map(d => {
                        const isMatched = matchedPatternIds.includes(d.id);
                        const color = getRiskColor(d.score, isMatched);
                        return (
                          <div
                            key={d.id}
                            className={`rounded-xl border-2 p-4 flex flex-col items-center gap-2 transition-all ${color.bg} ${color.border} ${
                              isMatched ? 'ring-2 ring-red-500/50 scale-105' : ''
                            }`}
                          >
                            <span className={`text-xs font-mono font-bold ${color.text}`}>{d.id}</span>
                            <span className={`text-2xl font-bold ${color.text}`}>{d.score}</span>
                            <span className={`text-xs text-center ${theme.subText}`}>{d.name}</span>
                            {isMatched && <span className="text-xs text-red-400 font-bold">감지됨</span>}
                            <div className={`w-full h-1 rounded-full ${isDarkMode ? 'bg-zinc-800' : 'bg-zinc-200'}`}>
                              <div className="h-1 rounded-full transition-all" style={{ width: `${d.score}%`, backgroundColor: color.bar }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    {/* 범례 */}
                    <div className="flex gap-4 mt-4">
                      <div className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded-full bg-red-500" />
                        <span className={`text-xs ${theme.subText}`}>HIGH (70+)</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded-full bg-yellow-500" />
                        <span className={`text-xs ${theme.subText}`}>MEDIUM (40~69)</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <div className="w-3 h-3 rounded-full bg-green-500" />
                        <span className={`text-xs ${theme.subText}`}>LOW (0~39)</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="p-6" />
                )}
              </div>

              {/* 카드 6: 추가 감지 패턴 */}
              {/* 로컬 분석에서 여러 패턴 감지 시 2번째 이후 패턴 목록 표시 */}
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