import { useState, useEffect } from 'react';
import { ChevronDown, Copy, Check } from 'lucide-react';
import { getRiskConfig } from '../utils/risk';
import RiskBadge from './RiskBadge';
import TypewriterText from './TypewriterText';

// ─── 아코디언 아이템 ──────────────────────────────────────────
function QueryAccordion({ result, index, isDarkMode, delay = 0 }) {
  const [visible, setVisible] = useState(false);
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedSql, setCopiedSql] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => {
      setVisible(true);
      if (result.risk === 'HIGH') setOpen(true);
    }, delay);
    return () => clearTimeout(t);
  }, [delay, result.risk]);

  const theme = {
    card:    isDarkMode ? 'bg-[#1a1a1a] border-[#2d2d2d]' : 'bg-white border-zinc-200',
    subText: isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500',
    inner:   isDarkMode ? 'bg-[#111111]/60' : 'bg-zinc-50',
    divider: isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200',
  };
  const cfg = getRiskConfig(isDarkMode)[result.risk] || getRiskConfig(isDarkMode).LOW;

  const accentStyle = {
    HIGH:   { bar: 'bg-red-500',    glow: isDarkMode ? 'from-red-500/20 to-transparent'    : 'from-red-200 to-transparent' },
    MEDIUM: { bar: 'bg-yellow-500', glow: isDarkMode ? 'from-yellow-500/20 to-transparent' : 'from-yellow-200 to-transparent' },
    LOW:    { bar: 'bg-emerald-500',glow: isDarkMode ? 'from-emerald-500/15 to-transparent' : 'from-emerald-200 to-transparent' },
  }[result.risk] || { bar: 'bg-zinc-500', glow: 'from-transparent to-transparent' };

  const copyText = async (text, setter) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const el = document.createElement('textarea');
      el.value = text;
      el.style.cssText = 'position:fixed;opacity:0';
      document.body.appendChild(el);
      el.select();
      document.execCommand('copy');
      document.body.removeChild(el);
    }
    setter(true);
    setTimeout(() => setter(false), 2000);
  };

  const copyDdl = () => copyText(result.recommended_ddl, setCopied);
  const copySql = () => copyText(result.sql, setCopiedSql);

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
          <span className={`text-xs font-mono px-2 py-0.5 rounded-md border ${isDarkMode ? 'bg-[#1e1e1e] border-[#2d2d2d] text-[#a0a0a0]' : 'bg-zinc-100 border-zinc-300 text-zinc-500'}`}>
            {result.top.id}
          </span>
        )}
        <span className={`text-sm font-medium truncate flex-1 ${isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-800'}`}>
          {result.top?.name || '패턴 없음'}
        </span>
        <span className={`text-xs ${theme.subText} font-mono shrink-0 hidden md:block max-w-48 truncate`}>{shortSQL}</span>
        <span className={`shrink-0 transition-transform duration-200 ${open ? 'rotate-180' : ''} ${cfg.text}`}>
          <ChevronDown size={16} />
        </span>
      </button>

      {open && (
        <div id={`query-detail-${result.index}`} className={`border-t ${theme.divider}`}>
          <div className={`grid grid-cols-2 divide-x ${isDarkMode ? 'divide-[#2d2d2d]' : 'divide-zinc-200'}`}>

            {/* 왼쪽: SQL 원문 + 문제 설명 */}
            <div className={`flex flex-col ${isDarkMode ? 'divide-y divide-[#2d2d2d] bg-[#111111]/40' : 'divide-y divide-zinc-200 bg-zinc-50/60'}`}>

              {/* SQL 원문 */}
              <div className="p-4">
                <div className={`flex items-center justify-between mb-2 pb-2 border-b ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>
                  <div className="flex items-center gap-1.5">
                    <p className={`text-sm font-bold ${isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-700'}`}>SQL 원문</p>
                  </div>
                  <button
                    onClick={copySql}
                    className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg transition-all ${
                      isDarkMode ? 'bg-[#1e1e1e] hover:bg-[#2a2a2a] text-[#c0c0c0] border border-[#2d2d2d]' : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-600 border border-zinc-300'
                    }`}
                  >
                    {copiedSql ? <Check size={11} /> : <Copy size={11} />}
                    {copiedSql ? '복사됨' : '복사'}
                  </button>
                </div>
                <pre className={`text-xs font-mono p-3 rounded-lg leading-relaxed whitespace-pre-wrap break-words ${
                  isDarkMode ? 'bg-[#0a0a0a] text-[#c0c0c0] border border-[#2d2d2d]' : 'bg-zinc-100 text-zinc-700 border border-zinc-300'
                }`}>
                  {result.sql}
                </pre>
              </div>

              {/* 문제 설명 */}
              {result.reason && (
                <div className="p-4">
                  <div className={`flex items-center gap-1.5 mb-2 pb-2 border-b ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>
                    <div className="w-1 h-3.5 rounded-full bg-red-400" />
                    <p className={`text-sm font-bold ${isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-700'}`}>문제 설명</p>
                  </div>
                  <p className={`text-xs leading-relaxed ${isDarkMode ? 'text-zinc-300' : 'text-zinc-600'}`}>
                    <TypewriterText text={result.reason} speed={15} />
                  </p>
                </div>
              )}

              {/* 감지된 패턴 — 2개 이상일 때만 표시 */}
              {result.matched.length >= 2 && (
                <div className="p-4">
                  <div className={`flex items-center gap-1.5 mb-2 pb-2 border-b ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>
                    <p className={`text-sm font-bold ${isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-700'}`}>
                      감지된 패턴
                      <span className={`ml-1.5 px-1.5 py-0.5 rounded-full text-xs ${isDarkMode ? 'bg-[#1e1e1e] text-[#a0a0a0]' : 'bg-zinc-200 text-zinc-500'}`}>
                        {result.matched.length}
                      </span>
                    </p>
                  </div>
                  <div className="flex flex-col gap-1.5">
                    {result.matched.map(m => {
                      const mc = getRiskConfig(isDarkMode)[m.risk] || getRiskConfig(isDarkMode).LOW;
                      return (
                        <div key={m.id} className={`flex items-center gap-2 px-2.5 py-2 rounded-lg border ${mc.bg} ${mc.border}`}>
                          <span className={`text-xs font-mono font-bold shrink-0 ${mc.text}`}>{m.id}</span>
                          <p className={`text-xs font-bold flex-1 truncate ${mc.text}`}>{m.name}</p>
                          <RiskBadge risk={m.risk} isDarkMode={isDarkMode} />
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* 오른쪽: 권고 DDL + 개선 효과 */}
            <div className={`flex flex-col divide-y ${isDarkMode ? 'divide-[#2d2d2d]' : 'divide-zinc-200'}`}>

              {/* 권고 DDL */}
              <div className="flex-1">
                <div className={`flex items-center justify-between px-4 py-3 border-b ${theme.divider}`}>
                  <div className="flex items-center gap-1.5">
                    <p className={`text-sm font-bold ${isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-700'}`}>권고 DDL</p>
                    {result.recommended_ddl && (
                      <span className={`text-xs px-1.5 py-0.5 rounded-full border ${isDarkMode ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/20' : 'bg-emerald-100 text-emerald-700 border-emerald-400'}`}>AI 생성</span>
                    )}
                  </div>
                  <button
                    onClick={copyDdl}
                    disabled={!result.recommended_ddl}
                    className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-lg transition-all disabled:opacity-30 ${
                      isDarkMode ? 'bg-[#1e1e1e] hover:bg-[#2a2a2a] text-[#c0c0c0] border border-[#2d2d2d]' : 'bg-zinc-100 hover:bg-zinc-200 text-zinc-600 border border-zinc-300'
                    }`}
                  >
                    {copied ? <Check size={11} /> : <Copy size={11} />}
                    {copied ? '복사됨' : '복사'}
                  </button>
                </div>
                <pre className={`px-4 py-3 font-mono text-xs max-h-52 whitespace-pre-wrap break-words ${isDarkMode ? 'bg-[#0a0a0a] text-green-400' : 'bg-zinc-100 text-green-700 border-t border-zinc-300'}`}>
                  {result.recommended_ddl
                    ? <TypewriterText text={result.recommended_ddl} speed={10} />
                    : (result.matched.length === 0 ? '-- 권고 DDL 없음' : '-- API 연동 후 AI 생성 DDL이 표시됩니다')
                  }
                </pre>
              </div>

              {/* 예상 개선 효과 */}
              {result.estimated_improvement && (
                <div className="p-4">
                  <div className={`flex items-center gap-1.5 mb-2 pb-2 border-b ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>
                    <div className="w-1 h-3.5 rounded-full bg-emerald-400" />
                    <p className={`text-sm font-bold ${isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-700'}`}>예상 개선 효과</p>
                  </div>
                  <p className={`text-xs leading-relaxed ${isDarkMode ? 'text-zinc-300' : 'text-zinc-600'}`}>
                    <TypewriterText text={result.estimated_improvement} speed={15} />
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default QueryAccordion;
