import React, { useState, useRef, useCallback, useEffect } from 'react';
import {
  Search, Copy, Check, AlertTriangle, Shield, Info,
  Sun, Moon, ChevronDown, ChevronUp, Upload, FileText,
  BarChart2, Zap, X
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';

// ─── 외부 의존성 import (기존 유지) ─────────────────────────────
// import rules from '../../backend/validation/pattern_rules.json';
// import mockData from './data/mock_diagnose_result.json';
// import { fetchDiagnose } from './api/diagnose';

// ─── 개발용 더미 (실제 프로젝트에서는 위 import로 교체) ──────────
const rules = [
  { id: 'P01', name: 'ROWNUM 사용', risk: 'HIGH', failure_type: '문법 오류', description: 'Oracle 전용 ROWNUM은 MySQL에서 지원되지 않습니다.', impact: '쿼리 실행 실패', fix: 'LIMIT / ROW_NUMBER() OVER() 로 변환', type: 'regex', pattern: 'ROWNUM' },
  { id: 'P02', name: 'SYSDATE 사용', risk: 'MEDIUM', failure_type: '함수 불일치', description: 'SYSDATE()는 MySQL에서 동작 방식이 다릅니다.', impact: '날짜 데이터 불일치', fix: 'NOW() 또는 CURRENT_TIMESTAMP() 로 변환', type: 'regex', pattern: 'SYSDATE' },
  { id: 'P03', name: 'NVL 사용', risk: 'MEDIUM', failure_type: '함수 불일치', description: 'NVL은 Oracle 전용 NULL 처리 함수입니다.', impact: '쿼리 실행 실패', fix: 'IFNULL() 또는 COALESCE() 로 변환', type: 'regex', pattern: '\\bNVL\\b' },
  { id: 'P04', name: 'SELECT *', risk: 'LOW', failure_type: '성능 위험', description: '모든 컬럼을 조회하면 불필요한 데이터 전송이 발생합니다.', impact: '쿼리 성능 저하', fix: '필요한 컬럼만 명시적으로 선택', type: 'regex', pattern: 'SELECT\\s+\\*' },
  { id: 'P05', name: 'CONNECT BY', risk: 'HIGH', failure_type: '문법 오류', description: '계층 쿼리 Oracle 전용 문법입니다.', impact: '쿼리 실행 불가', fix: 'WITH RECURSIVE CTE로 변환', type: 'regex', pattern: 'CONNECT BY' },
  { id: 'P06', name: 'JOIN without INDEX', risk: 'HIGH', failure_type: '성능 위험', description: '인덱스 없는 JOIN은 풀스캔을 유발합니다.', impact: '쿼리 성능 심각 저하', fix: 'JOIN 컬럼에 인덱스 생성', type: 'heuristic', heuristic: 'join_without_index' },
  { id: 'P07', name: 'Nested Subquery', risk: 'MEDIUM', failure_type: '성능 위험', description: '중첩 서브쿼리는 반복 실행으로 성능 저하를 유발합니다.', impact: '실행시간 증가', fix: 'JOIN 또는 WITH CTE로 리팩토링', type: 'heuristic', heuristic: 'nested_subquery' },
  { id: 'P08', name: 'Implicit Cast', risk: 'MEDIUM', failure_type: '타입 불일치', description: '암묵적 형변환은 인덱스를 무력화합니다.', impact: '인덱스 미사용, 성능 저하', fix: '명시적 CAST() 사용', type: 'heuristic', heuristic: 'implicit_cast' },
];

const IS_MOCK = import.meta.env.VITE_MOCK === 'true';

const riskConfig = {
  HIGH:   { label: 'HIGH',   bg: 'bg-red-500/20',    border: 'border-red-500/40',    text: 'text-red-400',    icon: <AlertTriangle size={14} />, bar: '#ef4444' },
  MEDIUM: { label: 'MEDIUM', bg: 'bg-yellow-500/20', border: 'border-yellow-500/40', text: 'text-yellow-400', icon: <Shield size={14} />,        bar: '#eab308' },
  LOW:    { label: 'LOW',    bg: 'bg-green-500/20',  border: 'border-green-500/40',  text: 'text-green-400',  icon: <Info size={14} />,           bar: '#22c55e' },
};

// ─── 로컬 패턴 매칭 (fallback) ────────────────────────────────
function matchPatterns(sql) {
  const matched = [];
  for (const rule of rules) {
    if (rule.type === 'regex' && rule.pattern) {
      if (new RegExp(rule.pattern, 'i').test(sql)) matched.push(rule);
    } else if (rule.type === 'heuristic') {
      if (rule.heuristic === 'implicit_cast' && /\b[A-Z_][A-Z0-9_]*\s*=\s*'\d+'/i.test(sql)) matched.push(rule);
      if (rule.heuristic === 'join_without_index' && /JOIN/i.test(sql) && !/USE INDEX|FORCE INDEX|CREATE INDEX/i.test(sql)) matched.push(rule);
      if (rule.heuristic === 'nested_subquery' && (sql.match(/SELECT/gi) || []).length >= 2) matched.push(rule);
    }
  }
  return matched;
}

function getHighestRisk(matched) {
  const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };
  return matched.reduce((prev, curr) => (rank[curr.risk] || 0) > (rank[prev.risk] || 0) ? curr : prev);
}

function calcRiskScore(matched) {
  const weights = { HIGH: 35, MEDIUM: 15, LOW: 5 };
  const raw = matched.reduce((sum, m) => sum + (weights[m.risk] || 0), 0);
  return Math.min(100, raw);
}

function splitSQLs(raw) {
  return raw.split(';').map(s => s.trim()).filter(s => s.length > 5);
}

function analyzeSQL(sql, index) {
  const matched = matchPatterns(sql);
  const score = calcRiskScore(matched);
  const top = matched.length > 0 ? getHighestRisk(matched) : null;
  return { index, sql, matched, top, score, risk: top?.risk || 'LOW', recommended_ddl: null, reason: null, estimated_improvement: null };
}

function calcSummary(results) {
  const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 };
  results.forEach(r => counts[r.risk]++);
  const avgScore = results.length ? Math.round(results.reduce((s, r) => s + r.score, 0) / results.length) : 0;
  const maxScore = results.length ? Math.max(...results.map(r => r.score)) : 0;
  return { counts, avgScore, maxScore, total: results.length };
}

// ─── 타이핑 애니메이션 컴포넌트 ──────────────────────────────────
function TypewriterText({ text, speed = 8, className = '' }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!text) { setDone(true); return; }
    setDisplayed('');
    setDone(false);
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) {
        clearInterval(interval);
        setDone(true);
      }
    }, speed);
    return () => clearInterval(interval);
  }, [text, speed]);

  return (
    <span className={className}>
      {displayed}
      {!done && <span className="animate-pulse text-green-400">▍</span>}
    </span>
  );
}

// ─── 컴포넌트 ─────────────────────────────────────────────────

function RiskBadge({ risk, score }) {
  const cfg = riskConfig[risk] || riskConfig.LOW;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.text} border ${cfg.border}`}>
      {cfg.icon} {cfg.label} {score != null ? `· ${score}` : ''}
    </span>
  );
}

function SummaryBar({ counts, total }) {
  const pct = (n) => total ? Math.round((n / total) * 100) : 0;
  return (
    <div className="flex rounded-full overflow-hidden h-2 w-full">
      <div className="bg-red-500 transition-all" style={{ width: `${pct(counts.HIGH)}%` }} />
      <div className="bg-yellow-500 transition-all" style={{ width: `${pct(counts.MEDIUM)}%` }} />
      <div className="bg-green-500 transition-all" style={{ width: `${pct(counts.LOW)}%` }} />
    </div>
  );
}

// ─── 아코디언 아이템 ─────────────────────────────────────────
function QueryAccordion({ result, index, isDarkMode, delay = 0 }) {
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  // 카드 순차 등장 + HIGH 자동 펼침
  useEffect(() => {
    const t = setTimeout(() => {
      setVisible(true);
      if (result.risk === 'HIGH') setOpen(true);
    }, delay);
    return () => clearTimeout(t);
  }, [delay, result.risk]);

  const theme = {
    card:    isDarkMode ? 'bg-[#1e1e1e] border-zinc-800' : 'bg-white border-zinc-200',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    inner:   isDarkMode ? 'bg-zinc-900/50' : 'bg-zinc-50',
    divider: isDarkMode ? 'border-zinc-800' : 'border-zinc-200',
  };
  const cfg = riskConfig[result.risk] || riskConfig.LOW;

  const copyDdl = () => {
    if (!result.recommended_ddl) return;
    navigator.clipboard.writeText(result.recommended_ddl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shortSQL = result.sql.length > 40 ? result.sql.slice(0, 40) + '…' : result.sql;

  return (
    <div
      className={`rounded-2xl border ${theme.card} overflow-hidden transition-all duration-500 ${
        visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
      }`}
    >
      {/* 헤더 */}
      <button
        onClick={() => setOpen(!open)}
        className={`w-full flex items-center gap-3 px-5 py-4 text-left transition-colors ${cfg.bg} hover:opacity-90`}
      >
        <span className={`text-xs font-mono font-bold ${theme.subText} shrink-0`}>
          #{String(index + 1).padStart(2, '0')}
        </span>
        <RiskBadge risk={result.risk} score={result.score} />
        {result.top && (
          <span className={`text-xs font-mono px-2 py-0.5 rounded ${isDarkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-zinc-200 text-zinc-600'}`}>
            {result.top.id}
          </span>
        )}
        <span className="text-sm font-medium truncate flex-1">{result.top?.name || '패턴 없음'}</span>
        <span className={`text-xs ${theme.subText} font-mono shrink-0 hidden md:block max-w-50 truncate`}>{shortSQL}</span>
        <span className={`shrink-0 ${cfg.text}`}>
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </span>
      </button>

      {/* 상세 내용 */}
      {open && (
        <div className="flex flex-col gap-0">

          {/* SQL 원문 */}
          <div className={`px-5 py-4 border-t ${theme.divider}`}>
            <p className={`text-xs font-bold mb-2 ${theme.subText}`}>SQL 원문</p>
            <pre className={`text-xs font-mono p-3 rounded-xl overflow-x-auto ${theme.inner} text-zinc-300`}>
              {result.sql}
            </pre>
          </div>

          {/* 문제 설명 - 타이핑 애니메이션 */}
          {result.reason && (
            <div className={`px-5 py-4 border-t ${theme.divider}`}>
              <p className={`text-xs font-bold mb-2 ${theme.subText}`}>문제 설명</p>
              <p className="text-sm leading-relaxed">
                <TypewriterText text={result.reason} speed={6} />
              </p>
            </div>
          )}

          {/* 감지된 패턴 목록 */}
          {result.matched.length > 0 && (
            <div className={`px-5 py-4 border-t ${theme.divider}`}>
              <p className={`text-xs font-bold mb-3 ${theme.subText}`}>
                감지된 패턴 ({result.matched.length}개)
              </p>
              <div className="flex flex-col gap-2">
                {result.matched.map(m => {
                  const mc = riskConfig[m.risk] || riskConfig.LOW;
                  return (
                    <div key={m.id} className={`flex items-start gap-3 p-3 rounded-xl border ${mc.bg} ${mc.border}`}>
                      <span className={`text-xs font-mono font-bold shrink-0 mt-0.5 ${mc.text}`}>{m.id}</span>
                      <div className="flex-1 min-w-0">
                        <p className={`text-xs font-bold ${mc.text}`}>{m.name}</p>
                        <p className={`text-xs mt-0.5 ${theme.subText}`}>{m.description}</p>
                        {m.fix && (
                          <p className="text-xs mt-1 text-green-400 font-mono">→ {m.fix}</p>
                        )}
                      </div>
                      <RiskBadge risk={m.risk} />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {result.matched.length === 0 && (
            <div className={`px-5 py-4 border-t ${theme.divider}`}>
              <p className="text-sm text-green-400">✓ 감지된 위험 패턴 없음</p>
            </div>
          )}

          {/* 권고 DDL - 타이핑 애니메이션 */}
          <div className={`border-t ${theme.divider} overflow-hidden`}>
            <div className={`flex items-center justify-between px-5 py-3 border-b ${theme.divider}`}>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold">권고 DDL</span>
                {result.recommended_ddl && (
                  <span className="text-xs text-green-400 opacity-60">AI 생성</span>
                )}
              </div>
              <button
                onClick={copyDdl}
                disabled={!result.recommended_ddl}
                className={`flex items-center gap-1.5 text-xs px-3 py-1 rounded-lg transition-all disabled:opacity-30 ${
                  isDarkMode ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300' : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-600'
                }`}
              >
                {copied ? <Check size={11} /> : <Copy size={11} />}
                {copied ? '복사됨' : '복사'}
              </button>
            </div>
            <pre className="px-5 py-4 font-mono text-xs text-green-400 overflow-x-auto overflow-y-auto bg-zinc-900 max-h-48">
              {result.recommended_ddl
                ? <TypewriterText text={result.recommended_ddl} speed={3} />
                : (result.matched.length === 0 ? '-- 권고 DDL 없음' : '-- API 연동 후 AI 생성 DDL이 표시됩니다')
              }
            </pre>
          </div>

          {/* 예상 개선 효과 - 타이핑 애니메이션 */}
          {result.estimated_improvement && (
            <div className={`px-5 py-4 border-t ${theme.divider}`}>
              <p className={`text-xs font-bold mb-1 ${theme.subText}`}>예상 개선 효과</p>
              <p className="text-sm leading-relaxed">
                <TypewriterText text={result.estimated_improvement} speed={6} />
              </p>
            </div>
          )}

        </div>
      )}
    </div>
  );
}

// ─── 배치 요약 대시보드 ───────────────────────────────────────
function BatchSummary({ summary, results, isDarkMode }) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, []);

  const theme = {
    card:    isDarkMode ? 'bg-[#1e1e1e] border-zinc-800' : 'bg-white border-zinc-200',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    inner:   isDarkMode ? 'bg-zinc-900/60' : 'bg-zinc-50',
  };

  const chartData = results.map((r, i) => ({
    name: `#${String(i + 1).padStart(2, '0')}`,
    score: r.score,
    risk: r.risk,
  }));

  return (
    <div className={`rounded-2xl border ${theme.card} overflow-hidden mb-4 transition-all duration-500 ${
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
    }`}>
      <div className={`px-6 py-4 border-b ${isDarkMode ? 'border-zinc-800' : 'border-zinc-200'} flex items-center gap-2`}>
        <BarChart2 size={15} className="text-zinc-400" />
        <span className="text-sm font-bold">배치 분석 요약</span>
        <span className={`text-xs ${theme.subText} ml-auto`}>총 {summary.total}개 쿼리</span>
      </div>

      <div className="p-6 flex flex-col gap-5">
        <div>
          <div className="flex justify-between mb-2">
            <span className={`text-xs font-bold ${theme.subText}`}>위험도 분포</span>
            <div className="flex gap-3">
              <span className="text-xs text-red-400 font-bold">HIGH {summary.counts.HIGH}</span>
              <span className="text-xs text-yellow-400 font-bold">MEDIUM {summary.counts.MEDIUM}</span>
              <span className="text-xs text-green-400 font-bold">LOW {summary.counts.LOW}</span>
            </div>
          </div>
          <SummaryBar counts={summary.counts} total={summary.total} />
        </div>

        <div className="grid grid-cols-3 gap-3">
          <div className={`rounded-xl p-4 ${theme.inner}`}>
            <p className={`text-xs mb-1 ${theme.subText}`}>평균 Risk Score</p>
            <p className={`text-2xl font-bold ${
              summary.avgScore >= 70 ? 'text-red-400' :
              summary.avgScore >= 40 ? 'text-yellow-400' : 'text-green-400'
            }`}>{summary.avgScore}</p>
          </div>
          <div className={`rounded-xl p-4 ${theme.inner}`}>
            <p className={`text-xs mb-1 ${theme.subText}`}>최고 Risk Score</p>
            <p className={`text-2xl font-bold ${
              summary.maxScore >= 70 ? 'text-red-400' :
              summary.maxScore >= 40 ? 'text-yellow-400' : 'text-green-400'
            }`}>{summary.maxScore}</p>
          </div>
          <div className={`rounded-xl p-4 ${theme.inner}`}>
            <p className={`text-xs mb-1 ${theme.subText}`}>HIGH 위험 쿼리</p>
            <p className="text-2xl font-bold text-red-400">{summary.counts.HIGH}개</p>
          </div>
        </div>

        {results.length > 1 && (
          <ResponsiveContainer width="100%" height={120}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#3f3f46' : '#e4e4e7'} />
              <XAxis dataKey="name" tick={{ fill: isDarkMode ? '#a1a1aa' : '#52525b', fontSize: 10 }} />
              <YAxis domain={[0, 100]} tick={{ fill: isDarkMode ? '#a1a1aa' : '#52525b', fontSize: 10 }} />
              <Tooltip
                contentStyle={{
                  background: isDarkMode ? '#18181b' : '#fff',
                  border: `1px solid ${isDarkMode ? '#3f3f46' : '#e4e4e7'}`,
                  borderRadius: 8,
                  fontSize: 12,
                  color: isDarkMode ? '#f4f4f5' : '#18181b',
                }}
                labelStyle={{ color: isDarkMode ? '#f4f4f5' : '#18181b', fontWeight: 'bold' }}
                itemStyle={{ color: isDarkMode ? '#d4d4d8' : '#3f3f46' }}
                formatter={(v, _, props) => [`${v}점`, `Risk Score (${props.payload.risk})`]}
              />
              <Bar dataKey="score" radius={[4, 4, 0, 0]}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={riskConfig[d.risk]?.bar || '#22c55e'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

// ─── 메인 App ────────────────────────────────────────────────
export default function App() {
  const [isDarkMode, setIsDarkMode]   = useState(true);
  const [loading, setLoading]         = useState(false);
  const [query, setQuery]             = useState('');
  const [results, setResults]         = useState([]);
  const [summary, setSummary]         = useState(null);
  const [hasResult, setHasResult]     = useState(false);
  const [isApiConnected, setIsApiConnected] = useState(false);
  const [fileName, setFileName]       = useState(null);
  const [dragOver, setDragOver]       = useState(false);
  const fileInputRef = useRef(null);

  const theme = {
    bg:      isDarkMode ? 'bg-[#121212]' : 'bg-zinc-200',
    card:    isDarkMode ? 'bg-[#1e1e1e] border-zinc-800' : 'bg-white border-zinc-200',
    text:    isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    button:  isDarkMode ? 'bg-zinc-100 text-zinc-900 hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700',
    textarea: isDarkMode ? 'bg-[#1e1e1e] text-zinc-100 placeholder:text-zinc-600' : 'bg-white text-zinc-800 placeholder:text-zinc-400',
  };

  const handleFile = useCallback((file) => {
    if (!file) return;
    if (!file.name.endsWith('.sql') && !file.name.endsWith('.txt')) {
      alert('.sql 또는 .txt 파일만 지원합니다');
      return;
    }
    const reader = new FileReader();
    reader.onload = (e) => { setQuery(e.target.result); setFileName(file.name); };
    reader.readAsText(file);
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setDragOver(false);
    handleFile(e.dataTransfer.files[0]);
  }, [handleFile]);

  const clearFile = () => {
    setFileName(null);
    setQuery('');
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ─── API 응답 → 결과 객체 변환 ──────────────────────────────
  const processApiResult = (data, sql, index) => {
    const simulatorMatched = data.simulator_detail?.[0]?.matched_patterns || [];
    const matchedRules = simulatorMatched.length > 0
      ? simulatorMatched.map(p => ({
          id: p.id, name: p.name, risk: p.severity,
          failure_type: p.failure_type, description: p.description, impact: p.impact,
          fix: data.simulator_detail?.[0]?.recommendations?.[0] || null,
        }))
      : matchPatterns(sql);

    const top = matchedRules.length > 0
      ? matchedRules.reduce((prev, curr) => {
          const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };
          return (rank[curr.risk] || 0) > (rank[prev.risk] || 0) ? curr : prev;
        })
      : null;

    const matchedIds = data.matched_pattern_ids || [];
    const scoreFromData = data.risk_score_data
      ? Math.max(0, ...matchedIds.map(id => {
          const d = data.risk_score_data.find(r => r.id === id);
          return d ? d.score : 0;
        }))
      : 0;

    return {
      index, sql, matched: matchedRules, top,
      score: data.risk_score || scoreFromData || { HIGH: 70, MEDIUM: 40, LOW: 10 }[data.risk_level] || 0,
      risk: data.risk_level || 'LOW',
      recommended_ddl: data.recommended_ddl || null,
      reason: data.reason || null,
      estimated_improvement: data.estimated_improvement || null,
    };
  };

  // ─── 진단 실행 ────────────────────────────────────────────
  const runDiagnose = async () => {
    const sqls = splitSQLs(query);
    if (sqls.length === 0) return;

    setLoading(true);
    setHasResult(true);
    setResults([]);
    setSummary(null);

    await new Promise(r => setTimeout(r, 700));

    const analysisResults = [];
    let apiSuccess = false;
    for (let i = 0; i < sqls.length; i++) {
      if (IS_MOCK) {
        analysisResults.push(analyzeSQL(sqls[i], i));
      } else {
        try {
          const { fetchDiagnose } = await import('./api/diagnose');
          const data = await fetchDiagnose(sqls[i]);
          analysisResults.push(processApiResult(data, sqls[i], i));
          apiSuccess = true;
        } catch (e) {
          console.error(`[API ERROR] Query #${i + 1}:`, e.message);
          analysisResults.push(analyzeSQL(sqls[i], i));
        }
      }
    }
    setIsApiConnected(apiSuccess);

    const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };
    analysisResults.sort((a, b) => (rank[b.risk] || 0) - (rank[a.risk] || 0));
    setResults(analysisResults);
    setSummary(calcSummary(analysisResults));
    setLoading(false);
  };

  const sqlCount = splitSQLs(query).length;

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} font-sans transition-colors duration-700`}>

      <div className="fixed top-4 right-4 z-50 flex items-center gap-3">
        {hasResult && (
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full ${
            isApiConnected ? 'bg-green-500/20 text-green-400' : 'bg-blue-500/20 text-blue-400'
          }`}>
            <div className={`w-1.5 h-1.5 rounded-full ${isApiConnected ? 'bg-green-400' : 'bg-blue-400'}`} />
            {isApiConnected ? 'AI 연결됨' : '로컬 분석'}
          </div>
        )}
        <button onClick={() => setIsDarkMode(!isDarkMode)}
          className={`p-2 rounded-full transition-all hover:scale-110 ${
            isDarkMode ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-zinc-300 hover:bg-zinc-400'
          }`}>
          {isDarkMode ? <Sun size={18} /> : <Moon size={18} className="text-zinc-600" />}
        </button>
      </div>

      {/* ── 초기 화면 ── */}
      {!hasResult && (
        <div className="min-h-screen flex flex-col items-center justify-center px-6">
          <div className="w-full max-w-3xl">
            <div className="mb-8 text-center">
              <h1 className="text-3xl font-bold mb-2">AI 쿼리 진단</h1>
              <p className={`text-sm ${theme.subText}`}>
                Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다 · 여러 쿼리는 <code className="font-mono text-xs bg-zinc-800 px-1 rounded">;</code>으로 구분
              </p>
            </div>
            <InputArea
              query={query} setQuery={setQuery} fileName={fileName} sqlCount={sqlCount}
              loading={loading} runDiagnose={runDiagnose} handleDrop={handleDrop}
              handleFile={handleFile} dragOver={dragOver} setDragOver={setDragOver}
              clearFile={clearFile} fileInputRef={fileInputRef}
              isDarkMode={isDarkMode} theme={theme} compact={false}
            />
          </div>
        </div>
      )}

      {/* ── 결과 화면 ── */}
      {hasResult && (
        <div className="max-w-3xl mx-auto px-6 py-10">
          <div className="mb-6">
            <h1 className="text-3xl font-bold mb-2">AI 쿼리 진단</h1>
            <p className={`text-sm ${theme.subText}`}>
              Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다 · 여러 쿼리는 <code className="font-mono text-xs bg-zinc-800 px-1 rounded">;</code>으로 구분
            </p>
          </div>

          <InputArea
            query={query} setQuery={setQuery} fileName={fileName} sqlCount={sqlCount}
            loading={loading} runDiagnose={runDiagnose} handleDrop={handleDrop}
            handleFile={handleFile} dragOver={dragOver} setDragOver={setDragOver}
            clearFile={clearFile} fileInputRef={fileInputRef}
            isDarkMode={isDarkMode} theme={theme} compact={true}
          />

          {loading && (
            <div className={`rounded-2xl border ${theme.card} p-12 flex flex-col items-center gap-4`}>
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-zinc-200 rounded-full animate-spin" />
              <p className={`text-sm ${theme.subText}`}>
                {sqlCount > 1 ? `${sqlCount}개 쿼리 분석 중...` : 'Analyzing...'}
              </p>
            </div>
          )}

          {!loading && results.length > 0 && (
            <div className="flex flex-col gap-4">
              {results.length > 1 && summary && (
                <BatchSummary summary={summary} results={results} isDarkMode={isDarkMode} />
              )}
              {results.length > 1 && (
                <div className="flex items-center gap-2 px-1">
                  <Zap size={12} className="text-zinc-500" />
                  <span className={`text-xs ${theme.subText}`}>
                    HIGH 위험 쿼리가 상단에 정렬됩니다 · 헤더 클릭으로 상세 토글
                  </span>
                </div>
              )}
              {/* 150ms 간격 순차 등장 */}
              {results.map((r, i) => (
                <QueryAccordion
                  key={i}
                  result={r}
                  index={i}
                  isDarkMode={isDarkMode}
                  delay={i * 150}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── 입력 영역 ───────────────────────────────────────────────
function InputArea({
  query, setQuery, fileName, sqlCount, loading, runDiagnose,
  handleDrop, handleFile, dragOver, setDragOver, clearFile,
  fileInputRef, isDarkMode, theme, compact,
}) {
  return (
    <div className="mb-6">
      <div
        onDrop={handleDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => !fileName && fileInputRef.current?.click()}
        className={`mb-3 rounded-xl border-2 border-dashed px-4 py-3 flex items-center gap-3 cursor-pointer transition-all ${
          dragOver ? 'border-zinc-400 bg-zinc-700/30'
            : isDarkMode ? 'border-zinc-700 hover:border-zinc-500 bg-zinc-800/30'
            : 'border-zinc-300 hover:border-zinc-400 bg-zinc-50'
        }`}
      >
        <input ref={fileInputRef} type="file" accept=".sql,.txt" className="hidden"
          onChange={e => handleFile(e.target.files[0])} />
        {fileName ? (
          <>
            <FileText size={15} className="text-green-400 shrink-0" />
            <span className="text-sm text-green-400 font-mono flex-1 truncate">{fileName}</span>
            <button onClick={(e) => { e.stopPropagation(); clearFile(); }}
              className="text-zinc-500 hover:text-zinc-300 transition-colors">
              <X size={14} />
            </button>
          </>
        ) : (
          <>
            <Upload size={15} className={`${theme.subText} shrink-0`} />
            <span className={`text-xs ${theme.subText}`}>.sql 파일 드래그 앤 드롭 또는 클릭하여 업로드</span>
          </>
        )}
      </div>

      <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
        <textarea
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => { if (e.ctrlKey && e.key === 'Enter') runDiagnose(); }}
          placeholder={`분석할 Oracle SQL을 입력하세요...\n\n여러 쿼리는 세미콜론(;)으로 구분:\nSELECT * FROM orders WHERE ROWNUM <= 10;\nSELECT NVL(name,'') FROM users;`}
          className={`w-full ${compact ? 'h-28' : 'h-48'} p-5 outline-none font-mono text-sm resize-none transition-all ${theme.textarea}`}
        />
        <div className={`flex items-center justify-between px-5 py-3 border-t ${
          isDarkMode ? 'border-zinc-800 bg-[#1a1a1a]' : 'border-zinc-200 bg-zinc-50'
        }`}>
          <div className="flex items-center gap-3">
            <span className="text-xs font-mono opacity-40">Oracle → MySQL · Ctrl+Enter</span>
            {sqlCount > 0 && (
              <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                isDarkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-zinc-200 text-zinc-600'
              }`}>
                {sqlCount}개 쿼리
              </span>
            )}
          </div>
          <button
            onClick={runDiagnose}
            disabled={loading || sqlCount === 0}
            className={`flex items-center gap-2 px-5 py-2 rounded-full font-bold text-xs uppercase tracking-widest transition-all hover:scale-105 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed ${theme.button}`}
          >
            <Search size={13} />
            {loading ? 'Analyzing...' : sqlCount > 1 ? `Run Batch (${sqlCount})` : 'Run Diagnose'}
          </button>
        </div>
      </div>
    </div>
  );
}
