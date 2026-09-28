import { useState, useRef, useEffect } from 'react';
import { BarChart2 } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import { getRiskConfig } from '../utils/risk';
import SummaryBar from './SummaryBar';
import { PredictionLogTabs } from './PredictionLogDashboard';

// ─── 배치 요약 대시보드 ───────────────────────────────────────
function BatchSummary({ summary, results, isDarkMode }) {
  const [visible, setVisible] = useState(false);
  const [mainTab, setMainTab] = useState('summary');
  const [tabDir, setTabDir] = useState('right');
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0 });
  const tabRefs = useRef({});
  const handleTabChange = (id) => {
    setTabDir(id === 'prediction' ? 'right' : 'left');
    setMainTab(id);
  };
  useEffect(() => {
    const el = tabRefs.current[mainTab];
    if (el) setIndicatorStyle({ left: el.offsetLeft, width: el.offsetWidth });
  }, [mainTab, visible]);
  useEffect(() => { const t = setTimeout(() => setVisible(true), 50); return () => clearTimeout(t); }, []);

  const theme = {
    card:        isDarkMode ? 'bg-[#1a1a1a] border-[#2d2d2d]' : 'bg-white border-zinc-200',
    subText:     isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500',
    inner:       isDarkMode ? 'bg-[#0e0e0e] border-[#2d2d2d]' : 'bg-zinc-50 border-zinc-200',
    divider:     isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200',
    tabActive:   isDarkMode ? 'bg-[#2d2d2d] text-[#e0e0e0]' : 'bg-zinc-800 text-white',
    tabInactive: isDarkMode ? 'text-[#666] hover:text-[#aaa]' : 'text-zinc-400 hover:text-zinc-600',
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
        <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${isDarkMode ? 'bg-[#2d2d2d]' : 'bg-zinc-800'}`}>
          <BarChart2 size={13} className="text-white" />
        </div>
        {/* 탭 버튼 - 슬라이딩 박스 */}
        <div className={`relative flex p-1 rounded-xl border ${isDarkMode ? 'bg-[#0e0e0e] border-[#2d2d2d]' : 'bg-zinc-100 border-zinc-300'}`}>
          {/* 슬라이딩 인디케이터 */}
          <div
            className={`absolute top-1 bottom-1 rounded-lg shadow-sm ${isDarkMode ? 'bg-[#2d2d2d]' : 'bg-zinc-800'}`}
            style={{
              left: indicatorStyle.left,
              width: indicatorStyle.width,
              transition: 'left 220ms cubic-bezier(0.22, 1, 0.36, 1), width 220ms cubic-bezier(0.22, 1, 0.36, 1)',
            }}
          />
          {[{ id: 'summary', label: '배치 분석 요약' }, { id: 'prediction', label: '예측 로그' }].map(tab => (
            <button
              key={tab.id}
              ref={el => tabRefs.current[tab.id] = el}
              onClick={() => handleTabChange(tab.id)}
              className={`relative z-10 text-xs px-3 py-1.5 rounded-lg font-medium cursor-pointer select-none transition-colors duration-150 ${
                mainTab === tab.id
                  ? (isDarkMode ? 'text-[#e0e0e0]' : 'text-white')
                  : (isDarkMode ? 'text-[#666] hover:text-[#aaa]' : 'text-zinc-400 hover:text-zinc-600')
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className={`ml-auto flex items-center gap-1 text-xs ${theme.subText}`}>
          <span>총</span>
          <span className={`font-bold ${isDarkMode ? 'text-zinc-200' : 'text-zinc-700'}`}>{summary.total}개</span>
          <span>쿼리</span>
        </div>
      </div>

      <div className="p-6 flex flex-col gap-6 overflow-hidden">
        {/* PredictionLog 탭 */}
        {mainTab === 'prediction' && (
          <div key="prediction" className={`animate-tab-from-${tabDir}`}>
            <PredictionLogTabs isDarkMode={isDarkMode} />
          </div>
        )}

        {/* 배치 분석 요약 */}
        {mainTab === 'summary' && (
          <div key="summary" className={`animate-tab-from-${tabDir} flex flex-col gap-6`}>
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
        )}
      </div>
    </div>
  );
}

export default BatchSummary;
