import { useState, useRef } from 'react';
import { PanelLeft, Plus, Search, LogOut, LogIn, Database, X, Clock, Trash2 } from 'lucide-react';
import { API_BASE } from '../utils/api';

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
    bg:        isDarkMode ? 'bg-[#1E1D1B]' : 'bg-zinc-100',
    border:    isDarkMode ? 'border-white/[0.06]' : 'border-zinc-200',
    text:      isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-800',
    subText:   isDarkMode ? 'text-[#666666]' : 'text-zinc-400',
    iconBtn:   isDarkMode ? 'text-[#a0a0a0] hover:bg-[#1e1e1e] hover:text-[#e0e0e0]' : 'text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700',
    itemHover: isDarkMode ? 'text-[#a0a0a0] hover:bg-[#1e1e1e] hover:text-[#e0e0e0]' : 'text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700',
    inputBg:   isDarkMode ? 'bg-[#1a1a1a] border-[#2d2d2d] text-[#c0c0c0] placeholder:text-[#555555]' : 'bg-zinc-200/60 border-zinc-300 text-zinc-600 placeholder:text-zinc-400',
  };

  const miniVisible = !isOpen;

  return (
    <div className={`animate-slide-in-left fixed top-0 left-0 h-full z-30 border-r transition-all duration-300 overflow-hidden ${t.bg} ${t.border} ${isOpen ? 'w-64' : 'w-12'}`}>

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
          <a href={`${API_BASE}/login`} title="Google로 로그인"
            className={`p-2 rounded-lg transition-all flex items-center justify-center ${t.iconBtn}`}>
            <LogIn size={16} />
          </a>
        )}
      </div>

      {/* ── 풀 레이어 (텍스트 포함) ── */}
      <div className={`absolute inset-0 w-64 flex flex-col transition-opacity duration-150 ${isOpen ? 'opacity-100 delay-150' : 'opacity-0 pointer-events-none'}`}>

        {/* 헤더 */}
        <div className="flex items-center gap-2.5 px-3 py-3 shrink-0">
          <div className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${isDarkMode ? 'bg-[#2d2d2d]' : 'bg-zinc-800'}`}>
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
            isDarkMode ? 'border-[#2d2d2d] text-[#a0a0a0] hover:bg-[#1e1e1e] hover:text-[#e0e0e0]' : 'border-zinc-300 text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700'
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
              <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold text-white shrink-0 ${isDarkMode ? 'bg-[#3a3a3a]' : 'bg-zinc-700'}`}>
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
            <a href={`${API_BASE}/login`}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all w-full ${t.iconBtn}`}>
              <LogIn size={13} /> Google로 로그인
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export default Sidebar;
