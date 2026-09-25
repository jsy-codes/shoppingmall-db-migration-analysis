import { useState, useRef } from 'react';
import { X } from 'lucide-react';
import { useModalKeyboard } from '../hooks/useModalKeyboard';
import { PATTERN_CATALOG } from '../data/patternCatalog';
import { getRiskConfig } from '../utils/risk';

// ─── 패턴 카탈로그 모달 (2열 그리드) ─────────────────────────
function PatternCatalogModal({ onClose, isDarkMode }) {
  const [filter, setFilter] = useState('ALL');
  const modalRef = useRef(null);  
  const theme = {
    bg:      isDarkMode ? 'bg-[#1a1a1a]' : 'bg-white',
    text:    isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-800',
    subText: isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500',
    divider: isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200',
    card:    isDarkMode ? 'bg-[#242424] border-[#2d2d2d]' : 'bg-zinc-50 border-zinc-200',
    code:    isDarkMode ? 'bg-[#111111] text-[#c0c0c0]' : 'bg-zinc-100 text-zinc-700',
    fix:     isDarkMode ? 'bg-[#111111] text-green-400' : 'bg-green-50 text-green-700',
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
              isDarkMode ? 'hover:bg-[#1e1e1e] text-[#a0a0a0]' : 'hover:bg-zinc-100 text-zinc-500'
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
                    ? isDarkMode ? 'bg-[#e0e0e0] text-[#121212]' : 'bg-zinc-800 text-white'
                    : `${isDarkMode ? 'bg-[#1e1e1e] hover:bg-[#2a2a2a]' : 'bg-zinc-100 hover:bg-zinc-200'} ${cls || theme.subText}`
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
              isDarkMode ? 'bg-[#e0e0e0] text-[#121212] hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
          >
            닫기
          </button>
        </div>
      </div>
    </div>
  );
}

export default PatternCatalogModal;
