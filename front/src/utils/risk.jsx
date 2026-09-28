import { AlertTriangle, Shield, Info } from 'lucide-react';

// ─── 위험도 순위 (공통 상수) ───────────────────────────────────
const RISK_RANK = { HIGH: 3, MEDIUM: 2, LOW: 1 };

// ─── 위험도 설정 ───────────────────────────────────────────────
const getRiskConfig = (isDarkMode = true) => ({
  HIGH:   { label: 'HIGH',   bg: isDarkMode ? 'bg-red-500/20'     : 'bg-red-200',     border: isDarkMode ? 'border-red-500/40'     : 'border-red-400',     text: isDarkMode ? 'text-red-400'     : 'text-red-700',     icon: <AlertTriangle size={14} />, bar: '#ef4444' },
  MEDIUM: { label: 'MEDIUM', bg: isDarkMode ? 'bg-yellow-500/20'  : 'bg-yellow-200',  border: isDarkMode ? 'border-yellow-500/40'  : 'border-yellow-400',  text: isDarkMode ? 'text-yellow-400'  : 'text-yellow-800',  icon: <Shield size={14} />,        bar: '#eab308' },
  LOW:    { label: 'LOW',    bg: isDarkMode ? 'bg-emerald-500/20' : 'bg-emerald-200', border: isDarkMode ? 'border-emerald-500/40' : 'border-emerald-400', text: isDarkMode ? 'text-emerald-400' : 'text-emerald-700', icon: <Info size={14} />,           bar: '#10b981' },
});

export { RISK_RANK, getRiskConfig };
