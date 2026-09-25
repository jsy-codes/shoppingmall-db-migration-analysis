import { useRef } from 'react';
import { BookOpen, X } from 'lucide-react';
import { useModalKeyboard } from '../hooks/useModalKeyboard';
import { HELP_SECTIONS } from '../data/helpSections';

// ─── 도움말 모달 ───────────────────────────────────────────────
function HelpModal({ onClose, isDarkMode }) {
  const modalRef = useRef(null); 

  const theme = {
    bg:      isDarkMode ? 'bg-[#1a1a1a]' : 'bg-white',
    card:    isDarkMode ? 'bg-[#242424] border-[#2d2d2d]' : 'bg-zinc-50 border-zinc-200',
    text:    isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-800',
    subText: isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500',
    divider: isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200',
    code:    isDarkMode ? 'bg-[#111111] text-green-400' : 'bg-zinc-100 text-green-700',
    badge:   isDarkMode ? 'bg-[#1e1e1e] text-[#c0c0c0]' : 'bg-zinc-200 text-zinc-600',
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
          <BookOpen size={18} className={isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-400'} />
          <div>
            <h2 className={`text-base font-bold ${theme.text}`}>사용 가이드</h2>
            <p className={`text-xs mt-0.5 ${theme.subText}`}>Oracle → MySQL 이관 위험도 분석 도구</p>
          </div>
          <button onClick={onClose} className={`ml-auto p-1.5 rounded-lg transition-colors ${
            isDarkMode ? 'hover:bg-[#1e1e1e] text-[#a0a0a0]' : 'hover:bg-zinc-100 text-zinc-500'
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
                <div className={`rounded-xl overflow-hidden border ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-200'}`}>
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
              isDarkMode ? 'bg-[#e0e0e0] text-[#121212] hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700'
            }`}
          >
            확인
          </button>
        </div>
      </div>
    </div>
  );
}

export default HelpModal;
