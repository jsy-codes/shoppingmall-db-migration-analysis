import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react'; // ← 이 부분이 바뀌었어요 (useMemo 추가)
import {
  Search, Copy, Check, AlertTriangle, Shield, Info,
  Sun, Moon, ChevronDown, ChevronUp, Upload, FileText,
  BarChart2, Zap, X, HelpCircle, BookOpen,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import rules from '../../backend/validation/pattern_rules.json';

// ─── Mock 설정 ─────────────────────────────────────────────────
const IS_MOCK = import.meta.env.VITE_MOCK === 'true';
// ← 이 부분이 바뀌었어요 (앱 시작을 막던 await import 제거 → runDiagnose 안으로 이동)

// ─── 위험도 설정 ───────────────────────────────────────────────
const riskConfig = {
  HIGH:   { label: 'HIGH',   bg: 'bg-red-500/20',    border: 'border-red-500/40',    text: 'text-red-400',    icon: <AlertTriangle size={14} />, bar: '#ef4444' },
  MEDIUM: { label: 'MEDIUM', bg: 'bg-yellow-500/20', border: 'border-yellow-500/40', text: 'text-yellow-400', icon: <Shield size={14} />,        bar: '#eab308' },
  LOW:    { label: 'LOW',    bg: 'bg-green-500/20',  border: 'border-green-500/40',  text: 'text-green-400',  icon: <Info size={14} />,           bar: '#22c55e' },
};

// ─── 패턴 카탈로그 데이터 (P01~P22) ───────────────────────────
const PATTERN_CATALOG = [
  {
    id: 'P01', name: 'Implicit Type Cast', severity: 'MEDIUM', type: 'TYPE_MISMATCH_INDEX_BYPASS',
    oracle: "WHERE member_id = '123'",
    result: '암묵적 형변환 발생으로 인덱스가 사용되지 않을 수 있습니다.',
    reason: '문자열을 숫자와 비교할 때 형변환이 발생하여 인덱스가 무력화됩니다.',
    fix: 'WHERE member_id = 123',
  },
  {
    id: 'P02', name: 'Function on Indexed Column', severity: 'HIGH', type: 'FUNCTION_INDEX_BYPASS',
    oracle: "WHERE UPPER(name) = 'KIM'",
    result: '인덱스 미사용, 풀 테이블 스캔 발생.',
    reason: '인덱스 컬럼에 함수를 적용하면 인덱스를 사용할 수 없습니다.',
    fix: "WHERE name = 'KIM'\n-- 또는 생성 컬럼(generated column) + 인덱스 생성",
  },
  {
    id: 'P03', name: 'ROWNUM Pagination', severity: 'HIGH', type: 'PAGINATION_MIGRATION_ERROR',
    oracle: 'WHERE ROWNUM <= 10',
    result: 'LIMIT을 적용하지 않으면 전체 행이 반환됩니다.',
    reason: 'Oracle의 ROWNUM은 MySQL의 LIMIT과 호환되지 않습니다.',
    fix: 'LIMIT 10',
  },
  {
    id: 'P04', name: 'NVL Function', severity: 'LOW', type: 'FUNCTION_COMPATIBILITY',
    oracle: 'NVL(col, 0)',
    result: '해당 함수를 지원하지 않습니다.',
    reason: 'MySQL은 NVL 대신 IFNULL을 사용합니다.',
    fix: 'IFNULL(col, 0)',
  },
  {
    id: 'P05', name: 'DATE vs DATETIME', severity: 'MEDIUM', type: 'TEMPORAL_TYPE_MISMATCH',
    oracle: 'DATE',
    result: 'DATETIME 또는 TIMESTAMP 타입이 필요합니다.',
    reason: 'Oracle의 DATE는 시간 정보를 포함하지만, MySQL의 DATE는 날짜만 저장합니다.',
    fix: 'MySQL에서는 DATETIME 또는 TIMESTAMP를 사용하세요.',
  },
  {
    id: 'P06', name: 'VARCHAR2 Usage', severity: 'LOW', type: 'STRING_TYPE_COMPATIBILITY',
    oracle: 'VARCHAR2',
    result: 'VARCHAR',
    reason: '길이, 패딩, 비교 동작 방식이 다릅니다.',
    fix: '컬럼 길이와 charset을 명시적으로 확인하세요.',
  },
  {
    id: 'P07', name: 'CHAR Padding', severity: 'LOW', type: 'CHAR_PADDING_COMPARISON',
    oracle: 'CHAR(10)',
    result: '후행 공백(trailing space)이 비교에 영향을 줄 수 있습니다.',
    reason: 'CHAR 타입은 공백으로 채워지므로 비교 시 예상치 못한 결과가 발생할 수 있습니다.',
    fix: 'VARCHAR 또는 TRIM() 사용',
  },
  {
    id: 'P08', name: 'Function Based Index', severity: 'HIGH', type: 'FUNCTION_BASED_INDEX_LOSS',
    oracle: 'CREATE INDEX idx ON t(UPPER(name))',
    result: '함수 기반 인덱스를 직접 지원하지 않습니다.',
    reason: 'MySQL에서 함수 기반 인덱스를 사용하려면 생성 컬럼(generated column)이 필요합니다.',
    fix: '생성 컬럼 + 인덱스 방식으로 대체하세요.',
  },
  {
    id: 'P09', name: 'JOIN Without Index', severity: 'HIGH', type: 'JOIN_FULL_SCAN',
    oracle: 'JOIN without index',
    result: '풀 스캔 / 느린 조인 발생.',
    reason: 'MySQL 옵티마이저는 인덱스 의존도가 높아 인덱스 없는 조인 시 성능이 급격히 저하됩니다.',
    fix: '조인 컬럼에 인덱스를 추가하세요.',
  },
  {
    id: 'P10', name: 'Nested Subquery', severity: 'MEDIUM', type: 'NESTED_QUERY_DEGRADATION',
    oracle: 'Nested subquery',
    result: '실행 속도 저하.',
    reason: 'Oracle과 MySQL의 옵티마이저 동작 방식이 달라 중첩 서브쿼리 성능이 크게 차이납니다.',
    fix: 'JOIN 또는 WITH CTE로 재작성하세요.',
  },
  {
    id: 'P11', name: 'DECODE Function', severity: 'MEDIUM', type: 'FUNCTION_COMPATIBILITY',
    oracle: 'DECODE(col, val, res, default)',
    result: '해당 함수를 지원하지 않습니다.',
    reason: 'DECODE는 Oracle 전용 함수입니다.',
    fix: 'CASE WHEN col = val THEN res ELSE default END',
  },
  {
    id: 'P12', name: 'CONNECT BY Hierarchy', severity: 'HIGH', type: 'HIERARCHY_QUERY_MIGRATION',
    oracle: 'CONNECT BY PRIOR employee_id = manager_id',
    result: 'MySQL에서 문법 오류 발생.',
    reason: '계층 쿼리 문법이 Oracle 전용이라 MySQL에서 지원되지 않습니다.',
    fix: 'WITH RECURSIVE cte AS (...) SELECT ...',
  },
  {
    id: 'P13', name: 'START WITH Hierarchy', severity: 'MEDIUM', type: 'HIERARCHY_QUERY_MIGRATION',
    oracle: 'START WITH manager_id IS NULL',
    result: 'MySQL에서 문법 오류 발생.',
    reason: '계층 쿼리 시작점 지정 문법이 Oracle 전용입니다.',
    fix: '재귀 CTE의 기본 케이스(base case)로 변환',
  },
  {
    id: 'P14', name: 'Oracle Outer Join (+)', severity: 'HIGH', type: 'JOIN_SYNTAX_INCOMPATIBILITY',
    oracle: 'WHERE a.id = b.id(+)',
    result: 'MySQL에서 문법 오류 발생.',
    reason: '(+) 외부 조인 문법은 Oracle 전용입니다.',
    fix: 'LEFT JOIN b ON a.id = b.id',
  },
  {
    id: 'P15', name: 'SYSDATE Usage', severity: 'LOW', type: 'FUNCTION_COMPATIBILITY',
    oracle: 'SYSDATE',
    result: 'MySQL에서 동작 방식이 다릅니다.',
    reason: 'SYSDATE는 Oracle과 MySQL에서 동작 방식이 다릅니다.',
    fix: 'NOW() 또는 CURRENT_TIMESTAMP',
  },
  {
    id: 'P16', name: 'SYSTIMESTAMP Usage', severity: 'MEDIUM', type: 'TIMESTAMP_PRECISION_COMPATIBILITY',
    oracle: 'SYSTIMESTAMP',
    result: '정밀도와 타임존 처리 방식이 다릅니다.',
    reason: '타임스탬프 정밀도와 타임존 처리 방식이 Oracle과 MySQL 간에 차이가 있습니다.',
    fix: 'NOW(6) — 정밀도를 명시적으로 매핑하세요.',
  },
  {
    id: 'P17', name: 'MERGE INTO Statement', severity: 'HIGH', type: 'UPSERT_SYNTAX_MIGRATION',
    oracle: 'MERGE INTO target USING source ON (...)',
    result: 'MySQL에서 해당 문법을 지원하지 않습니다.',
    reason: 'MERGE 문법은 MySQL로 직접 이식할 수 없습니다.',
    fix: 'INSERT ... ON DUPLICATE KEY UPDATE',
  },
  {
    id: 'P18', name: 'MINUS Set Operator', severity: 'MEDIUM', type: 'SET_OPERATOR_INCOMPATIBILITY',
    oracle: 'SELECT ... MINUS SELECT ...',
    result: 'MySQL에서 MINUS 연산자를 지원하지 않습니다.',
    reason: 'MINUS는 Oracle 전용 집합 연산자입니다.',
    fix: 'SELECT ... WHERE id NOT IN (SELECT id ...) -- 또는 ANTI JOIN',
  },
  {
    id: 'P19', name: 'DUAL Table Dependency', severity: 'LOW', type: 'SYSTEM_TABLE_DEPENDENCY',
    oracle: 'SELECT 1 FROM DUAL',
    result: 'MySQL에서는 DUAL이 필요하지 않습니다.',
    reason: 'DUAL 테이블은 Oracle 전용 시스템 테이블로 MySQL에서는 불필요합니다.',
    fix: 'SELECT 1  -- DUAL 제거',
  },
  {
    id: 'P20', name: 'TO_CHAR Date Formatting', severity: 'MEDIUM', type: 'DATE_FORMAT_FUNCTION_MIGRATION',
    oracle: "TO_CHAR(dt, 'YYYY-MM-DD')",
    result: '해당 함수를 지원하지 않습니다.',
    reason: 'Oracle과 MySQL의 날짜 포맷 토큰이 다릅니다.',
    fix: "DATE_FORMAT(dt, '%Y-%m-%d')",
  },
  {
    id: 'P21', name: 'TO_DATE Parsing', severity: 'MEDIUM', type: 'DATE_PARSE_FUNCTION_MIGRATION',
    oracle: "TO_DATE('2024-01-01', 'YYYY-MM-DD')",
    result: '해당 함수를 지원하지 않습니다.',
    reason: '날짜 파싱 포맷 토큰이 Oracle과 MySQL 간에 다릅니다.',
    fix: "STR_TO_DATE('2024-01-01', '%Y-%m-%d')",
  },
  {
    id: 'P22', name: 'TRUNC Date Function', severity: 'MEDIUM', type: 'DATE_TRUNCATION_MIGRATION',
    oracle: 'TRUNC(SYSDATE)',
    result: 'MySQL에서 TRUNC 함수를 지원하지 않습니다.',
    reason: '날짜 절삭 함수의 동작 방식이 Oracle과 MySQL 간에 다릅니다.',
    fix: "DATE(NOW())  -- 또는 DATE_FORMAT(NOW(), '%Y-%m-%d')",
  },
];

// ─── 도움말 데이터 ─────────────────────────────────────────────
const HELP_SECTIONS = [
  {
    icon: '❓',
    title: '이 페이지는 무엇인가요?',
    desc: 'Oracle DB를 MySQL로 이관할 때 발생할 수 있는 위험 패턴을 자동으로 분석하는 AI 진단 도구입니다. SQL을 입력하면 이관 실패 가능성, 위험도 점수, 수정 DDL을 즉시 제공합니다.',
  },
  {
    icon: '✍️',
    title: 'SQL 입력 방법',
    desc: '분석할 Oracle SQL을 직접 입력하거나 .sql 이나 .txt 파일을 업로드하세요. 여러 쿼리를 한 번에 분석하려면 세미콜론(;)으로 구분합니다.',
    example: {
      label: '입력 예시',
      code: `SELECT * FROM orders WHERE ROWNUM <= 10;\nSELECT NVL(customer_name, '미입력') FROM customers;\nSELECT employee_id FROM emp CONNECT BY PRIOR employee_id = manager_id`,
    },
  },
  {
    icon: '📊',
    title: '배치 분석 요약 카드',
    desc: '여러 쿼리를 분석했을 때 전체 결과를 한눈에 보여주는 요약 대시보드입니다.',
    items: [
      { label: '위험도 분포 바', desc: '전체 쿼리 중 HIGH / MEDIUM / LOW 비율을 색상 바로 표시' },
      { label: '평균 Risk Score', desc: '모든 쿼리의 위험도 점수 평균 (0~100)' },
      { label: '최고 Risk Score', desc: '가장 위험한 단일 쿼리의 점수' },
      { label: '쿼리별 차트', desc: '각 쿼리(#01, #02...)의 Risk Score를 바 차트로 비교' },
    ],
  },
  {
    icon: '🔍',
    title: '쿼리 결과 카드',
    desc: '각 쿼리별 분석 결과를 펼쳐서 확인할 수 있습니다. HIGH 위험 쿼리는 자동으로 펼쳐집니다.',
    items: [
      { label: 'SQL 원문',        desc: '입력한 원본 SQL 확인' },
      { label: '문제 설명',       desc: 'AI가 분석한 이관 실패 원인' },
      { label: '감지된 패턴',     desc: '탐지된 이관 위험 패턴 목록 (P01~P22)' },
      { label: '권고 DDL',        desc: 'MySQL로 변환된 수정 쿼리 (복사 가능)' },
      { label: '예상 개선 효과',  desc: '성능 개선 예측치' },
    ],
  },
  {
    icon: '🚦',
    title: '위험도 기준',
    desc: 'Risk Score는 0~100점으로 이관 위험도를 수치화합니다.',
    levels: [
      { risk: 'HIGH',   score: '70점 이상', desc: '이관 시 즉시 오류 발생 가능. 반드시 수정 필요', color: 'text-red-400' },
      { risk: 'MEDIUM', score: '40~69점',   desc: '성능 저하 또는 결과 불일치 발생 가능',          color: 'text-yellow-400' },
      { risk: 'LOW',    score: '40점 미만', desc: '이관 가능하나 최적화 권장',                     color: 'text-green-400' },
    ],
  },
];

// ─── 패턴 카탈로그 모달 (2열 그리드) ─────────────────────────
function PatternCatalogModal({ onClose, isDarkMode }) {
  const [filter, setFilter] = useState('ALL');
  const modalRef = useRef(null);  // ← 이 부분이 바뀌었어요

  const theme = {
    bg:      isDarkMode ? 'bg-[#1a1a1a]' : 'bg-white',
    text:    isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    divider: isDarkMode ? 'border-zinc-800' : 'border-zinc-200',
    card:    isDarkMode ? 'bg-[#242424] border-zinc-700' : 'bg-zinc-50 border-zinc-200',
    code:    isDarkMode ? 'bg-zinc-900 text-zinc-300' : 'bg-zinc-100 text-zinc-700',
    fix:     isDarkMode ? 'bg-zinc-900 text-green-400' : 'bg-green-50 text-green-700',
  };

  useEffect(() => {
    modalRef.current?.focus(); // ← 이 부분이 바뀌었어요 (모달 열릴 때 자동 포커스 이동)

    const handler = (e) => {
      if (e.key === 'Escape') { onClose(); return; }

      // ← 이 부분이 바뀌었어요 (Tab 키로 모달 밖 탈출 방지)
      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last  = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
          if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
        }
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  const filtered = filter === 'ALL'
    ? PATTERN_CATALOG
    : PATTERN_CATALOG.filter(p => p.severity === filter);

  const counts = {
    HIGH:   PATTERN_CATALOG.filter(p => p.severity === 'HIGH').length,
    MEDIUM: PATTERN_CATALOG.filter(p => p.severity === 'MEDIUM').length,
    LOW:    PATTERN_CATALOG.filter(p => p.severity === 'LOW').length,
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div ref={modalRef} tabIndex={-1} className={`relative w-full max-w-5xl max-h-[90vh] rounded-2xl overflow-hidden flex flex-col ${theme.bg} shadow-2xl outline-none`}>{/* ← 이 부분이 바뀌었어요 */}

        {/* 헤더 */}
        <div className={`px-6 py-4 border-b ${theme.divider} shrink-0`}>
          <div className="flex items-center gap-3 mb-3">
            <span className="text-lg">🔎</span>
            <div className="flex-1">
              <h2 className={`text-base font-bold ${theme.text}`}>이관 실패 패턴 카탈로그</h2>
              <p className={`text-xs mt-0.5 ${theme.subText}`}>
                정합성 검증 시뮬레이터 · 총 22개 패턴 (P01~P22) · Oracle → MySQL
              </p>
            </div>
            <button onClick={onClose} className={`p-1.5 rounded-lg transition-colors ${
              isDarkMode ? 'hover:bg-zinc-800 text-zinc-400' : 'hover:bg-zinc-100 text-zinc-500'
            }`}>
              <X size={16} />
            </button>
          </div>

          {/* 필터 탭 */}
          <div className="flex gap-2">
            {[
              { key: 'ALL',    label: `전체 ${PATTERN_CATALOG.length}`, cls: '' },
              { key: 'HIGH',   label: `HIGH ${counts.HIGH}`,            cls: 'text-red-400' },
              { key: 'MEDIUM', label: `MEDIUM ${counts.MEDIUM}`,        cls: 'text-yellow-400' },
              { key: 'LOW',    label: `LOW ${counts.LOW}`,              cls: 'text-green-400' },
            ].map(({ key, label, cls }) => (
              <button key={key} onClick={() => setFilter(key)}
                className={`text-xs px-3 py-1.5 rounded-full font-bold transition-all ${
                  filter === key
                    ? isDarkMode ? 'bg-zinc-100 text-zinc-900' : 'bg-zinc-800 text-white'
                    : `${isDarkMode ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-zinc-100 hover:bg-zinc-200'} ${cls || theme.subText}`
                }`}
              >
                {label}
              </button>
            ))}
            <span className={`ml-auto text-xs self-center ${theme.subText}`}>
              {filtered.length}개 표시
            </span>
          </div>
        </div>

        {/* 2열 그리드 패턴 목록 */}
        <div className="overflow-y-auto flex-1 px-6 py-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((p) => {
              const cfg = riskConfig[p.severity] || riskConfig.LOW;
              return (
                <div key={p.id} className={`rounded-xl border ${theme.card} overflow-hidden`}>
                  <div className={`flex items-center gap-2 px-4 py-3 border-b ${theme.divider} ${cfg.bg}`}>
                    <span className={`text-xs font-mono font-bold ${theme.subText}`}>{p.id}</span>
                    <span className={`text-xs font-bold ${cfg.text}`}>{p.name}</span>
                    <span className={`ml-auto text-xs font-bold px-2 py-0.5 rounded-full border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
                      {p.severity}
                    </span>
                  </div>
                  <div className="px-4 py-3 flex flex-col gap-2">
                    <p className={`text-xs leading-relaxed ${theme.subText}`}>{p.reason}</p>
                    <div className="flex flex-col gap-1.5">
                      <div>
                        <span className={`text-xs font-bold mb-1 block opacity-60 ${theme.subText}`}>Oracle</span>
                        <pre className={`text-xs font-mono px-3 py-2 rounded-lg overflow-x-auto ${theme.code}`}>
                          {p.oracle}
                        </pre>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className={`flex-1 h-px ${isDarkMode ? 'bg-zinc-700' : 'bg-zinc-200'}`} />
                        <span className="text-xs text-green-400 font-bold shrink-0">→ MySQL</span>
                        <div className={`flex-1 h-px ${isDarkMode ? 'bg-zinc-700' : 'bg-zinc-200'}`} />
                      </div>
                      <pre className={`text-xs font-mono px-3 py-2 rounded-lg overflow-x-auto ${theme.fix}`}>
                        {p.fix}
                      </pre>
                    </div>
                    <p className={`text-xs opacity-50 ${theme.subText}`}>⚠ {p.result}</p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 푸터 */}
        <div className={`px-6 py-3 border-t ${theme.divider} shrink-0 flex items-center justify-between`}>
          <span className={`text-xs ${theme.subText}`}>ESC 또는 배경 클릭으로 닫기</span>
          <button onClick={onClose}
            className={`text-xs px-4 py-2 rounded-full font-bold transition-all hover:scale-105 ${
              isDarkMode ? 'bg-zinc-100 text-zinc-900 hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── 도움말 모달 ───────────────────────────────────────────────
function HelpModal({ onClose, isDarkMode }) {
  const modalRef = useRef(null);  // ← 이 부분이 바뀌었어요

  const theme = {
    bg:      isDarkMode ? 'bg-[#1a1a1a]' : 'bg-white',
    card:    isDarkMode ? 'bg-[#242424] border-zinc-700' : 'bg-zinc-50 border-zinc-200',
    text:    isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    divider: isDarkMode ? 'border-zinc-800' : 'border-zinc-200',
    code:    isDarkMode ? 'bg-zinc-900 text-green-400' : 'bg-zinc-100 text-green-700',
    badge:   isDarkMode ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-200 text-zinc-600',
  };

  useEffect(() => {
    modalRef.current?.focus(); // ← 이 부분이 바뀌었어요 (모달 열릴 때 자동 포커스 이동)

    const handler = (e) => {
      if (e.key === 'Escape') { onClose(); return; }

      // ← 이 부분이 바뀌었어요 (Tab 키로 모달 밖 탈출 방지)
      if (e.key === 'Tab' && modalRef.current) {
        const focusable = modalRef.current.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        const first = focusable[0];
        const last  = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) { e.preventDefault(); last.focus(); }
        } else {
          if (document.activeElement === last)  { e.preventDefault(); first.focus(); }
        }
      }
    };

    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div ref={modalRef} tabIndex={-1} className={`relative w-full max-w-2xl max-h-[85vh] rounded-2xl overflow-hidden flex flex-col ${theme.bg} shadow-2xl outline-none`}>{/* ← 이 부분이 바뀌었어요 */}

        <div className={`flex items-center gap-3 px-6 py-5 border-b ${theme.divider} shrink-0`}>
          <BookOpen size={18} className="text-zinc-400" />
          <div>
            <h2 className={`text-base font-bold ${theme.text}`}>사용 가이드</h2>
            <p className={`text-xs mt-0.5 ${theme.subText}`}>Oracle → MySQL 이관 위험도 분석 도구</p>
          </div>
          <button onClick={onClose} className={`ml-auto p-1.5 rounded-lg transition-colors ${
            isDarkMode ? 'hover:bg-zinc-800 text-zinc-400' : 'hover:bg-zinc-100 text-zinc-500'
          }`}>
            <X size={16} />
          </button>
        </div>

        <div className="overflow-y-auto flex-1 px-6 py-5 flex flex-col gap-6">
          {HELP_SECTIONS.map((section, si) => (
            <div key={si}>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-lg">{section.icon}</span>
                <h3 className={`text-sm font-bold ${theme.text}`}>{section.title}</h3>
              </div>
              <p className={`text-xs leading-relaxed mb-3 ${theme.subText}`}>{section.desc}</p>

              {section.example && (
                <div className={`rounded-xl overflow-hidden border ${isDarkMode ? 'border-zinc-700' : 'border-zinc-200'}`}>
                  <div className={`px-3 py-2 text-xs font-bold ${theme.badge} border-b ${theme.divider}`}>
                    {section.example.label}
                  </div>
                  <pre className={`px-4 py-3 text-xs font-mono leading-relaxed overflow-x-auto ${theme.code}`}>
                    {section.example.code}
                  </pre>
                </div>
              )}

              {section.items && (
                <div className="flex flex-col gap-2">
                  {section.items.map((item, ii) => (
                    <div key={ii} className={`flex items-start gap-3 p-3 rounded-xl border ${theme.card}`}>
                      <span className={`text-xs font-bold shrink-0 mt-0.5 ${theme.text}`}>{item.label}</span>
                      <span className={`text-xs ${theme.subText}`}>— {item.desc}</span>
                    </div>
                  ))}
                </div>
              )}

              {section.levels && (
                <div className="flex flex-col gap-2">
                  {section.levels.map((lv, li) => (
                    <div key={li} className={`flex items-start gap-3 p-3 rounded-xl border ${theme.card}`}>
                      <span className={`text-xs font-bold shrink-0 ${lv.color}`}>{lv.risk}</span>
                      <span className={`text-xs font-mono shrink-0 ${theme.subText}`}>{lv.score}</span>
                      <span className={`text-xs ${theme.subText}`}>— {lv.desc}</span>
                    </div>
                  ))}
                </div>
              )}

              {si < HELP_SECTIONS.length - 1 && (
                <div className={`mt-5 border-b ${theme.divider}`} />
              )}
            </div>
          ))}
        </div>

        <div className={`px-6 py-4 border-t ${theme.divider} shrink-0 flex items-center justify-between`}>
          <span className={`text-xs ${theme.subText}`}>Ctrl+Enter 로 빠르게 분석 실행</span>
          <button onClick={onClose}
            className={`text-xs px-4 py-2 rounded-full font-bold transition-all hover:scale-105 ${
              isDarkMode ? 'bg-zinc-100 text-zinc-900 hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── 로컬 패턴 매칭 (API 실패 시 fallback) ────────────────────

// ← 이 부분이 바뀌었어요: 앱 시작 시 딱 한 번만 정규식을 컴파일해서 보관
const COMPILED_RULES = rules.map(rule => ({
  ...rule,
  _regex: rule.type === 'regex' && rule.pattern
    ? new RegExp(rule.pattern, 'i')
    : null,
}));

function matchPatterns(sql) {
  const matched = [];
  for (const rule of COMPILED_RULES) {  // ← 이 부분이 바뀌었어요: rules → COMPILED_RULES
    if (rule._regex) {                  // ← 이 부분이 바뀌었어요: 미리 만든 정규식 재사용
      if (rule._regex.test(sql)) matched.push(rule);
    } else if (rule.type === 'heuristic') {
      if (rule.heuristic === 'implicit_cast' && /\b[A-Z_][A-Z0-9_]*\s*=\s*'\d+'/i.test(sql)) matched.push(rule);
      if (rule.heuristic === 'join_without_index' && /JOIN/i.test(sql) && !/USE INDEX|FORCE INDEX|CREATE INDEX/i.test(sql)) matched.push(rule);
      if (rule.heuristic === 'nested_subquery' && (sql.match(/SELECT/gi) || []).length >= 2) matched.push(rule);
    }
  }
  return matched;
}

function getHighestRisk(matched) {
  if (matched.length === 0) return null;  // ← 이 부분이 바뀌었어요 (빈 배열 방어)
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
  return {
    index, sql, matched, top, score,
    risk: top?.risk || 'LOW',
    recommended_ddl: null, reason: null, estimated_improvement: null,
  };
}

function calcSummary(results) {
  const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 };
  results.forEach(r => counts[r.risk]++);
  const avgScore = results.length ? Math.round(results.reduce((s, r) => s + r.score, 0) / results.length) : 0;
  const maxScore = results.length ? Math.max(...results.map(r => r.score)) : 0;
  return { counts, avgScore, maxScore, total: results.length };
}

function processApiResult(data, sql, index) {
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
}

// ─── 타이핑 애니메이션 ────────────────────────────────────────
function TypewriterText({ text, speed, className = '' }) {
  const [displayed, setDisplayed] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    if (!text) { setDone(true); return; }
    setDisplayed(''); setDone(false);
    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(text.slice(0, i));
      if (i >= text.length) { clearInterval(interval); setDone(true); }
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

// ─── 공통 컴포넌트 ────────────────────────────────────────────
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

// ─── 아코디언 아이템 ──────────────────────────────────────────
function QueryAccordion({ result, index, isDarkMode, delay = 0 }) {
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

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

  const copyDdl = async () => {                          // ← 이 부분이 바뀌었어요 (기다리는 함수로 변경)
    if (!result.recommended_ddl) return;
    try {
      await navigator.clipboard.writeText(result.recommended_ddl); // ← 이 부분이 바뀌었어요 (복사 완료를 기다림)
    } catch {
      // ← 이 부분이 바뀌었어요 (HTTPS가 아닐 때 쓰는 옛날 방식 복사)
      const el = document.createElement('textarea');
      el.value = result.recommended_ddl;
      el.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const shortSQL = result.sql.length > 40 ? result.sql.slice(0, 40) + '…' : result.sql;

  return (
    <div className={`rounded-2xl border ${theme.card} overflow-hidden transition-all duration-500 ${
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
    }`}>
      {/* ← 이 부분이 바뀌었어요: aria-expanded, aria-controls 추가 */}
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls={`query-detail-${result.index}`}
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

      {open && (
        <div id={`query-detail-${result.index}`} className="flex flex-col gap-0">{/* ← 이 부분이 바뀌었어요 */}
          <div className={`px-5 py-4 border-t ${theme.divider}`}>
            <p className={`text-xs font-bold mb-2 ${theme.subText}`}>SQL 원문</p>
            <pre className={`text-xs font-mono p-3 rounded-xl overflow-x-auto ${theme.inner} text-zinc-300`}>
              {result.sql}
            </pre>
          </div>

          {result.reason && (
            <div className={`px-5 py-4 border-t ${theme.divider}`}>
              <p className={`text-xs font-bold mb-2 ${theme.subText}`}>문제 설명</p>
              <p className="text-sm leading-relaxed">
                <TypewriterText text={result.reason} speed={15} />
              </p>
            </div>
          )}

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
                        {m.fix && <p className="text-xs mt-1 text-green-400 font-mono">→ {m.fix}</p>}
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

          <div className={`border-t ${theme.divider} overflow-hidden`}>
            <div className={`flex items-center justify-between px-5 py-3 border-b ${theme.divider}`}>
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold">권고 DDL</span>
                {result.recommended_ddl && <span className="text-xs text-green-400 opacity-60">AI 생성</span>}
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
                ? <TypewriterText text={result.recommended_ddl} speed={10} />
                : (result.matched.length === 0 ? '-- 권고 DDL 없음' : '-- API 연동 후 AI 생성 DDL이 표시됩니다')
              }
            </pre>
          </div>

          {result.estimated_improvement && (
            <div className={`px-5 py-4 border-t ${theme.divider}`}>
              <p className={`text-xs font-bold mb-1 ${theme.subText}`}>예상 개선 효과</p>
              <p className="text-sm leading-relaxed">
                <TypewriterText text={result.estimated_improvement} speed={15} />
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
  useEffect(() => { const t = setTimeout(() => setVisible(true), 50); return () => clearTimeout(t); }, []);

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
          {[
            { label: '평균 Risk Score', val: summary.avgScore },
            { label: '최고 Risk Score', val: summary.maxScore },
            { label: 'HIGH 위험 쿼리',  val: `${summary.counts.HIGH}개`, forceRed: true },
          ].map(({ label, val, forceRed }) => (
            <div key={label} className={`rounded-xl p-4 ${theme.inner}`}>
              <p className={`text-xs mb-1 ${theme.subText}`}>{label}</p>
              <p className={`text-2xl font-bold ${
                forceRed ? 'text-red-400' :
                Number(val) >= 70 ? 'text-red-400' :
                Number(val) >= 40 ? 'text-yellow-400' : 'text-green-400'
              }`}>{val}</p>
            </div>
          ))}
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
                  borderRadius: 8, fontSize: 12,
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

// ─── 메인 App ─────────────────────────────────────────────────
export default function App() {
  const [isDarkMode, setIsDarkMode]   = useState(true);
  const [loading, setLoading]         = useState(false);
  const [totalCount, setTotalCount]   = useState(0);   // 전체 쿼리 수 (스트리밍 진행 표시용)
  const [query, setQuery]             = useState('');
  const [results, setResults]         = useState([]);
  const [summary, setSummary]         = useState(null);
  const [hasResult, setHasResult]     = useState(false);
  const [apiStatus, setApiStatus]     = useState('idle');
  const [fileName, setFileName]       = useState(null);
  const [dragOver, setDragOver]       = useState(false);
  const [showHelp, setShowHelp]       = useState(false);
  const [showCatalog, setShowCatalog] = useState(false);
  const [fileError, setFileError]     = useState(null);  // ← 이 부분이 바뀌었어요 (인라인 에러 상태 추가)
  const fileInputRef = useRef(null);

  // ← 이 부분이 바뀌었어요 (onClose 함수를 한 번만 만들고 재사용)
  const handleCloseHelp    = useCallback(() => setShowHelp(false),    []);
  const handleCloseCatalog = useCallback(() => setShowCatalog(false), []);

  // ← 이 부분이 바뀌었어요 (isDarkMode가 바뀔 때만 theme 재계산)
  const theme = useMemo(() => ({
    bg:       isDarkMode ? 'bg-[#121212]' : 'bg-zinc-200',
    card:     isDarkMode ? 'bg-[#1e1e1e] border-zinc-800' : 'bg-white border-zinc-200',
    text:     isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText:  isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    button:   isDarkMode ? 'bg-zinc-100 text-zinc-900 hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700',
    textarea: isDarkMode ? 'bg-[#1e1e1e] text-zinc-100 placeholder:text-zinc-600' : 'bg-white text-zinc-800 placeholder:text-zinc-400',
  }), [isDarkMode]); // isDarkMode가 바뀔 때만 실행

  const handleFile = useCallback((file) => {
    if (!file) return;
    if (!file.name.endsWith('.sql') && !file.name.endsWith('.txt')) {
      setFileError('.sql 또는 .txt 파일만 지원합니다');  // ← 이 부분이 바뀌었어요 (alert → 인라인 에러)
      return;
    }
    setFileError(null);  // ← 이 부분이 바뀌었어요 (올바른 파일이면 에러 초기화)
    const reader = new FileReader();
    reader.onload = (e) => { setQuery(e.target.result); setFileName(file.name); };
    reader.readAsText(file);
  }, []);

  const clearFile = () => {
    setFileName(null);
    setQuery('');
    setFileError(null);  // ← 이 부분이 바뀌었어요 (파일 제거 시 에러도 함께 초기화)
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  // ─── 진단 실행 (스트리밍) ────────────────────────────────────
  const runDiagnose = async () => {
    const sqls = splitSQLs(query);
    if (sqls.length === 0) return;

    setLoading(true);
    setHasResult(true);
    setResults([]);
    setSummary(null);
    setApiStatus('idle');
    setTotalCount(sqls.length);

    await new Promise(r => setTimeout(r, 700));

    const analysisResults = [];
    let successCount = 0;
    const rank = { HIGH: 3, MEDIUM: 2, LOW: 1 };

    // ← 이 부분이 바뀌었어요 (mock 데이터를 실제로 필요한 시점에 로드)
    let mockData = null;
    if (IS_MOCK) {
      const mod = await import('./data/mock_diagnose_result.json');
      mockData = mod.default;
    }

    for (let i = 0; i < sqls.length; i++) {
      let result;

      if (IS_MOCK) {
        const mockResult = mockData?.results?.[i] ?? mockData?.results?.[0];
        result = mockResult ? processApiResult(mockResult, sqls[i], i) : analyzeSQL(sqls[i], i);
      } else {
        try {
          const { fetchDiagnose } = await import('./api/diagnose');
          const data = await fetchDiagnose(sqls[i]);
          result = processApiResult(data, sqls[i], i);
          successCount++;
        } catch (e) {
          console.error(`[API ERROR] Query #${i + 1}:`, e.message);
          result = analyzeSQL(sqls[i], i);
        }
      }

      analysisResults.push(result);

      // ─── 쿼리 하나 완료마다 즉시 화면 반영 ───────────────────
      // ← 이 부분이 바뀌었어요: 정렬 없이 바로 표시 (스트리밍 효과 유지)
      setResults([...analysisResults]);
      setSummary(calcSummary(analysisResults));
    }

    // ← 이 부분이 바뀌었어요: 모든 쿼리 완료 후 딱 한 번만 정렬
    setResults(prev => [...prev].sort(
      (a, b) => (rank[b.risk] || 0) - (rank[a.risk] || 0)
    ));

    if (IS_MOCK) setApiStatus('mock');
    else if (successCount > 0) setApiStatus('connected');
    else setApiStatus('local');

    setLoading(false);
  };

  const sqlCount = splitSQLs(query).length;

  const statusBadge = {
    connected: { cls: 'bg-green-500/20 text-green-400', dot: 'bg-green-400', label: 'AI 연결됨' },
    local:     { cls: 'bg-blue-500/20 text-blue-400',   dot: 'bg-blue-400',  label: '로컬 분석' },
    mock:      { cls: 'bg-zinc-800 text-zinc-500',       dot: 'bg-zinc-600',  label: '오프라인(mock)' },
  }[apiStatus] ?? null;

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} font-sans transition-colors duration-700`}>

      {/* 모달 */}
      {showHelp    && <HelpModal           onClose={handleCloseHelp}    isDarkMode={isDarkMode} />}  {/* ← 이 부분이 바뀌었어요 */}
      {showCatalog && <PatternCatalogModal onClose={handleCloseCatalog} isDarkMode={isDarkMode} />}  {/* ← 이 부분이 바뀌었어요 */}

      {/* 우측 상단 고정 */}
      <div className="fixed top-4 right-4 z-40 flex items-center gap-3">
        {hasResult && statusBadge && (
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full ${statusBadge.cls}`}>
            <div className={`w-1.5 h-1.5 rounded-full ${statusBadge.dot}`} />
            {statusBadge.label}
          </div>
        )}
        <button
          onClick={() => setShowHelp(true)}
          title="사용 가이드"
          className={`p-2 rounded-full transition-all hover:scale-110 ${
            isDarkMode ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-400' : 'bg-zinc-300 hover:bg-zinc-400 text-zinc-600'
          }`}
        >
          <HelpCircle size={18} />
        </button>
        <button
          onClick={() => setIsDarkMode(!isDarkMode)}
          className={`p-2 rounded-full transition-all hover:scale-110 ${
            isDarkMode ? 'bg-zinc-800 hover:bg-zinc-700' : 'bg-zinc-300 hover:bg-zinc-400'
          }`}
        >
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
                Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다 · 여러 쿼리는{' '}
                <code className="font-mono text-xs bg-zinc-800 px-1 rounded">;</code>으로 구분
              </p>
              <button
                onClick={() => setShowCatalog(true)}
                className={`mt-4 inline-flex items-center gap-2 text-xs px-4 py-2 rounded-full border transition-all hover:scale-105 ${
                  isDarkMode
                    ? 'border-zinc-700 text-zinc-400 hover:border-zinc-500 hover:text-zinc-300'
                    : 'border-zinc-300 text-zinc-500 hover:border-zinc-400 hover:text-zinc-700'
                }`}
              >
                <span>🔎</span>
                이관 실패 패턴 카탈로그 보기
              </button>
            </div>
            <InputArea
              query={query} setQuery={setQuery} fileName={fileName} sqlCount={sqlCount}
              loading={loading} runDiagnose={runDiagnose}
              handleFile={handleFile} dragOver={dragOver} setDragOver={setDragOver}
              clearFile={clearFile} fileInputRef={fileInputRef}
              isDarkMode={isDarkMode} theme={theme} compact={false}
              fileError={fileError}
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
              Oracle SQL을 입력하면 이관 위험도를 즉시 분석합니다 · 여러 쿼리는{' '}
              <code className="font-mono text-xs bg-zinc-800 px-1 rounded">;</code>으로 구분
            </p>
          </div>

          <InputArea
            query={query} setQuery={setQuery} fileName={fileName} sqlCount={sqlCount}
            loading={loading} runDiagnose={runDiagnose}
            handleFile={handleFile} dragOver={dragOver} setDragOver={setDragOver}
            clearFile={clearFile} fileInputRef={fileInputRef}
            isDarkMode={isDarkMode} theme={theme} compact={true}
          />

          {/* 최초 로딩 스피너 — 첫 결과 나오기 전까지만 표시 */}
          {loading && results.length === 0 && (
            <div className={`rounded-2xl border ${theme.card} p-12 flex flex-col items-center gap-4`}>
              <div className="w-8 h-8 border-2 border-zinc-600 border-t-zinc-200 rounded-full animate-spin" />
              <p className={`text-sm ${theme.subText}`}>
                {totalCount > 1 ? `${totalCount}개 쿼리 분석 중...` : 'Analyzing...'}
              </p>
            </div>
          )}

          {/* 결과 목록 — 로딩 중에도 나온 결과 즉시 표시 */}
          {results.length > 0 && (
            <div className="flex flex-col gap-4">
              {results.length > 1 && summary && (
                <BatchSummary summary={summary} results={results} isDarkMode={isDarkMode} />
              )}

              {/* 스트리밍 진행 표시 */}
              {loading && (
                <div className="flex items-center gap-2 px-1">
                  <div className="w-3 h-3 border border-zinc-500 border-t-zinc-300 rounded-full animate-spin shrink-0" />
                  <span className={`text-xs ${theme.subText}`}>
                    {results.length} / {totalCount}개 완료 · 분석 중...
                  </span>
                </div>
              )}

              {!loading && results.length > 1 && (
                <div className="flex items-center gap-2 px-1">
                  <Zap size={12} className="text-zinc-500" />
                  <span className={`text-xs ${theme.subText}`}>
                    HIGH 위험 쿼리가 상단에 정렬됩니다 · 헤더 클릭으로 상세 토글
                  </span>
                </div>
              )}

              {results.map((r, i) => (
                <QueryAccordion key={r.index} result={r} index={i} isDarkMode={isDarkMode} delay={0} />
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
  handleFile, dragOver, setDragOver, clearFile,
  fileInputRef, isDarkMode, theme, compact,
  fileError,  // ← 이 부분이 바뀌었어요 (에러 메시지 prop 추가)
}) {
  return (
    <div className="mb-6">
      <div className={`rounded-2xl border ${theme.card} overflow-hidden`}>
        {/* 파일명 표시 */}
        {fileName && (
          <div className={`flex items-center gap-2 px-4 py-2 border-b ${
            isDarkMode ? 'border-zinc-800 bg-zinc-900/50' : 'border-zinc-200 bg-zinc-50'
          }`}>
            <FileText size={13} className="text-green-400 shrink-0" />
            <span className="text-xs text-green-400 font-mono flex-1 truncate">{fileName}</span>
            <button onClick={clearFile} className="text-zinc-500 hover:text-zinc-300 transition-colors">
              <X size={13} />
            </button>
          </div>
        )}

        {/* textarea + 드래그앤드롭 */}
        <div
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          className={`relative transition-all ${dragOver ? isDarkMode ? 'bg-zinc-800/60' : 'bg-zinc-100' : ''}`}
        >
          <textarea
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.ctrlKey && e.key === 'Enter') runDiagnose(); }}
            placeholder={`분석할 Oracle SQL을 입력...\n\nEx)  SELECT * FROM orders WHERE ROWNUM <= 10;\n     SELECT NVL(name,'') FROM users;`}
            className={`w-full ${compact ? 'h-28' : 'h-48'} p-5 outline-none font-mono text-sm resize-none transition-all ${theme.textarea} bg-transparent`}
          />
          {dragOver && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className={`flex items-center gap-2 text-xs font-bold px-4 py-2 rounded-full ${
                isDarkMode ? 'bg-zinc-700 text-zinc-300' : 'bg-zinc-200 text-zinc-600'
              }`}>
                <Upload size={13} />
                파일을 놓으면 업로드됩니다
              </div>
            </div>
          )}
        </div>

        {/* 하단 바 */}
        <div className={`flex items-center justify-between px-5 py-3 border-t ${
          isDarkMode ? 'border-zinc-800 bg-[#1a1a1a]' : 'border-zinc-200 bg-zinc-50'
        }`}>
          <div className="flex items-center gap-3">
            <button
              onClick={() => fileInputRef.current?.click()}
              className={`flex items-center gap-1.5 text-xs transition-colors ${
                isDarkMode ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-400 hover:text-zinc-600'
              }`}
            >
              <Upload size={14} />
              .sql 파일 또는 .txt 파일 업로드
            </button>
            <input ref={fileInputRef} type="file" accept=".sql,.txt" className="hidden"
              onChange={e => handleFile(e.target.files[0])} />
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
      {/* ← 이 부분이 바뀌었어요: alert() 대신 카드 아래 인라인 에러 메시지 표시 */}
      {fileError && (
        <p className="text-xs text-red-400 mt-2 px-1">{fileError}</p>
      )}
    </div>
  );
}
