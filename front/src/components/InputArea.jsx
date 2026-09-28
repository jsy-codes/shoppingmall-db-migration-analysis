import { Upload, FileText, X, Search } from 'lucide-react';

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
      <div className={`input-panel rounded-2xl border overflow-hidden transition-all duration-300 ${isDarkMode ? 'bg-[#1E1D1C] border-[#2d2d2d]' : 'bg-white border-zinc-200'}`}>

        {/* 파일명 표시 */}
        {fileName && (
          <div className={`flex items-center gap-2 px-4 py-2 border-b ${
            isDarkMode ? 'border-[#2d2d2d] bg-[#1e1e1e]/40' : 'border-zinc-200 bg-zinc-100'
          }`}>
            <FileText size={13} className={`shrink-0 ${isDarkMode ? 'text-[#a0a0a0]' : 'text-zinc-500'}`} />
            <span className={`text-xs font-mono flex-1 truncate ${isDarkMode ? 'text-[#c0c0c0]' : 'text-zinc-600'}`}>{fileName}</span>
            <button onClick={clearFile} className={`transition-colors ${isDarkMode ? 'text-[#666666] hover:text-[#e0e0e0]' : 'text-zinc-400 hover:text-zinc-600'}`}>
              <X size={13} />
            </button>
          </div>
        )}

        {/* textarea + 드래그앤드롭 */}
        <div
          onDrop={(e) => { e.preventDefault(); setDragOver(false); handleFile(e.dataTransfer.files[0]); }}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          className={`relative transition-all ${dragOver ? isDarkMode ? 'bg-[#2a2a2a]/40' : 'bg-zinc-100/60' : ''}`}
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
              <div className={`flex items-center gap-2 text-xs font-semibold px-4 py-2.5 rounded-full border backdrop-blur-sm ${isDarkMode ? 'bg-[#1e1e1e]/80 border-[#2d2d2d] text-[#e0e0e0]' : 'bg-white/80 border-zinc-300 text-zinc-700'}`}>
                <Upload size={13} />
                파일을 놓으면 업로드됩니다
              </div>
            </div>
          )}
        </div>

        {/* 하단 바 */}
        <div className={`flex items-center justify-between px-4 py-2.5 border-t ${
          isDarkMode ? 'border-[#2d2d2d] bg-[#111111]/60' : 'border-zinc-200 bg-zinc-50/80'
        }`}>
          <div className="flex items-center gap-2.5">
            <button
              onClick={() => fileInputRef.current?.click()}
              className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-lg transition-all ${
                isDarkMode
                  ? 'text-[#666666] hover:text-[#e0e0e0] hover:bg-[#1e1e1e]'
                  : 'text-zinc-400 hover:text-zinc-600 hover:bg-zinc-200'
              }`}
            >
              <Upload size={13} />
              파일 업로드
            </button>
            <input ref={fileInputRef} type="file" accept=".sql,.txt" className="hidden"
              onChange={e => handleFile(e.target.files[0])} />
            {sqlCount > 0 && (
              <span className={`text-xs px-2.5 py-1 rounded-full font-mono font-medium border ${isDarkMode ? 'bg-[#1e1e1e] text-[#c0c0c0] border-[#2d2d2d]' : 'bg-zinc-100 text-zinc-600 border-zinc-300'}`}>
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
                ? 'bg-[#e0e0e0] text-[#121212] hover:bg-white shadow-black/30'
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

export default InputArea;
