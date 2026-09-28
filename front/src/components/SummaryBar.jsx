// ─── 요약 바 (위험도 분포) ─────────────────────────────────────
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

export default SummaryBar;
