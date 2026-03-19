import React, { useState } from 'react';
import { Activity, Database, ShieldAlert, Zap, Sun, Moon, Search } from 'lucide-react';

export default function App() {
  // --- [상태 관리] ---
  // 현재 선택된 메뉴 탭 상태 (기본값: 메인)
  const [activeTab, setActiveTab] = useState('메인');
  // 다크모드/라이트모드 전환 상태
  const [isDarkMode, setIsDarkMode] = useState(true);
  // 사용자가 입력한 SQL 쿼리 텍스트 상태
  const [query, setQuery] = useState('');

  // --- [데이터 정의] ---
  // 네비게이션 및 퀵 메뉴에 사용될 설정 데이터
  const tabs = [
    { name: 'AI 쿼리 진단', icon: <Zap size={20} />, desc: 'AI 기반 SQL 최적화' },
    { name: '성능 비교', icon: <Activity size={20} />, desc: '실행 속도 비교 분석' },
    { name: '의존성 맵', icon: <Database size={20} />, desc: '데이터 영향도 시각화' },
    { name: '위험도 스코어', icon: <ShieldAlert size={20} />, desc: '마이그레이션 리스크' },
  ];

  // --- [테마 시스템] ---
  // 다크모드 여부에 따라 변경될 스타일 클래스 모음
  const theme = {
    bg: isDarkMode ? 'bg-[#121212]' : 'bg-zinc-200', 
    sidebar: isDarkMode ? 'bg-[#1e1e1e] border-zinc-800' : 'bg-zinc-300 border-zinc-400/50', 
    card: isDarkMode ? 'bg-[#1e1e1e] border-zinc-800/60' : 'bg-zinc-100/70 border-zinc-400/50 shadow-sm',
    text: isDarkMode ? 'text-zinc-100' : 'text-zinc-800',
    subText: isDarkMode ? 'text-zinc-500' : 'text-zinc-500',
    button: isDarkMode ? 'bg-zinc-100 text-zinc-900 hover:bg-white' : 'bg-zinc-700 text-zinc-100 hover:bg-zinc-800',
  };

  return (
    <div className={`flex h-screen ${theme.bg} ${theme.text} font-sans transition-colors duration-700 overflow-hidden`}>
      
      {/* [1] 좌측 사이드바 영역 */}
      <aside className={`w-20 border-r ${theme.sidebar} flex flex-col items-center py-8 z-20 transition-all`}>
        {/* 상단 메뉴 버튼 리스트 */}
        <div className="flex-1 flex flex-col gap-10 mt-4">
          {tabs.map(t => (
            <button 
              key={t.name} 
              onClick={() => setActiveTab(t.name)} // 클릭 시 해당 탭으로 상태 변경
              className={`${activeTab === t.name ? (isDarkMode ? 'text-white' : 'text-zinc-900') : 'text-zinc-500'} hover:text-zinc-400 transition-all transform hover:scale-110`}
            >
              {t.icon}
            </button>
          ))}
        </div>
        {/* 하단 다크모드 토글 버튼 */}
        <button onClick={() => setIsDarkMode(!isDarkMode)} className="mt-auto opacity-50 hover:opacity-100 transition-opacity p-2">
          {isDarkMode ? <Sun size={20} /> : <Moon size={20} className="text-zinc-500" />}
        </button>
      </aside>

      {/* [2] 메인 컨텐츠 영역 */}
      <main className="flex-1 flex flex-col items-center justify-center p-6 relative">
        
        {/* 중앙 정렬 컨테이너 (애니메이션 효과 포함) */}
        <div className="w-full max-w-3xl flex flex-col items-center animate-in fade-in zoom-in duration-1000">
          
          {/* SQL 쿼리 입력창 섹션 */}
          <div className="w-full relative mb-16">
            <div className={`relative flex flex-col rounded-3xl border ${theme.card} overflow-hidden shadow-lg`}>
              
              {/* 텍스트 입력 영역 (실시간 상태 반영) */}
              <textarea 
                value={query}
                onChange={(e) => setQuery(e.target.value)} // 입력할 때마다 query 상태 업데이트
                placeholder="분석할 Oracle SQL 쿼리를 입력하세요..."
                className={`w-full h-44 p-8 outline-none font-mono resize-none transition-colors ${
                  isDarkMode 
                    ? 'bg-[#1e1e1e] text-zinc-100 placeholder:text-zinc-500' 
                    : 'bg-zinc-50 text-zinc-800 placeholder:opacity-40'
                } text-base leading-relaxed`}
              />
              
              {/* 입력창 하단 컨트롤 바 (데이터 변환 정보 및 실행 버튼) */}
              <div className={`flex items-center justify-between px-8 py-4 border-t ${isDarkMode ? 'border-zinc-800' : 'border-zinc-200'} ${isDarkMode ? 'bg-[#1a1a1a]' : 'bg-black/2'}`}>
                {/* 변환 방향 표시 */}
                <div className="flex gap-4 opacity-40 font-mono">
                   <span className="text-[10px] font-bold tracking-widest uppercase">Oracle</span>
                   <span className="text-[10px] font-bold tracking-widest uppercase">→</span>
                   <span className="text-[10px] font-bold tracking-widest uppercase">MySQL</span>
                </div>
                {/* 분석 실행 버튼 (클릭 시 진단 탭으로 이동) */}
                <button 
                  className={`flex items-center gap-2 px-6 py-2 rounded-full font-bold text-xs uppercase tracking-widest transition-all hover:scale-105 active:scale-95 ${theme.button}`}
                  onClick={() => setActiveTab('AI 쿼리 진단')}
                >
                  <Search size={14} />
                  Run Diagnose
                </button>
              </div>
            </div>
          </div>

          {/* 하단 4개 기능 퀵 메뉴 그리드 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
            {tabs.map((tab) => (
              <button
                key={tab.name}
                onClick={() => setActiveTab(tab.name)} // 클릭 시 해당 기능으로 탭 이동
                className={`flex flex-col items-center p-6 rounded-3xl border ${theme.card} hover:border-zinc-500/50 hover:bg-zinc-400/10 transition-all group`}
              >
                {/* 아이콘 배경 및 아이콘 처리 */}
                <div className={`mb-3 p-3 rounded-xl ${isDarkMode ? 'bg-zinc-800/50' : 'bg-zinc-300/50'} group-hover:bg-zinc-700/50 transition-colors`}>
                  {React.cloneElement(tab.icon, { 
                    size: 20, 
                    className: activeTab === tab.name 
                      ? (isDarkMode ? 'text-white' : 'text-zinc-900') 
                      : 'text-zinc-500' 
                  })}
                </div>
                {/* 탭 제목 및 설명 */}
                <span className="text-[11px] font-bold mb-1 tracking-tight">{tab.name}</span>
                <span className={`text-[9px] ${theme.subText} text-center leading-tight px-1 opacity-70`}>{tab.desc}</span>
              </button>
            ))}
          </div>
        </div>

      </main>
    </div>
  );
}