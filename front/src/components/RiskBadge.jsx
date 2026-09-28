import { getRiskConfig } from '../utils/risk';

// ─── 공통 컴포넌트 ────────────────────────────────────────────
function RiskBadge({ risk, score, isDarkMode = true }) {
  const cfg = getRiskConfig(isDarkMode)[risk] || getRiskConfig(isDarkMode).LOW;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.text} border ${cfg.border}`}>
      {cfg.icon} {cfg.label} {score != null ? `· ${score}` : ''}
    </span>
  );
}

export default RiskBadge;
