import { useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { AlertTriangle, Sun, Moon, HelpCircle, Zap, Search } from 'lucide-react';
import PredictionLogDashboard from './components/PredictionLogDashboard';

import { API_BASE, IS_MOCK, getAuthHeaders } from './utils/api';
import { RISK_RANK } from './utils/risk';
import { splitSQLs, analyzeSQL, calcSummary, processApiResult } from './utils/diagnosis';
import { EXAMPLE_QUERIES } from './data/exampleQueries';

import Sidebar from './components/Sidebar';
import InputArea from './components/InputArea';
import QueryAccordion from './components/QueryAccordion';
import BatchSummary from './components/BatchSummary';
import PatternCatalogModal from './components/PatternCatalogModal';
import HelpModal from './components/HelpModal';

// ─── 메인 App ─────────────────────────────────────────────────
export default function App() {


  const [page, setPage]               = useState('main'); // 'main' | 'prediction'

  const [isDarkMode, setIsDarkMode]   = useState(() => {
    const saved = localStorage.getItem('darkMode');
    return saved !== null ? saved === 'true' : true;
  });
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
  const [isExiting, setIsExiting]     = useState(false);
  const [isOfflineCache, setIsOfflineCache] = useState(false);
  const fileInputRef = useRef(null);

  const handleCloseHelp    = useCallback(() => setShowHelp(false),    []);
  const handleCloseCatalog = useCallback(() => setShowCatalog(false), []);
  // ─── 히스토리 갱신 함수 (초기 로딩 + 진단 완료 후 재사용) ───
const refreshHistory = useCallback(async () => {
  try {
    const res = await fetch(
      `${API_BASE}/history?limit=30&offset=0`,
      { headers: getAuthHeaders() }
    );
    if (res.ok) {
      const data = await res.json();
      setHistoryItems(data);
    }
  } catch { }
}, []);
  // ─── 배치 결과 전체를 하나의 세션으로 저장 ─────────────────
const saveSession = useCallback(async (allResults, originalQuery, sqlList) => {
  try {
    const resultsWithSql = allResults.map((r, i) => ({
      ...r,
      query_sql: sqlList[i] ?? ''
    }));

    const res = await fetch(
      `${API_BASE}/session`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...getAuthHeaders(),
        },
        body: JSON.stringify({ query_sql: originalQuery, results: resultsWithSql }),
      }
    );

    const data = await res.json();
  } catch (err) {
    console.error("SESSION ERROR:", err);
  }

  await refreshHistory();
}, [refreshHistory]);

  // ─── 히스토리 + 유저 로딩 ───────────────────────────────────
  useEffect(() => {
  const params = new URLSearchParams(window.location.search);
  const token = params.get('token');
  if (token) {
    localStorage.setItem('auth_token', token);
    window.history.replaceState({}, '', '/');
  }

  const savedToken = localStorage.getItem('auth_token');
  const headers = savedToken ? { Authorization: `Bearer ${savedToken}` } : {};
//http://localhost:5173
  const loadAll = async () => {
    try {
      const [meRes, histRes] = await Promise.all([
        fetch(`${API_BASE}/me`, { headers: getAuthHeaders() }),
        fetch(`${API_BASE}/history?limit=30&offset=0`, { headers: getAuthHeaders() }),
      ]);
      if (meRes.ok) {
        const meData = await meRes.json();
        setUser(meData.email ? { email: meData.email } : null);
      }
      if (histRes.ok) {
        const histData = await histRes.json();
        setHistoryItems(histData);
      }
    } catch { }
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
    await fetch(`${API_BASE}/history/${id}`, {
      method: 'DELETE',
      headers: getAuthHeaders(),
    });
    setHistoryItems(prev => prev.filter(item => item.id !== id));
  } catch { }
}, []);

 const handleLogout = useCallback(async () => {
  localStorage.removeItem('auth_token');
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

      const sorted = [...loaded].sort((a, b) => (RISK_RANK[b.risk] || 0) - (RISK_RANK[a.risk] || 0));
      setResults(sorted);
      setSummary(calcSummary(sorted));
      setQuery(item.query_sql);
      window.history.pushState({ view: 'result' }, '');
      setHasResult(true);
      setApiStatus('connected');
    } catch (e) {
      console.error('히스토리 로드 실패:', e);
    }
  }, []);

  const theme = useMemo(() => ({
    bg:       isDarkMode ? 'bg-[#171615]' : 'bg-zinc-200',
    card:     isDarkMode ? 'bg-[#1a1a1a] border-[#2d2d2d]' : 'bg-white border-zinc-200',
    text:     isDarkMode ? 'text-[#e0e0e0]' : 'text-zinc-800',
    subText:  isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500',
    button:   isDarkMode ? 'bg-[#e0e0e0] text-[#121212] hover:bg-white' : 'bg-zinc-800 text-white hover:bg-zinc-700',
    textarea: isDarkMode ? 'bg-[#1a1a1a] text-[#e0e0e0] placeholder:text-[#555555]' : 'bg-white text-zinc-800 placeholder:text-zinc-400',
  }), [isDarkMode]);

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

    setIsExiting(true);
    await new Promise(r => setTimeout(r, 280));

    window.history.pushState({ view: 'result' }, '');
    setLoading(true);
    setHasResult(true);
    setIsExiting(false);
    setResults([]);
    setSummary(null);
    setApiStatus('idle');
    setTotalCount(sqls.length);

    await new Promise(r => setTimeout(r, 420));

    const analysisResults = [];
    let successCount = 0;

    let mockData = null;
    if (IS_MOCK) {
      const mod = await import('./data/mock_diagnose_result.json');
      mockData = mod.default;
    }

    const { fetchDiagnose, getOfflineCache } = IS_MOCK ? {} : await import('./api/diagnose');

    setIsOfflineCache(false);

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
          try {
            const cached = await getOfflineCache(sqls[i]);
            result = processApiResult(cached, sqls[i], i);
            setIsOfflineCache(true);
          } catch {
            result = analyzeSQL(sqls[i], i);
          }
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
    mock:      { cls: 'bg-[#1e1e1e] text-[#666666]',     dot: 'bg-[#3a3a3a]', label: '오프라인(mock)' },
  }[apiStatus] ?? null;

  if (page === 'prediction') {
    return (
      <div className={`transition-all duration-300 ${sidebarOpen ? 'ml-64' : 'ml-12'}`}>
        <Sidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(v => !v)}
          historyItems={historyItems}
          user={user}
          isDarkMode={isDarkMode}
          onSelectHistory={handleSelectHistory}
          onNewAnalysis={() => { setPage('main'); handleNewAnalysis(); }}
          onLogout={handleLogout}
          onDeleteHistory={handleDeleteHistory}
        />
        <PredictionLogDashboard
          isDarkMode={isDarkMode}
          onClose={() => setPage('main')}
        />
      </div>
    );
  }

  return (
    <div className={`min-h-screen ${theme.bg} ${theme.text} font-sans transition-colors duration-700`}>

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

      {/* 오프라인 캐시 배너 */}
      {isOfflineCache && (
        <div className="fixed top-0 left-0 right-0 z-50 flex items-center justify-center gap-2 py-2 text-xs font-medium bg-yellow-500/90 text-yellow-950 backdrop-blur-sm">
          <AlertTriangle size={13} />
          네트워크 오류 — 오프라인 캐시 응답을 사용 중입니다
        </div>
      )}

      {/* 우측 상단 고정 */}
      <div className="fixed top-4 right-4 z-40 flex items-center gap-2">
        {hasResult && statusBadge && (
          <div className={`flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full border font-medium ${statusBadge.cls} ${isDarkMode ? 'border-[#2d2d2d]' : 'border-zinc-300'}`}>
            <div className={`w-1.5 h-1.5 rounded-full animate-pulse ${statusBadge.dot}`} />
            {statusBadge.label}
          </div>
        )}
        <div className={`flex items-center gap-1 p-1 rounded-xl border ${isDarkMode ? 'bg-[#111111]/80 border-[#2d2d2d]' : 'bg-white/80 border-zinc-200'} backdrop-blur-sm`}>
          <button
            onClick={() => setShowHelp(true)}
            title="사용 가이드"
            className={`p-1.5 rounded-lg transition-all hover:scale-105 ${
              isDarkMode ? 'hover:bg-[#1e1e1e] text-[#a0a0a0] hover:text-[#e0e0e0]' : 'hover:bg-zinc-100 text-zinc-500 hover:text-zinc-700'
            }`}
          >
            <HelpCircle size={16} />
          </button>
          <div className={`w-px h-4 ${isDarkMode ? 'bg-[#2d2d2d]' : 'bg-zinc-200'}`} />
          <button
            onClick={() => { const next = !isDarkMode; setIsDarkMode(next); localStorage.setItem('darkMode', next); }}
            className={`p-1.5 rounded-lg transition-all hover:scale-105 ${
              isDarkMode ? 'hover:bg-[#1e1e1e] text-[#a0a0a0] hover:text-[#e0e0e0]' : 'hover:bg-zinc-100 text-zinc-500 hover:text-zinc-700'
            }`}
          >
            {isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </div>
      </div>

      {/* ── 초기 화면 ── */}
      {(!hasResult || isExiting) && (
        <div className={`min-h-screen flex flex-col items-center justify-center px-6 ${isExiting ? 'animate-fade-out-up' : ''}`}>
          <div className="relative z-10 w-full max-w-3xl">

            {/* 타이틀 영역 */}
            <div className="mb-7 text-center">
              <h1 className={`animate-slide-up text-4xl font-bold tracking-tight mb-2.5 bg-linear-to-b bg-clip-text text-transparent ${
                isDarkMode
                  ? 'from-white via-zinc-100 to-zinc-500'
                  : 'from-zinc-900 via-zinc-700 to-zinc-500'
              }`}>
                AI 쿼리 진단
              </h1>
              <p className={`animate-slide-up-delay text-sm ${theme.subText}`}>
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
              <span
                className={`animate-fade-in text-xs shrink-0 ${theme.subText}`}
                style={{ animationDelay: '0.15s' }}
              >예제:</span>
              {EXAMPLE_QUERIES.map(({ label, sql }, i) => (
                <button
                  key={label}
                  onClick={() => setQuery(sql)}
                  style={{ animationDelay: `${0.2 + i * 0.05}s` }}
                  className={`animate-fade-in text-xs px-3 py-1.5 rounded-lg border transition-all hover:scale-105 active:scale-95 shrink-0 ${
                    isDarkMode
                      ? 'bg-[#111111] border-[#2d2d2d] text-[#666666] hover:bg-[#1e1e1e] hover:text-[#c0c0c0] hover:border-[#3a3a3a]'
                      : 'bg-zinc-50 border-zinc-200 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-700 hover:border-zinc-300'
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* 카탈로그 링크 — 예제 아래 */}
            <div
              className="animate-fade-in mt-4 flex justify-center"
              style={{ animationDelay: '0.55s' }}
            >
              <button
                onClick={() => setShowCatalog(true)}
                className={`inline-flex items-center gap-2 text-xs px-4 py-2 rounded-full border transition-all hover:scale-105 ${
                  isDarkMode
                    ? 'border-[#2d2d2d] text-[#666666] hover:border-[#3a3a3a] hover:text-[#c0c0c0] hover:bg-[#1e1e1e]/50'
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
      {hasResult && !isExiting && (
        <div className="animate-fade-in-up max-w-3xl mx-auto px-6 py-10">
          <div className="mb-6">
            <h1 className={`animate-slide-up text-xl font-bold bg-linear-to-r bg-clip-text text-transparent ${
              isDarkMode ? 'from-white to-zinc-400' : 'from-zinc-900 to-zinc-500'
            }`}>AI 쿼리 진단</h1>
            <p className={`animate-slide-up-delay text-xs ${theme.subText}`}>Oracle → MySQL 이관 위험도 분석</p>
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
                <span className={`dot-1 w-2.5 h-2.5 rounded-full ${isDarkMode ? 'bg-[#a0a0a0]' : 'bg-zinc-600'}`} />
                <span className={`dot-2 w-2.5 h-2.5 rounded-full ${isDarkMode ? 'bg-[#a0a0a0]' : 'bg-zinc-600'}`} />
                <span className={`dot-3 w-2.5 h-2.5 rounded-full ${isDarkMode ? 'bg-[#a0a0a0]' : 'bg-zinc-600'}`} />
              </div>
              <p className={`text-sm font-medium ${theme.subText}`}>
                {totalCount > 1 ? `${totalCount}개 쿼리 분석 중...` : '쿼리 분석 중...'}
              </p>
            </div>
          )}

          {/* 결과 목록 — 로딩 중에도 나온 결과 즉시 표시 */}
          {results.length > 0 && (
            <div className="flex flex-col gap-4">
              {results.length >= 1 && summary && (
                <BatchSummary summary={summary} results={results} isDarkMode={isDarkMode} />
              )}

              {/* 스트리밍 진행 표시 */}
              {loading && (
                <div className="flex items-center gap-3 px-1">
                  <div className="flex items-end gap-1">
                    <span className={`dot-1 w-1.5 h-1.5 rounded-full ${isDarkMode ? 'bg-[#a0a0a0]' : 'bg-zinc-600'}`} />
                    <span className={`dot-2 w-1.5 h-1.5 rounded-full ${isDarkMode ? 'bg-[#a0a0a0]' : 'bg-zinc-600'}`} />
                    <span className={`dot-3 w-1.5 h-1.5 rounded-full ${isDarkMode ? 'bg-[#a0a0a0]' : 'bg-zinc-600'}`} />
                  </div>
                  <span className={`text-xs ${theme.subText}`}>
                    {results.length} / {totalCount}개 완료 · 분석 중...
                  </span>
                </div>
              )}

              {!loading && results.length >= 1 && (
                <div className="flex items-center gap-2 px-1">
                  <Zap size={12} className={isDarkMode ? 'text-[#666666]' : 'text-zinc-500'} />
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
