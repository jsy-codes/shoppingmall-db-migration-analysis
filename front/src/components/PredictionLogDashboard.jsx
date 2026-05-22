import React, { useState, useEffect } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, ReferenceLine, Legend,
} from 'recharts';
import { AlertTriangle, Shield, Info, TrendingDown, Activity, Search, Zap } from 'lucide-react';
import mockData from '../data/mock_prediction_log.json';

const API_BASE = 'http://localhost:8000';

async function fetchLogs() {
  const res = await fetch(`${API_BASE}/logs`);
  if (!res.ok) throw new Error('logs fetch failed');
  return res.json();
}

const TABS = [
  { id: 'error',  label: '오차율 현황',          icon: <Activity size={14} /> },
  { id: 'compare',label: '패턴별 실측 비교',      icon: <Search size={14} /> },
  { id: 'grid',   label: 'Grid Search 보정 이력', icon: <TrendingDown size={14} /> },
  { id: 'quant',  label: 'quant_signal',          icon: <Zap size={14} /> },
];

const RISK_COLOR = { HIGH: '#ef4444', MEDIUM: '#eab308', LOW: '#22c55e' };

function RiskBadge({ risk }) {
  const colors = {
    HIGH:   'bg-red-500/20 text-red-400 border-red-500/40',
    MEDIUM: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40',
    LOW:    'bg-green-500/20 text-green-400 border-green-500/40',
  };
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border font-semibold ${colors[risk] ?? ''}`}>
      {risk}
    </span>
  );
}

// ── 탭 1: 오차율 현황 테이블 ─────────────────────────────────────
function ErrorRateTab({ isDarkMode, logs }) {
  const t = isDarkMode
    ? { row: 'hover:bg-[#1e1e1e]', border: 'border-[#2d2d2d]', sub: 'text-[#888]' }
    : { row: 'hover:bg-zinc-50',   border: 'border-zinc-200',   sub: 'text-zinc-400' };

  const validLogs = logs.filter(l => l.error_rate != null);
  const avgError = validLogs.length
    ? (validLogs.reduce((s, l) => s + l.error_rate, 0) / validLogs.length).toFixed(2)
    : '0.00';
  const overThreshold = validLogs.filter(l => l.error_rate > 3.0).length;

  return (
    <div className="space-y-4">
      {/* 요약 카드 */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: '평균 오차율', value: `${avgError}%`, sub: '전체 패턴 기준', color: parseFloat(avgError) <= 3 ? 'text-green-400' : 'text-red-400' },
          { label: '기록 수',     value: logs.length, sub: '총 진단 로그', color: 'text-blue-400' },
          { label: '3% 초과',    value: `${overThreshold}개`, sub: '패턴 수',       color: overThreshold > 0 ? 'text-red-400' : 'text-green-400' },
        ].map(card => (
          <div key={card.label} className={`rounded-xl p-3 border ${isDarkMode ? 'bg-[#161616] border-[#2d2d2d]' : 'bg-white border-zinc-200'}`}>
            <p className={`text-xs ${t.sub}`}>{card.label}</p>
            <p className={`text-xl font-bold mt-1 ${card.color}`}>{card.value}</p>
            <p className={`text-[10px] mt-0.5 ${t.sub}`}>{card.sub}</p>
          </div>
        ))}
      </div>

      {/* 테이블 */}
      <div className={`rounded-xl border overflow-hidden ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>
        <table className="w-full text-sm">
          <thead>
            <tr className={`text-xs ${isDarkMode ? 'bg-[#161616] text-[#888]' : 'bg-zinc-50 text-zinc-400'}`}>
              {['패턴 ID', '패턴명', '위험도', '예측 점수', '실행 전(ms)', '실행 후(ms)', '오차율(%)'].map(h => (
                <th key={h} className={`px-3 py-2.5 text-left font-medium border-b ${t.border}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {logs.map((log, i) => (
              <tr key={log.pattern_id + i} className={`transition-colors ${t.row} ${i !== logs.length - 1 ? `border-b ${t.border}` : ''}`}>
                <td className="px-3 py-2 font-mono text-xs text-blue-400">{log.pattern_id}</td>
                <td className={`px-3 py-2 text-xs ${isDarkMode ? 'text-[#ccc]' : 'text-zinc-700'}`}>{log.pattern_name}</td>
                <td className="px-3 py-2"><RiskBadge risk={log.risk} /></td>
                <td className={`px-3 py-2 text-xs font-medium ${isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-800'}`}>{log.predicted_score}</td>
                <td className={`px-3 py-2 text-xs ${isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500'}`}>{log.before_ms != null ? log.before_ms.toLocaleString() : '-'}</td>
                <td className="px-3 py-2 text-xs text-green-400">{log.after_ms ?? '-'}</td>
                <td className="px-3 py-2">
                  {log.error_rate != null ? (
                    <span className={`text-xs font-semibold ${log.error_rate > 3.0 ? 'text-red-400' : 'text-green-400'}`}>
                      {log.error_rate.toFixed(2)}%
                      {log.error_rate > 3.0 && <span className="ml-1 text-[10px]">⚠</span>}
                    </span>
                  ) : <span className="text-xs text-zinc-400">-</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 탭 2: 패턴별 실측 비교 막대 차트 ────────────────────────────
function CompareTab({ isDarkMode, logs }) {
  const chartData = logs.map(l => ({
    name: l.pattern_id,
    before: l.before_ms,
    after: l.after_ms,
    error: l.error_rate,
    risk: l.risk,
  }));

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div className={`rounded-lg px-3 py-2 text-xs shadow-lg border ${isDarkMode ? 'bg-[#1a1a1a] border-[#3d3d3d] text-[#e0e0e0]' : 'bg-white border-zinc-200 text-zinc-800'}`}>
        <p className="font-semibold mb-1">{label}</p>
        {payload.map(p => (
          <p key={p.dataKey} style={{ color: p.color }}>{p.name}: {p.value}{p.dataKey === 'error' ? '%' : 'ms'}</p>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <p className={`text-xs ${isDarkMode ? 'text-[#888]' : 'text-zinc-400'}`}>
        패턴별 이관 전(before_ms) / 이관 후(after_ms) 실측 비교 · 오차율 3.0% 초과 시 빨간색 강조
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} barGap={2} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#2d2d2d' : '#e5e7eb'} />
          <XAxis dataKey="name" tick={{ fill: isDarkMode ? '#888' : '#6b7280', fontSize: 11 }} />
          <YAxis tick={{ fill: isDarkMode ? '#888' : '#6b7280', fontSize: 11 }} />
          <Tooltip content={<CustomTooltip />} />
          <Legend wrapperStyle={{ fontSize: 11, color: isDarkMode ? '#888' : '#6b7280' }} />
          <Bar dataKey="before" name="이관 전(ms)" radius={[3,3,0,0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.error > 3.0 ? '#ef4444' : '#6366f1'} fillOpacity={0.8} />
            ))}
          </Bar>
          <Bar dataKey="after" name="이관 후(ms)" fill="#22c55e" fillOpacity={0.7} radius={[3,3,0,0]} />
        </BarChart>
      </ResponsiveContainer>

      {/* 오차율 막대 */}
      <p className={`text-xs font-medium ${isDarkMode ? 'text-[#ccc]' : 'text-zinc-600'}`}>패턴별 오차율</p>
      <ResponsiveContainer width="100%" height={160}>
        <BarChart data={chartData} barCategoryGap="30%">
          <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#2d2d2d' : '#e5e7eb'} />
          <XAxis dataKey="name" tick={{ fill: isDarkMode ? '#888' : '#6b7280', fontSize: 11 }} />
          <YAxis tick={{ fill: isDarkMode ? '#888' : '#6b7280', fontSize: 11 }} domain={[0, 5]} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={3.0} stroke="#ef4444" strokeDasharray="4 2" label={{ value: '3.0%', fill: '#ef4444', fontSize: 10 }} />
          <Bar dataKey="error" name="오차율(%)" radius={[3,3,0,0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={entry.error > 3.0 ? '#ef4444' : '#22c55e'} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ── 탭 3: Grid Search 보정 이력 ──────────────────────────────────
function GridSearchTab({ isDarkMode }) {
  const history = mockData.grid_search_history;
  const best = history.find(h => h.best);

  const CustomTooltip = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    const d = history[label - 1];
    return (
      <div className={`rounded-lg px-3 py-2 text-xs shadow-lg border ${isDarkMode ? 'bg-[#1a1a1a] border-[#3d3d3d] text-[#e0e0e0]' : 'bg-white border-zinc-200 text-zinc-800'}`}>
        <p className="font-semibold mb-1">Round {label}</p>
        <p>평균 오차율: <span className={payload[0].value <= 3 ? 'text-green-400' : 'text-red-400'}>{payload[0].value}%</span></p>
        {d && <><p className="text-[#888]">DECAY_RATE: {d.decay_rate}</p><p className="text-[#888]">BONUS: {d.category_bonus}</p></>}
        {d?.best && <p className="text-yellow-400 font-semibold">★ 최적</p>}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      {best && (
        <div className={`rounded-xl p-3 border ${isDarkMode ? 'bg-yellow-500/10 border-yellow-500/30' : 'bg-yellow-50 border-yellow-200'}`}>
          <p className="text-yellow-400 text-xs font-semibold mb-1">★ 최적 파라미터 (Round {best.round})</p>
          <div className="flex gap-4 text-xs">
            <span className={isDarkMode ? 'text-[#ccc]' : 'text-zinc-700'}>DECAY_RATE: <strong>{best.decay_rate}</strong></span>
            <span className={isDarkMode ? 'text-[#ccc]' : 'text-zinc-700'}>CATEGORY_BONUS: <strong>{best.category_bonus}</strong></span>
            <span className="text-green-400">평균 오차율: <strong>{best.avg_error_rate}%</strong></span>
          </div>
        </div>
      )}

      <p className={`text-xs ${isDarkMode ? 'text-[#888]' : 'text-zinc-400'}`}>
        보정 회차별 평균 오차율 변화 · 빨간 점선: 목표 기준선 3.0%
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={history.map(h => ({ ...h, round: h.round }))}>
          <CartesianGrid strokeDasharray="3 3" stroke={isDarkMode ? '#2d2d2d' : '#e5e7eb'} />
          <XAxis dataKey="round" label={{ value: '보정 회차', position: 'insideBottom', offset: -2, fill: isDarkMode ? '#666' : '#9ca3af', fontSize: 11 }} tick={{ fill: isDarkMode ? '#888' : '#6b7280', fontSize: 11 }} />
          <YAxis domain={[0, 6]} tick={{ fill: isDarkMode ? '#888' : '#6b7280', fontSize: 11 }} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={3.0} stroke="#ef4444" strokeDasharray="5 3" label={{ value: '목표 3.0%', fill: '#ef4444', fontSize: 10, position: 'insideTopRight' }} />
          <Line
            type="monotone"
            dataKey="avg_error_rate"
            name="평균 오차율(%)"
            stroke="#6366f1"
            strokeWidth={2}
            dot={(props) => {
              const { cx, cy, payload } = props;
              return payload.best
                ? <circle key={cx} cx={cx} cy={cy} r={6} fill="#eab308" stroke="#fff" strokeWidth={1.5} />
                : <circle key={cx} cx={cx} cy={cy} r={3} fill="#6366f1" />;
            }}
          />
        </LineChart>
      </ResponsiveContainer>

      {/* 보정 이력 테이블 */}
      <div className={`rounded-xl border overflow-hidden ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>
        <table className="w-full text-xs">
          <thead>
            <tr className={isDarkMode ? 'bg-[#161616] text-[#888]' : 'bg-zinc-50 text-zinc-400'}>
              {['Round', 'DECAY_RATE', 'CATEGORY_BONUS', '평균 오차율', ''].map(h => (
                <th key={h} className={`px-3 py-2 text-left font-medium border-b ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {history.map((h, i) => (
              <tr key={h.round} className={`${h.best ? (isDarkMode ? 'bg-yellow-500/5' : 'bg-yellow-50') : (isDarkMode ? 'hover:bg-[#1e1e1e]' : 'hover:bg-zinc-50')} ${i !== history.length - 1 ? `border-b ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}` : ''}`}>
                <td className={`px-3 py-2 font-medium ${isDarkMode ? 'text-[#ccc]' : 'text-zinc-700'}`}>{h.round}</td>
                <td className={`px-3 py-2 font-mono ${isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500'}`}>{h.decay_rate}</td>
                <td className={`px-3 py-2 font-mono ${isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500'}`}>{h.category_bonus}</td>
                <td className={`px-3 py-2 font-semibold ${h.avg_error_rate <= 3.0 ? 'text-green-400' : 'text-red-400'}`}>{h.avg_error_rate}%</td>
                <td className="px-3 py-2">{h.best && <span className="text-yellow-400 text-[10px] font-semibold">★ 최적</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ── 탭 4: quant_signal 뷰 ────────────────────────────────────────
function QuantSignalTab({ isDarkMode }) {
  const signals = mockData.quant_signals;
  const t = isDarkMode
    ? { card: 'bg-[#161616] border-[#2d2d2d]', sub: 'text-[#888]', text: 'text-[#ccc]' }
    : { card: 'bg-white border-zinc-200',        sub: 'text-zinc-400', text: 'text-zinc-700' };

  return (
    <div className="space-y-4">
      <p className={`text-xs ${isDarkMode ? 'text-[#888]' : 'text-zinc-400'}`}>
        EXPLAIN 실행 계획 기반 정량 신호 · 실 API 연동 후 진단 결과와 연동 예정 (W2)
      </p>
      <div className="grid grid-cols-1 gap-3">
        {signals.map(sig => (
          <div key={sig.pattern_id} className={`rounded-xl border p-4 ${t.card}`}>
            <div className="flex items-center justify-between mb-3">
              <span className="font-mono text-sm font-semibold text-blue-400">{sig.pattern_id}</span>
              <div className="flex gap-2">
                {sig.no_index_flag && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/20 text-red-400 border border-red-500/40 font-semibold">
                    NO INDEX
                  </span>
                )}
              </div>
            </div>

            {/* full_scan_ratio 게이지 */}
            <div className="mb-3">
              <div className="flex justify-between items-center mb-1">
                <span className={`text-[11px] ${t.sub}`}>full_scan_ratio</span>
                <span className={`text-[11px] font-semibold ${sig.full_scan_ratio > 0.5 ? 'text-red-400' : 'text-green-400'}`}>
                  {(sig.full_scan_ratio * 100).toFixed(0)}%
                </span>
              </div>
              <div className={`h-2 rounded-full overflow-hidden ${isDarkMode ? 'bg-[#2d2d2d]' : 'bg-zinc-200'}`}>
                <div
                  className={`h-full rounded-full transition-all duration-700 ${sig.full_scan_ratio > 0.7 ? 'bg-red-500' : sig.full_scan_ratio > 0.4 ? 'bg-yellow-500' : 'bg-green-500'}`}
                  style={{ width: `${sig.full_scan_ratio * 100}%` }}
                />
              </div>
            </div>

            {/* rows_ratio */}
            <div className="flex items-center justify-between">
              <span className={`text-[11px] ${t.sub}`}>rows_ratio</span>
              <span className={`text-xs font-semibold px-2 py-0.5 rounded ${sig.rows_ratio > 100 ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}`}>
                {sig.rows_ratio}x {sig.rows_ratio > 100 && '⚠ 급증'}
              </span>
            </div>
          </div>
        ))}
      </div>
      <div className={`rounded-xl border p-3 text-xs ${isDarkMode ? 'bg-[#161616] border-[#2d2d2d] text-[#666]' : 'bg-zinc-50 border-zinc-200 text-zinc-400'}`}>
        W2에서 /diagnose API 응답에 explain_signal 필드 추가 후 실 데이터로 전환 예정
      </div>
    </div>
  );
}

// ── 탭 내용만 (BatchSummary 내장용) ─────────────────────────────
export function PredictionLogTabs({ isDarkMode }) {
  const [activeTab, setActiveTab] = useState('error');
  const [logs, setLogs] = useState(mockData.logs);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs()
      .then(setLogs)
      .catch(() => setLogs(mockData.logs))
      .finally(() => setLoading(false));
  }, []);

  const theme = isDarkMode
    ? { tabActive: 'bg-[#1e1e1e] text-[#e0e0e0] border-[#3d3d3d]', tabInactive: 'text-[#666] hover:text-[#aaa] hover:bg-[#161616]' }
    : { tabActive: 'bg-white text-zinc-800 border-zinc-300',          tabInactive: 'text-zinc-400 hover:text-zinc-600 hover:bg-zinc-50'  };

  if (loading) return (
    <div className={`flex items-center justify-center h-32 text-xs ${isDarkMode ? 'text-[#666]' : 'text-zinc-400'}`}>
      로딩 중...
    </div>
  );

  return (
    <div className="space-y-4">
      <div className={`flex gap-1 p-1 rounded-xl border w-fit ${isDarkMode ? 'bg-[#111] border-[#2d2d2d]' : 'bg-zinc-200 border-zinc-300'}`}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-all font-medium ${
              activeTab === tab.id ? `${theme.tabActive} border` : `${theme.tabInactive} border-transparent`
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>
      {activeTab === 'error'   && <ErrorRateTab  isDarkMode={isDarkMode} logs={logs} />}
      {activeTab === 'compare' && <CompareTab    isDarkMode={isDarkMode} logs={logs} />}
      {activeTab === 'grid'    && <GridSearchTab isDarkMode={isDarkMode} />}
      {activeTab === 'quant'   && <QuantSignalTab isDarkMode={isDarkMode} />}
    </div>
  );
}

// ── 메인 대시보드 ────────────────────────────────────────────────
export default function PredictionLogDashboard({ isDarkMode, onClose }) {
  const [activeTab, setActiveTab] = useState('error');
  const [logs, setLogs] = useState(mockData.logs);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLogs()
      .then(setLogs)
      .catch(() => setLogs(mockData.logs))
      .finally(() => setLoading(false));
  }, []);

  const theme = isDarkMode
    ? { bg: 'bg-[#121212]', card: 'bg-[#1a1a1a] border-[#2d2d2d]', text: 'text-[#e0e0e0]', sub: 'text-[#888]', tabActive: 'bg-[#1e1e1e] text-[#e0e0e0] border-[#3d3d3d]', tabInactive: 'text-[#666] hover:text-[#aaa] hover:bg-[#161616]' }
    : { bg: 'bg-zinc-100',  card: 'bg-white border-zinc-200',        text: 'text-zinc-800',   sub: 'text-zinc-400', tabActive: 'bg-white text-zinc-800 border-zinc-300',           tabInactive: 'text-zinc-400 hover:text-zinc-600 hover:bg-zinc-50'  };

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} p-6`}>
      {/* 헤더 */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-lg font-bold">예측 로그 대시보드</h1>
          <p className={`text-xs mt-0.5 ${theme.sub}`}>
            {loading ? '데이터 로딩 중...' : `${logs.length}개 로그 · /logs API 연동`}
          </p>
        </div>
        <button
          onClick={onClose}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${isDarkMode ? 'border-[#3d3d3d] text-[#888] hover:text-[#e0e0e0] hover:bg-[#1e1e1e]' : 'border-zinc-300 text-zinc-500 hover:text-zinc-800 hover:bg-zinc-100'}`}
        >
          ← 진단 화면으로
        </button>
      </div>

      {/* 탭 바 */}
      <div className={`flex gap-1 p-1 rounded-xl border mb-5 w-fit ${isDarkMode ? 'bg-[#111] border-[#2d2d2d]' : 'bg-zinc-200 border-zinc-300'}`}>
        {TABS.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border transition-all font-medium ${
              activeTab === tab.id ? `${theme.tabActive} border` : `${theme.tabInactive} border-transparent`
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* 탭 콘텐츠 */}
      <div className={`rounded-2xl border p-5 ${theme.card}`}>
        {activeTab === 'error'   && <ErrorRateTab    isDarkMode={isDarkMode} logs={logs} />}
        {activeTab === 'compare' && <CompareTab      isDarkMode={isDarkMode} logs={logs} />}
        {activeTab === 'grid'    && <GridSearchTab   isDarkMode={isDarkMode} />}
        {activeTab === 'quant'   && <QuantSignalTab  isDarkMode={isDarkMode} />}
      </div>
    </div>
  );
}
