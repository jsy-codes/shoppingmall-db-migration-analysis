import React, { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import {
  Search, Copy, Check, AlertTriangle, Shield, Info,
  Sun, Moon, ChevronDown, Upload, FileText,
  BarChart2, Zap, X, HelpCircle, BookOpen, Database, Plus, LogIn, LogOut, Clock, PanelLeft, Trash2,
} from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import rules from '../../backend/validation/pattern_rules.json';

// ─── Mock 설정 ─────────────────────────────────────────────────
const IS_MOCK = import.meta.env.VITE_MOCK === 'true';

// ─── 위험도 순위 (공통 상수) ───────────────────────────────────
const RISK_RANK = { HIGH: 3, MEDIUM: 2, LOW: 1 };

// ─── 위험도 설정 ───────────────────────────────────────────────
const getRiskConfig = (isDarkMode = true) => ({
  HIGH:   { label: 'HIGH',   bg: isDarkMode ? 'bg-red-500/20'     : 'bg-red-200',     border: isDarkMode ? 'border-red-500/40'     : 'border-red-400',     text: isDarkMode ? 'text-red-400'     : 'text-red-700',     icon: <AlertTriangle size={14} />, bar: '#ef4444' },
  MEDIUM: { label: 'MEDIUM', bg: isDarkMode ? 'bg-yellow-500/20'  : 'bg-yellow-200',  border: isDarkMode ? 'border-yellow-500/40'  : 'border-yellow-400',  text: isDarkMode ? 'text-yellow-400'  : 'text-yellow-800',  icon: <Shield size={14} />,        bar: '#eab308' },
  LOW:    { label: 'LOW',    bg: isDarkMode ? 'bg-emerald-500/20' : 'bg-emerald-200', border: isDarkMode ? 'border-emerald-500/40' : 'border-emerald-400', text: isDarkMode ? 'text-emerald-400' : 'text-emerald-700', icon: <Info size={14} />,           bar: '#10b981' },
});

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
      { risk: 'LOW',    score: '40점 미만', desc: '이관 가능하나 최적화 권장',                     color: 'text-emerald-400' },
    ],
  },
];

// ─── 모달 키보드 훅 (Escape 닫기 + Tab focus trap) ────────────
function useModalKeyboard(ref, onClose) {
  useEffect(() => {
    ref.current?.focus();
    const handler = (e) => {
      if (e.key === 'Escape') { onClose(); return; }
      if (e.key === 'Tab' && ref.current) {
        const focusable = ref.current.querySelectorAll(
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
  }, [ref, onClose]);
}

// ─── 패턴 카탈로그 모달 (2열 그리드) ─────────────────────────
function PatternCatalogModal({ onClose, isDarkMode }) {
  const [filter, setFilter] = useState('ALL');
  const modalRef = useRef(null);  
  const theme = {
    bg:      isDarkMode ? 'bg-[#1a1a1a]' : 'bg-white',
    text:    isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    divider: isDarkMode ? 'border-zinc-800' : 'border-zinc-200',
    card:    isDarkMode ? 'bg-[#242424] border-zinc-700' : 'bg-zinc-50 border-zinc-200',
    code:    isDarkMode ? 'bg-zinc-900 text-zinc-300' : 'bg-zinc-100 text-zinc-700',
    fix:     isDarkMode ? 'bg-zinc-900 text-green-400' : 'bg-green-50 text-green-700',
  };

  useModalKeyboard(modalRef, onClose);

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
      <div ref={modalRef} tabIndex={-1} className={`relative w-full max-w-5xl max-h-[90vh] rounded-2xl overflow-hidden flex flex-col ${theme.bg} shadow-2xl outline-none`}>
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
              { key: 'LOW',    label: `LOW ${counts.LOW}`,              cls: 'text-emerald-400' },
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
              const cfg = getRiskConfig(isDarkMode)[p.severity] || getRiskConfig(isDarkMode).LOW;
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
  const modalRef = useRef(null); 

  const theme = {
    bg:      isDarkMode ? 'bg-[#1a1a1a]' : 'bg-white',
    card:    isDarkMode ? 'bg-[#242424] border-zinc-700' : 'bg-zinc-50 border-zinc-200',
    text:    isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    divider: isDarkMode ? 'border-zinc-800' : 'border-zinc-200',
    code:    isDarkMode ? 'bg-zinc-900 text-green-400' : 'bg-zinc-100 text-green-700',
    badge:   isDarkMode ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-200 text-zinc-600',
  };

  useModalKeyboard(modalRef, onClose);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div ref={modalRef} tabIndex={-1} className={`relative w-full max-w-2xl max-h-[85vh] rounded-2xl overflow-hidden flex flex-col ${theme.bg} shadow-2xl outline-none`}>
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

const COMPILED_RULES = rules.map(rule => ({
  ...rule,
  _regex: rule.type === 'regex' && rule.pattern
    ? new RegExp(rule.pattern, 'i')
    : null,
}));

function matchPatterns(sql) {
  const matched = [];
  for (const rule of COMPILED_RULES) { 
    if (rule._regex) {                  
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
  if (matched.length === 0) return null;
  return matched.reduce((prev, curr) => (RISK_RANK[curr.risk] || 0) > (RISK_RANK[prev.risk] || 0) ? curr : prev);
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
    ? matchedRules.reduce((prev, curr) => (RISK_RANK[curr.risk] || 0) > (RISK_RANK[prev.risk] || 0) ? curr : prev)
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
function RiskBadge({ risk, score, isDarkMode = true }) {
  const cfg = getRiskConfig(isDarkMode)[risk] || getRiskConfig(isDarkMode).LOW;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.text} border ${cfg.border}`}>
      {cfg.icon} {cfg.label} {score != null ? `· ${score}` : ''}
    </span>
  );
}

function SummaryBar({ counts, total }) {
  const pct = (n) => total ? Math.round((n / total) * 100) : 0;
  return (
    <div className="flex rounded-full overflow-hidden h-3 w-full gap-px">
      {counts.HIGH   > 0 && <div className="bg-red-500     transition-all duration-700" style={{ width: `${pct(counts.HIGH)}%` }} />}
      {counts.MEDIUM > 0 && <div className="bg-yellow-500  transition-all duration-700" style={{ width: `${pct(counts.MEDIUM)}%` }} />}
      {counts.LOW    > 0 && <div className="bg-emerald-500 transition-all duration-700" style={{ width: `${pct(counts.LOW)}%` }} />}
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
    card:    isDarkMode ? 'bg-[#1a1a1a] border-zinc-800/80' : 'bg-white border-zinc-200',
    subText: isDarkMode ? 'text-zinc-400' : 'text-zinc-500',
    inner:   isDarkMode ? 'bg-zinc-900/60' : 'bg-zinc-50',
    divider: isDarkMode ? 'border-zinc-800/80' : 'border-zinc-200',
  };
  const cfg = getRiskConfig(isDarkMode)[result.risk] || getRiskConfig(isDarkMode).LOW;

  const accentStyle = {
    HIGH:   { bar: 'bg-red-500',    glow: isDarkMode ? 'from-red-500/8 to-transparent'    : 'from-red-100 to-transparent' },
    MEDIUM: { bar: 'bg-yellow-500', glow: isDarkMode ? 'from-yellow-500/8 to-transparent' : 'from-yellow-100 to-transparent' },
    LOW:    { bar: 'bg-emerald-500',glow: isDarkMode ? 'from-emerald-500/5 to-transparent' : 'from-emerald-100 to-transparent' },
  }[result.risk] || { bar: 'bg-zinc-500', glow: 'from-transparent to-transparent' };

  const copyDdl = async () => {   
    if (!result.recommended_ddl) return;
    try {
      await navigator.clipboard.writeText(result.recommended_ddl); 
    } catch {
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
    <div className={`group relative rounded-2xl border ${theme.card} overflow-hidden transition-all duration-500 hover:-translate-y-0.5 hover:shadow-lg ${
      isDarkMode ? 'hover:shadow-black/30' : 'hover:shadow-zinc-200'
    } ${visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'}`}>

      {/* 위험도별 왼쪽 세로 컬러줄 */}
      <div className={`absolute left-0 top-0 bottom-0 w-0.75 ${accentStyle.bar}`} />

      {/* 헤더 버튼 — 위험도 색상 미세 그라디언트 배경 */}
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-controls={`query-detail-${result.index}`}
        className={`w-full flex items-center gap-3 pl-6 pr-5 py-4 text-left transition-all bg-linear-to-r ${accentStyle.glow}`}
      >
        <span className={`text-xs font-mono font-bold ${theme.subText} shrink-0`}>
          #{String(index + 1).padStart(2, '0')}
        </span>
        <RiskBadge risk={result.risk} score={result.score} isDarkMode={isDarkMode} />
        {result.top && (
          <span className={`text-xs font-mono px-2 py-0.5 rounded-md border ${isDarkMode ? 'bg-zinc-800/80 border-zinc-700 text-zinc-400' : 'bg-zinc-100 border-zinc-300 text-zinc-500'}`}>
            {result.top.id}
          </span>
        )}
        <span className={`text-sm font-medium truncate flex-1 ${isDarkMode ? 'text-zinc-100' : 'text-zinc-800'}`}>
          {result.top?.name || '패턴 없음'}
        </span>
        <span className={`text-xs ${theme.subText} font-mono shrink-0 hidden md:block max-w-48 truncate`}>{shortSQL}</span>
        <span className={`shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''} ${cfg.text}`}>
          <ChevronDown size={16} />
        </span>
      </button>

      {open && (
        <div id={`query-detail-${result.index}`} className="flex flex-col">
          {/* SQL 원문 */}
          <div className={`pl-6 pr-5 py-4 border-t ${theme.divider}`}>
            <p className={`text-xs font-semibold uppercase tracking-wider mb-2 ${theme.subText}`}>SQL 원문</p>
            <pre className={`text-xs font-sans p-4 rounded-xl overflow-x-auto leading-relaxed ${
              isDarkMode ? 'bg-zinc-950/80 text-zinc-300 border border-zinc-800' : 'bg-zinc-100 text-zinc-700 border border-zinc-200'
            }`}>
              {result.sql}
            </pre>
          </div>

          {/* 문제 설명 */}
          {result.reason && (
            <div className={`pl-6 pr-5 py-4 border-t ${theme.divider}`}>
              <p className={`text-xs font-semibold uppercase tracking-wider mb-2 ${theme.subText}`}>문제 설명</p>
              <p className={`text-sm leading-relaxed ${isDarkMode ? 'text-zinc-200' : 'text-zinc-700'}`}>
                <TypewriterText text={result.reason} speed={15} />
              </p>
            </div>
          )}

          {/* 감지된 패턴 */}
          {result.matched.length > 0 && (
            <div className={`pl-6 pr-5 py-4 border-t ${theme.divider}`}>
              <p className={`text-xs font-semibold uppercase tracking-wider mb-3 ${theme.subText}`}>
                감지된 패턴 <span className={`ml-1 px-1.5 py-0.5 rounded-full text-xs ${isDarkMode ? 'bg-zinc-800 text-zinc-400' : 'bg-zinc-200 text-zinc-500'}`}>{result.matched.length}</span>
              </p>
              <div className="flex flex-col gap-2">
                {result.matched.map(m => {
                  const mc = getRiskConfig(isDarkMode)[m.risk] || getRiskConfig(isDarkMode).LOW;
                  return (
                    <div key={m.id} className={`flex items-start gap-3 p-3 rounded-xl border ${mc.bg} ${mc.border}`}>
                      <span className={`text-xs font-mono font-bold shrink-0 mt-0.5 ${mc.text}`}>{m.id}</span>
                      <div className="flex-1 min-w-0">
                        <p className={`text-xs font-bold ${mc.text}`}>{m.name}</p>
                        <p className={`text-xs mt-0.5 ${theme.subText}`}>{m.description}</p>
                        {m.fix && <p className="text-xs mt-1.5 text-emerald-400 font-mono">→ {m.fix}</p>}
                      </div>
                      <RiskBadge risk={m.risk} isDarkMode={isDarkMode} />
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 패턴 없음 */}
          {result.matched.length === 0 && (
            <div className={`pl-6 pr-5 py-4 border-t ${theme.divider}`}>
              <div className="flex items-center gap-2 text-emerald-400">
                <div className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                <p className="text-sm font-medium">감지된 위험 패턴 없음</p>
              </div>
            </div>
          )}

          {/* 권고 DDL */}
          <div className={`border-t ${theme.divider} overflow-hidden`}>
            <div className={`flex items-center justify-between pl-6 pr-5 py-3 border-b ${theme.divider}`}>
              <div className="flex items-center gap-2">
                <p className={`text-xs font-semibold uppercase tracking-wider ${theme.subText}`}>권고 DDL</p>
                {result.recommended_ddl && (
                  <span className="text-xs px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">AI 생성</span>
                )}
              </div>
              <button
                onClick={copyDdl}
                disabled={!result.recommended_ddl}
                className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg transition-all disabled:opacity-30 ${
                  isDarkMode
                    ? 'bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700'
                    : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-600 border border-zinc-300'
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
    inner:   isDarkMode ? 'bg-zinc-900/60 border-zinc-800' : 'bg-zinc-50 border-zinc-200',
    divider: isDarkMode ? 'border-zinc-800' : 'border-zinc-200',
  };

  const chartData = results.map((r, i) => ({
    name: `#${String(i + 1).padStart(2, '0')}`,
    score: r.score,
    risk: r.risk,
  }));

  const stats = [
    {
      label: '평균 Risk Score',
      val: summary.avgScore,
      accent: Number(summary.avgScore) >= 70 ? 'text-red-400' : Number(summary.avgScore) >= 40 ? 'text-yellow-400' : 'text-emerald-400',
      bar:    Number(summary.avgScore) >= 70 ? 'bg-red-500'   : Number(summary.avgScore) >= 40 ? 'bg-yellow-500'   : 'bg-emerald-500',
    },
    {
      label: '최고 Risk Score',
      val: summary.maxScore,
      accent: Number(summary.maxScore) >= 70 ? 'text-red-400' : Number(summary.maxScore) >= 40 ? 'text-yellow-400' : 'text-emerald-400',
      bar:    Number(summary.maxScore) >= 70 ? 'bg-red-500'   : Number(summary.maxScore) >= 40 ? 'bg-yellow-500'   : 'bg-emerald-500',
    },
    {
      label: 'HIGH 위험 쿼리',
      val: `${summary.counts.HIGH}개`,
      accent: summary.counts.HIGH > 0 ? 'text-red-400' : 'text-emerald-400',
      bar:    summary.counts.HIGH > 0 ? 'bg-red-500'   : 'bg-emerald-500',
    },
  ];

  return (
    <div className={`rounded-2xl border ${theme.card} overflow-hidden transition-all duration-500 ${
      visible ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-4'
    }`}>
      {/* 헤더 */}
      <div className={`px-6 py-4 border-b ${theme.divider} flex items-center gap-3`}>
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${isDarkMode ? 'bg-zinc-700' : 'bg-zinc-800'}`}>
          <BarChart2 size={13} className="text-white" />
        </div>
        <span className="text-sm font-bold">배치 분석 요약</span>
        <div className={`ml-auto flex items-center gap-1 text-xs ${theme.subText}`}>
          <span>총</span>
          <span className={`font-bold ${isDarkMode ? 'text-zinc-200' : 'text-zinc-700'}`}>{summary.total}개</span>
          <span>쿼리</span>
        </div>
      </div>

      <div className="p-6 flex flex-col gap-6">
        {/* 스탯 카드 3개 */}
        <div className="grid grid-cols-3 gap-3">
          {stats.map(({ label, val, accent, bar }) => (
            <div key={label} className={`rounded-xl border ${theme.inner} p-4 flex flex-col gap-2 relative overflow-hidden`}>
              <div className={`absolute top-0 left-0 right-0 h-0.75 ${bar}`} />
              <p className={`text-xs ${theme.subText}`}>{label}</p>
              <p className={`text-3xl font-bold tracking-tight ${accent}`}>{val}</p>
            </div>
          ))}
        </div>

        {/* 위험도 분포 바 */}
        <div>
          <div className="flex justify-between items-center mb-2.5">
            <span className={`text-xs font-semibold ${theme.subText}`}>위험도 분포</span>
            <div className="flex gap-3">
              <span className="text-xs text-red-400 font-bold">HIGH {summary.counts.HIGH}</span>
              <span className="text-xs text-yellow-400 font-bold">MED {summary.counts.MEDIUM}</span>
              <span className="text-xs text-emerald-400 font-bold">LOW {summary.counts.LOW}</span>
            </div>
          </div>
          <SummaryBar counts={summary.counts} total={summary.total} />
        </div>

        {/* 쿼리별 점수 차트 */}
        {results.length > 1 && (
          <ResponsiveContainer width="100%" height={130}>
            <BarChart data={chartData} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#27272a' : '#e4e4e7'} vertical={false} />
              <XAxis dataKey="name" tick={{ fill: isDarkMode ? '#71717a' : '#a1a1aa', fontSize: 10 }} axisLine={false} tickLine={false} />
              <YAxis domain={[0, 100]} tick={{ fill: isDarkMode ? '#71717a' : '#a1a1aa', fontSize: 10 }} axisLine={false} tickLine={false} />
              <Tooltip
                contentStyle={{
                  background: isDarkMode ? '#18181b' : '#fff',
                  border: `1px solid ${isDarkMode ? '#3f3f46' : '#e4e4e7'}`,
                  borderRadius: 10, fontSize: 12,
                  color: isDarkMode ? '#f4f4f5' : '#18181b',
                }}
                labelStyle={{ color: isDarkMode ? '#f4f4f5' : '#18181b', fontWeight: 700, marginBottom: 2 }}
                itemStyle={{ color: isDarkMode ? '#d4d4d8' : '#3f3f46' }}
                formatter={(v, _, props) => [`${v}점`, `Risk Score (${props.payload.risk})`]}
                cursor={{ fill: isDarkMode ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.03)' }}
              />
              <Bar dataKey="score" radius={[5, 5, 0, 0]} maxBarSize={40}>
                {chartData.map((d, i) => (
                  <Cell key={i} fill={getRiskConfig(isDarkMode)[d.risk]?.bar || '#10b981'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}

// ─── 예제 쿼리 ────────────────────────────────────────────────
const EXAMPLE_QUERIES = [
  { label: 'ROWNUM 페이징',  sql: 'SELECT * FROM orders WHERE ROWNUM <= 10' },
  { label: 'NVL 널 처리',    sql: "SELECT NVL(username, '익명') FROM users" },
  { label: 'SYSDATE 날짜',   sql: 'SELECT SYSDATE FROM DUAL' },
  { label: 'SEQUENCE 채번',  sql: 'SELECT seq_order.NEXTVAL FROM DUAL' },
  { label: 'DECODE 분기',    sql: "SELECT DECODE(status, 'Y', '활성', '비활성') FROM members" },
  { label: '묵시적 형변환',  sql: "SELECT * FROM products WHERE product_id = '100'" },
];

// ─── 사이드바 ─────────────────────────────────────────────────
function Sidebar({ isOpen, onToggle, historyItems, user, isDarkMode, onSelectHistory, onNewAnalysis, onLogout, onDeleteHistory }) {
  const [searchQuery, setSearchQuery] = useState('');
  const searchInputRef = useRef(null);

  const filtered = searchQuery.trim()
    ? historyItems.filter(item => item.query_sql?.toLowerCase().includes(searchQuery.toLowerCase()))
    : historyItems;

  const handleSearchClick = () => {
    if (!isOpen) {
      onToggle();
      setTimeout(() => searchInputRef.current?.focus(), 320);
    } else {
      searchInputRef.current?.focus();
    }
  };

  const t = {
    bg:        isDarkMode ? 'bg-[#111111]' : 'bg-zinc-100',
    border:    isDarkMode ? 'border-zinc-800' : 'border-zinc-200',
    text:      isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText:   isDarkMode ? 'text-zinc-500' : 'text-zinc-400',
    iconBtn:   isDarkMode ? 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200' : 'text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700',
    itemHover: isDarkMode ? 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200' : 'text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700',
    inputBg:   isDarkMode ? 'bg-zinc-800/60 border-zinc-700 text-zinc-300 placeholder:text-zinc-600' : 'bg-zinc-200/60 border-zinc-300 text-zinc-600 placeholder:text-zinc-400',
  };

  const miniVisible = !isOpen;

  return (
    <div className={`fixed top-0 left-0 h-full z-30 border-r transition-all duration-300 overflow-hidden ${t.bg} ${t.border} ${isOpen ? 'w-64' : 'w-12'}`}>

      {/* ── 미니 레이어 (아이콘만) ── */}
      <div className={`absolute inset-0 w-12 flex flex-col items-center py-3 gap-1 transition-opacity duration-150 ${miniVisible ? 'opacity-100 delay-150' : 'opacity-0 pointer-events-none'}`}>
        <button onClick={onToggle} className={`p-1.5 rounded-lg transition-all ${t.iconBtn}`}>
          <PanelLeft size={18} />
        </button>
        <button onClick={onNewAnalysis} title="새 분석" className={`p-2 rounded-lg transition-all ${t.iconBtn}`}>
          <Plus size={16} />
        </button>
        <button onClick={handleSearchClick} title="기록 검색" className={`p-2 rounded-lg transition-all ${t.iconBtn}`}>
          <Search size={16} />
        </button>
        <div className="flex-1" />
        {user ? (
          <button onClick={onLogout} title="로그아웃" className={`p-1.5 rounded-lg transition-all ${t.iconBtn}`}>
            <LogOut size={15} />
          </button>
        ) : (
          <a href="https://shoppingmall-db-migration-analysis.onrender.com/login" title="Google로 로그인"
            className={`p-2 rounded-lg transition-all flex items-center justify-center ${t.iconBtn}`}>
            <LogIn size={16} />
          </a>
        )}
      </div>

      {/* ── 풀 레이어 (텍스트 포함) ── */}
      <div className={`absolute inset-0 w-64 flex flex-col transition-opacity duration-150 ${isOpen ? 'opacity-100 delay-150' : 'opacity-0 pointer-events-none'}`}>

        {/* 헤더 */}
        <div className="flex items-center gap-2.5 px-3 py-3 shrink-0">
          <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${isDarkMode ? 'bg-zinc-700' : 'bg-zinc-800'}`}>
            <Database size={15} className="text-white" />
          </div>
          <span className={`text-sm font-bold flex-1 whitespace-nowrap ${t.text}`}>AI 쿼리 진단</span>
          <button onClick={onToggle} className={`p-1.5 rounded-lg transition-all ${t.iconBtn}`}>
            <PanelLeft size={16} />
          </button>
        </div>

        {/* 액션 버튼 */}
        <div className="px-2 pb-2 flex flex-col gap-1.5 shrink-0">
          <button onClick={onNewAnalysis} className={`w-full flex items-center gap-2 px-3 py-2 rounded-lg text-xs transition-all border ${
            isDarkMode ? 'border-zinc-700 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200' : 'border-zinc-300 text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700'
          }`}>
            <Plus size={13} /> 새 분석
          </button>
          <div className={`flex items-center gap-2 px-3 py-2 rounded-lg border text-xs ${t.inputBg}`}>
            <Search size={13} className="shrink-0 opacity-60" />
            <input
              ref={searchInputRef}
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="기록 검색..."
              className="flex-1 bg-transparent outline-none text-xs"
            />
            {searchQuery && (
              <button onClick={() => setSearchQuery('')} className="opacity-60 hover:opacity-100">
                <X size={11} />
              </button>
            )}
          </div>
        </div>

        <div className={`mx-3 border-t ${t.border} mb-1 shrink-0`} />

        {/* 히스토리 목록 */}
        <div className="flex-1 overflow-y-auto px-2 scrollbar-none">
          <p className={`px-2 py-1 text-xs font-semibold uppercase tracking-wider ${t.subText}`}>최근 분석</p>
          {filtered.length === 0 ? (
            <p className={`px-3 py-3 text-xs ${t.subText}`}>
              {searchQuery ? '검색 결과가 없습니다' : '분석 후 기록이 여기에 표시됩니다'}
            </p>
          ) : (
            filtered.map((item, i) => (
              <div key={item.id || i}
                className={`group relative flex items-center rounded-lg mb-0.5 transition-all ${t.itemHover}`}>
                <button onClick={() => onSelectHistory(item)}
                  className="flex-1 text-left px-3 py-2.5 text-xs min-w-0">
                  <p className="truncate font-medium">{item.query_sql?.slice(0, 35) ?? '—'}</p>
                  <p className={`text-xs mt-0.5 flex items-center gap-1 ${t.subText}`}>
                    <Clock size={10} /> {item.created_at?.slice(0, 10) ?? ''}
                  </p>
                </button>
                <button
                  onClick={(e) => { e.stopPropagation(); onDeleteHistory(item.id); }}
                  className={`opacity-0 group-hover:opacity-100 p-1.5 mr-1 rounded transition-all shrink-0 hover:text-red-400 ${t.subText}`}>
                  <Trash2 size={12} />
                </button>
              </div>
            ))
          )}
        </div>

        {/* 하단 유저 영역 */}
        <div className={`py-3 border-t ${t.border} shrink-0 px-3`}>
          {user ? (
            <div className="flex items-center gap-2 w-full">
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0 ${isDarkMode ? 'bg-zinc-600' : 'bg-zinc-700'}`}>
                {user.email?.[0]?.toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <p className={`text-xs font-medium truncate ${t.text}`}>{user.email}</p>
                <p className={`text-xs ${t.subText}`}>로그인됨</p>
              </div>
              <button onClick={onLogout} title="로그아웃" className={`p-1.5 rounded-lg transition-all shrink-0 ${t.iconBtn}`}>
                <LogOut size={14} />
              </button>
            </div>
          ) : (
            <a href="https://shoppingmall-db-migration-analysis.onrender.com/login"
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all w-full ${t.iconBtn}`}>
              <LogIn size={13} /> Google로 로그인
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── 메인 App ─────────────────────────────────────────────────
export default function App() {
  const [isDarkMode, setIsDarkMode]   = useState(true);
  const [loading, setLoading]         = useState(false);
  const [totalCount, setTotalCount]   = useState(0);
  const [query, setQuery]             = useState('');
  const [results, setResults]         = useState([]);
  const [summary, setSummary]         = useState(null);
  const [hasResult, setHasResult]     = useState(false);
  const [apiStatus, setApiStatus]     = useState('idle');
  const [fileName, setFileName]       = useState(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [historyItems, setHistoryItems] = useState([]);
  const [user, setUser]               = useState(null);
  const [dragOver, setDragOver]       = useState(false);
  const [showHelp, setShowHelp]       = useState(false);
  const [showCatalog, setShowCatalog] = useState(false);
  const [fileError, setFileError]     = useState(null);  
  const fileInputRef = useRef(null);

  const handleCloseHelp    = useCallback(() => setShowHelp(false),    []);
  const handleCloseCatalog = useCallback(() => setShowCatalog(false), []);

  // ─── 히스토리 갱신 함수 (초기 로딩 + 진단 완료 후 재사용) ───
  const refreshHistory = useCallback(async () => {
    try {
      const res = await fetch('https://shoppingmall-db-migration-analysis.onrender.com/history?limit=30&offset=0', { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setHistoryItems(data);
      }
    } catch { /* 백엔드 오프라인 시 무시 */ }
  }, []);

  // ─── 배치 결과 전체를 하나의 세션으로 저장 ─────────────────
const res = await fetch(
  "https://shoppingmall-db-migration-analysis.onrender.com/session",
  {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      query_sql: originalQuery,
      results: resultsWithSql
    }),
  }
);

const data = await res.json();
console.log("SESSION RESPONSE:", data);

  // ─── 히스토리 + 유저 로딩 ───────────────────────────────────
  useEffect(() => {
    const loadAll = async () => {
      try {
        const [meRes, histRes] = await Promise.all([
          fetch('https://shoppingmall-db-migration-analysis.onrender.com/me', { credentials: 'include' }),
          fetch('https://shoppingmall-db-migration-analysis.onrender.com/history?limit=30&offset=0', { credentials: 'include' }),
        ]);
        if (meRes.ok) {
          const meData = await meRes.json();
          setUser(meData.email ? { email: meData.email } : null);
        }
        if (histRes.ok) {
          const histData = await histRes.json();
          setHistoryItems(histData);
        }
      } catch { /* 백엔드 오프라인 시 무시 */ }
    };
    loadAll();
  }, []);

  // ─── 브라우저 뒤로가기 지원 ─────────────────────────────────
  useEffect(() => {
    const onPop = () => {
      setHasResult(false);
      setResults([]);
      setSummary(null);
      setApiStatus('idle');
    };
    window.addEventListener('popstate', onPop);
    return () => window.removeEventListener('popstate', onPop);
  }, []);

  const handleNewAnalysis = useCallback(() => {
    window.history.pushState(null, '');
    setHasResult(false);
    setResults([]);
    setSummary(null);
    setQuery('');
    setApiStatus('idle');
  }, []);

  const handleDeleteHistory = useCallback(async (id) => {
    try {
      await fetch(`https://shoppingmall-db-migration-analysis.onrender.com/history/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      setHistoryItems(prev => prev.filter(item => item.id !== id));
    } catch { /* 무시 */ }
  }, []);

  const handleLogout = useCallback(async () => {
    try {
      await fetch('https://shoppingmall-db-migration-analysis.onrender.com/logout', { credentials: 'include' });
    } catch { /* 무시 */ }
    setUser(null);
    setHistoryItems([]);
  }, []);

  const handleSelectHistory = useCallback((item) => {
    try {
      const aiResponse = typeof item.ai_response === 'string'
        ? JSON.parse(item.ai_response)
        : item.ai_response;

      // 새 배치 형식(배열): saveSession이 저장한 처리 완료된 결과 → 직접 사용
      // 구 형식(단일 객체): 원시 API 응답 → processApiResult로 변환
      const loaded = Array.isArray(aiResponse)
        ? aiResponse.map((res, i) => ({
            ...res,
            index: i,
            sql: res.sql || res.query_sql || item.query_sql,
          }))
        : [processApiResult(aiResponse, item.query_sql, 0)];

      setResults(loaded);
      setSummary(calcSummary(loaded));
      setQuery(item.query_sql);
      window.history.pushState({ view: 'result' }, '');
      setHasResult(true);
      setApiStatus('connected');
    } catch (e) {
      console.error('히스토리 로드 실패:', e);
    }
  }, []);

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
      setFileError('.sql 또는 .txt 파일만 지원합니다');  
      return;
    }
    setFileError(null); 
    const reader = new FileReader();
    reader.onload = (e) => { setQuery(e.target.result); setFileName(file.name); };
    reader.onerror = () => setFileError('파일을 읽을 수 없습니다. 다시 시도해주세요.');
    reader.readAsText(file);
  }, []);

  const clearFile = useCallback(() => {
    setFileName(null);
    setQuery('');
    setFileError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }, []);

  // ─── 진단 실행 (스트리밍) ────────────────────────────────────
  const runDiagnose = async () => {
    if (sqls.length === 0) return;
    if (sqls.length > 50) {
      alert('최대 50개 쿼리까지 분석 가능합니다. 쿼리 수를 줄여주세요.');
      return;
    }

    window.history.pushState({ view: 'result' }, '');
    setLoading(true);
    setHasResult(true);
    setResults([]);
    setSummary(null);
    setApiStatus('idle');
    setTotalCount(sqls.length);

    await new Promise(r => setTimeout(r, 700));

    const analysisResults = [];
    let successCount = 0;

    let mockData = null;
    if (IS_MOCK) {
      const mod = await import('./data/mock_diagnose_result.json');
      mockData = mod.default;
    }

    const { fetchDiagnose } = IS_MOCK ? {} : await import('./api/diagnose');

    for (let i = 0; i < sqls.length; i++) {
      let result;

      if (IS_MOCK) {
        const mockResult = mockData?.results?.[i] ?? mockData?.results?.[0];
        result = mockResult ? processApiResult(mockResult, sqls[i], i) : analyzeSQL(sqls[i], i);
      } else {
        try {
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
      setResults([...analysisResults]);
      setSummary(calcSummary(analysisResults));
    }

    setResults(prev => [...prev].sort(
      (a, b) => (RISK_RANK[b.risk] || 0) - (RISK_RANK[a.risk] || 0)
    ));

    if (IS_MOCK) setApiStatus('mock');
    else if (successCount > 0) setApiStatus('connected');
    else setApiStatus('local');

    setLoading(false);

    if (!IS_MOCK && successCount > 0) saveSession(analysisResults, query, sqls);
  };

  const sqls = useMemo(() => splitSQLs(query), [query]);
  const sqlCount = sqls.length;

  const statusBadge = {
    connected: { cls: 'bg-green-500/20 text-green-400', dot: 'bg-green-400', label: 'AI 연결됨' },
    local:     { cls: 'bg-blue-500/20 text-blue-400',   dot: 'bg-blue-400',  label: '로컬 분석' },
    mock:      { cls: 'bg-zinc-800 text-zinc-500',       dot: 'bg-zinc-600',  label: '오프라인(mock)' },
  }[apiStatus] ?? null;

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} font-sans transition-colors duration-700 ${isDarkMode ? 'bg-grid-dark' : 'bg-grid-light'}`}>

      {/* 모달 */}
      {showHelp    && <HelpModal           onClose={handleCloseHelp}    isDarkMode={isDarkMode} />}
      {showCatalog && <PatternCatalogModal onClose={handleCloseCatalog} isDarkMode={isDarkMode} />}

      {/* 사이드바 */}
      <Sidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(v => !v)}
        historyItems={historyItems}
        user={user}
        isDarkMode={isDarkMode}
        onSelectHistory={handleSelectHistory}
        onNewAnalysis={handleNewAnalysis}
        onLogout={handleLogout}
        onDeleteHistory={handleDeleteHistory}
      />

      {/* 컨텐츠 영역 — 사이드바 너비만큼 밀기 */}
      <div className={`transition-all duration-300 ${sidebarOpen ? 'ml-64' : 'ml-12'}`}>

      {/* 우측 상단 고정 */}
      <div className="fixed top-4 right-4 z-40 flex items-center gap-2">
        {hasResult && statusBadge && (
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border font-medium ${statusBadge.cls} ${isDarkMode ? 'border-zinc-700' : 'border-zinc-300'}`}>
            <div className={`w-1.5 h-1.5 rounded-full animate-pulse ${statusBadge.dot}`} />
            {statusBadge.label}
          </div>
        )}
        <div className={`flex items-center gap-1 p-1 rounded-xl border ${isDarkMode ? 'bg-zinc-900/80 border-zinc-800' : 'bg-white/80 border-zinc-200'} backdrop-blur-sm`}>
          <button
            onClick={() => setShowHelp(true)}
            title="사용 가이드"
            className={`p-1.5 rounded-lg transition-all hover:scale-105 ${
              isDarkMode ? 'hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200' : 'hover:bg-zinc-100 text-zinc-500 hover:text-zinc-700'
            }`}
          >
            <HelpCircle size={16} />
          </button>
          <div className={`w-px h-4 ${isDarkMode ? 'bg-zinc-800' : 'bg-zinc-200'}`} />
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className={`p-1.5 rounded-lg transition-all hover:scale-105 ${
              isDarkMode ? 'hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200' : 'hover:bg-zinc-100 text-zinc-500 hover:text-zinc-700'
            }`}
          >
            {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>

      {/* ── 초기 화면 ── */}
      {!hasResult && (
        <div className="min-h-screen flex flex-col items-center justify-center px-6">
          <div className="relative z-10 w-full max-w-3xl">

            {/* 타이틀 영역 */}
            <div className="mb-7 text-center">
              <h1 className={`text-4xl font-bold tracking-tight mb-2.5 bg-linear-to-b bg-clip-text text-transparent ${
                isDarkMode
                  ? 'from-white via-zinc-100 to-zinc-500'
                  : 'from-zinc-900 via-zinc-700 to-zinc-500'
              }`}>
                AI 쿼리 진단
              </h1>
              <p className={`text-sm ${theme.subText}`}>
                Oracle SQL의 MySQL 이관 위험도를 즉시 분석합니다
              </p>
            </div>

            {/* 입력 영역 */}
            <InputArea
              query={query} setQuery={setQuery} fileName={fileName} sqlCount={sqlCount}
              loading={loading} runDiagnose={runDiagnose}
              handleFile={handleFile} dragOver={dragOver} setDragOver={setDragOver}
              clearFile={clearFile} fileInputRef={fileInputRef}
              isDarkMode={isDarkMode} theme={theme} compact={false}
              fileError={fileError}
            />

            {/* 예제 쿼리 — 가로 스크롤 한 줄 */}
            <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-1 scrollbar-none">
              <span className={`text-xs shrink-0 ${theme.subText}`}>예제:</span>
              {EXAMPLE_QUERIES.map(({ label, sql }) => (
                <button
                  key={label}
                  onClick={() => setQuery(sql)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-all hover:scale-105 active:scale-95 shrink-0 ${
                    isDarkMode
                      ? 'bg-zinc-900 border-zinc-800 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-200 hover:border-zinc-600'
                      : 'bg-zinc-50 border-zinc-200 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 hover:border-zinc-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* 카탈로그 링크 — 예제 아래 */}
            <div className="mt-4 flex justify-center">
              <button
                onClick={() => setShowCatalog(true)}
                className={`inline-flex items-center gap-2 text-xs px-4 py-2 rounded-full border transition-all hover:scale-105 ${
                  isDarkMode
                    ? 'border-zinc-800 text-zinc-500 hover:border-zinc-600 hover:text-zinc-300 hover:bg-zinc-800/50'
                    : 'border-zinc-200 text-zinc-400 hover:border-zinc-300 hover:text-zinc-600 hover:bg-zinc-100'
                }`}
              >
                <Search size={11} />
                이관 실패 패턴 카탈로그 보기
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── 결과 화면 ── */}
      {hasResult && (
        <div className="max-w-3xl mx-auto px-6 py-10">
          <div className="mb-6">
            <h1 className={`text-xl font-bold bg-linear-to-r bg-clip-text text-transparent ${
              isDarkMode ? 'from-white to-zinc-400' : 'from-zinc-900 to-zinc-500'
            }`}>AI 쿼리 진단</h1>
            <p className={`text-xs ${theme.subText}`}>Oracle → MySQL 이관 위험도 분석</p>
          </div>

          <InputArea
            query={query} setQuery={setQuery} fileName={fileName} sqlCount={sqlCount}
            loading={loading} runDiagnose={runDiagnose}
            handleFile={handleFile} dragOver={dragOver} setDragOver={setDragOver}
            clearFile={clearFile} fileInputRef={fileInputRef}
            isDarkMode={isDarkMode} theme={theme} compact={true}
          />

          {/* 최초 로딩 — 첫 결과 나오기 전까지만 표시 */}
          {loading && results.length === 0 && (
            <div className={`rounded-2xl border ${theme.card} p-12 flex flex-col items-center gap-6`}>
              <div className="flex items-end gap-1.5">
                <span className={`dot-1 w-2.5 h-2.5 rounded-full ${isDarkMode ? 'bg-zinc-400' : 'bg-zinc-600'}`} />
                <span className={`dot-2 w-2.5 h-2.5 rounded-full ${isDarkMode ? 'bg-zinc-400' : 'bg-zinc-600'}`} />
                <span className={`dot-3 w-2.5 h-2.5 rounded-full ${isDarkMode ? 'bg-zinc-400' : 'bg-zinc-600'}`} />
              </div>
              <p className={`text-sm font-medium ${theme.subText}`}>
                {totalCount > 1 ? `${totalCount}개 쿼리 분석 중...` : '쿼리 분석 중...'}
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
                <div className="flex items-center gap-3 px-1">
                  <div className="flex items-end gap-1">
                    <span className={`dot-1 w-1.5 h-1.5 rounded-full ${isDarkMode ? 'bg-zinc-400' : 'bg-zinc-600'}`} />
                    <span className={`dot-2 w-1.5 h-1.5 rounded-full ${isDarkMode ? 'bg-zinc-400' : 'bg-zinc-600'}`} />
                    <span className={`dot-3 w-1.5 h-1.5 rounded-full ${isDarkMode ? 'bg-zinc-400' : 'bg-zinc-600'}`} />
                  </div>
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
      </div> {/* 컨텐츠 래퍼 끝 */}
    </div>
  );
}

// ─── 입력 영역 ───────────────────────────────────────────────
function InputArea({
  query, setQuery, fileName, sqlCount, loading, runDiagnose,
  handleFile, dragOver, setDragOver, clearFile,
  fileInputRef, isDarkMode, theme, compact,
  fileError, 
}) {
  return (
    <div className="mb-6">
      {/* 포커스 시 보라 글로우가 생기는 입력 패널 */}
      <div className={`input-panel rounded-2xl border overflow-hidden transition-all duration-300 ${theme.card}`}>

        {/* 파일명 표시 */}
        {fileName && (
          <div className={`flex items-center gap-2 px-4 py-2 border-b ${
            isDarkMode ? 'border-zinc-800 bg-zinc-800/40' : 'border-zinc-200 bg-zinc-100'
          }`}>
            <FileText size={13} className={`shrink-0 ${isDarkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
            <span className={`text-xs font-mono flex-1 truncate ${isDarkMode ? 'text-zinc-300' : 'text-zinc-600'}`}>{fileName}</span>
            <button onClick={clearFile} className={`transition-colors ${isDarkMode ? 'text-zinc-500 hover:text-zinc-200' : 'text-zinc-400 hover:text-zinc-600'}`}>
              <X size={13} />
            </button>
          </div>
        )}

        {/* textarea + 드래그앤드롭 */}
        <div
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          className={`relative transition-all ${dragOver ? isDarkMode ? 'bg-zinc-800/40' : 'bg-zinc-100/60' : ''}`}
        >
          <textarea
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => { if (e.ctrlKey && e.key === 'Enter') runDiagnose(); }}
            placeholder={`분석할 Oracle SQL을 입력하세요...\n\n예)  SELECT * FROM orders WHERE ROWNUM <= 10;\n     SELECT NVL(name,'') FROM users;`}
            maxLength={50000}
            className={`w-full ${compact ? 'h-28' : 'h-52'} px-5 pt-5 pb-3 outline-none font-sans text-sm leading-relaxed resize-none transition-all ${theme.textarea} bg-transparent`}
          />
          {dragOver && (
            <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
              <div className={`flex items-center gap-2 text-xs font-semibold px-4 py-2.5 rounded-full border backdrop-blur-sm ${isDarkMode ? 'bg-zinc-800/70 border-zinc-600 text-zinc-200' : 'bg-white/80 border-zinc-300 text-zinc-700'}`}>
                <Upload size={13} />
                파일을 놓으면 업로드됩니다
              </div>
            </div>
          )}
        </div>

        {/* 하단 바 */}
        <div className={`flex items-center justify-between px-4 py-2.5 border-t ${
          isDarkMode ? 'border-zinc-800 bg-zinc-900/60' : 'border-zinc-200 bg-zinc-50/80'
        }`}>
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => fileInputRef.current?.click()}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-all ${
                isDarkMode
                  ? 'text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800'
                  : 'text-zinc-400 hover:text-zinc-600 hover:bg-zinc-200'
              }`}
            >
              <Upload size={13} />
              파일 업로드
            </button>
            <input ref={fileInputRef} type="file" accept=".sql,.txt" className="hidden"
              onChange={e => handleFile(e.target.files[0])} />
            {sqlCount > 0 && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-mono font-medium border ${isDarkMode ? 'bg-zinc-800 text-zinc-300 border-zinc-700' : 'bg-zinc-100 text-zinc-600 border-zinc-300'}`}>
                {sqlCount}개 쿼리
              </span>
            )}
          </div>

          {/* Run 버튼 — 그라디언트 */}
          <button
            onClick={runDiagnose}
            disabled={loading || sqlCount === 0}
            className={`relative flex items-center gap-2 px-5 py-2 rounded-full text-xs font-bold uppercase tracking-widest transition-all duration-200 hover:scale-105 active:scale-95 disabled:opacity-30 disabled:cursor-not-allowed disabled:hover:scale-100 shadow-lg ${
              isDarkMode
                ? 'bg-zinc-100 text-zinc-900 hover:bg-white shadow-zinc-900/30'
                : 'bg-zinc-900 text-white hover:bg-zinc-700 shadow-zinc-900/20'
            }`}
          >
            <Search size={13} />
            {loading ? 'Analyzing...' : sqlCount > 1 ? `Run Batch (${sqlCount})` : 'Run Diagnose'}
          </button>
        </div>
      </div>
            {fileError && (
        <p className="text-xs text-red-400 mt-2 px-1">{fileError}</p>
      )}
    </div>
  );
}
