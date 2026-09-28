import rules from '../../../backend/validation/pattern_rules.json';
import { RISK_RANK } from './risk';

// ─── 로컬 패턴 매칭 (API 실패 시 fallback) ────────────────────

const COMPILED_RULES = rules.map(rule => ({
  ...rule,
  _regex: rule.type === 'regex' && rule.pattern
    ? new RegExp(rule.pattern, 'i')
    : null,
}));

function matchPatterns(sql) {
  const matched = [];
  for (const rule of COMPILED_RULES) { 
    if (rule._regex) {                  
      if (rule._regex.test(sql)) matched.push(rule);
    } else if (rule.type === 'heuristic') {
      if (rule.heuristic === 'implicit_cast' && /\b[A-Z_][A-Z0-9_]*\s*=\s*'\d+'/i.test(sql)) matched.push(rule);
      if (rule.heuristic === 'join_without_index' && /JOIN/i.test(sql) && !/USE INDEX|FORCE INDEX|CREATE INDEX/i.test(sql)) matched.push(rule);
      if (rule.heuristic === 'nested_subquery' && (sql.match(/SELECT/gi) || []).length >= 2) matched.push(rule);
    }
  }
  return matched;
}

function getHighestRisk(matched) {
  if (matched.length === 0) return null;
  return matched.reduce((prev, curr) => (RISK_RANK[curr.risk] || 0) > (RISK_RANK[prev.risk] || 0) ? curr : prev);
}

function calcRiskScore(matched) {
  const weights = { HIGH: 35, MEDIUM: 15, LOW: 5 };
  const raw = matched.reduce((sum, m) => sum + (weights[m.risk] || 0), 0);
  return Math.min(100, raw);
}

function splitSQLs(raw) {
  return raw.split(';').map(s => s.trim()).filter(s => s.length > 5);
}

function analyzeSQL(sql, index) {
  const matched = matchPatterns(sql);
  const score = calcRiskScore(matched);
  const top = matched.length > 0 ? getHighestRisk(matched) : null;
  return {
    index, sql, matched, top, score,
    risk: top?.risk || 'LOW',
    recommended_ddl: null, reason: null, estimated_improvement: null,
  };
}

function calcSummary(results) {
  const counts = { HIGH: 0, MEDIUM: 0, LOW: 0 };
  results.forEach(r => counts[r.risk]++);
  const avgScore = results.length ? Math.round(results.reduce((s, r) => s + r.score, 0) / results.length) : 0;
  const maxScore = results.length ? Math.max(...results.map(r => r.score)) : 0;
  return { counts, avgScore, maxScore, total: results.length };
}

function processApiResult(data, sql, index) {
  const simulatorMatched = data.simulator_detail?.[0]?.matched_patterns || [];
  const matchedRules = simulatorMatched.length > 0
    ? simulatorMatched.map(p => ({
        id: p.id, name: p.name, risk: p.severity,
        failure_type: p.failure_type, description: p.description, impact: p.impact,
        fix: data.simulator_detail?.[0]?.recommendations?.[0] || null,
      }))
    : matchPatterns(sql);

  const top = matchedRules.length > 0
    ? matchedRules.reduce((prev, curr) => (RISK_RANK[curr.risk] || 0) > (RISK_RANK[prev.risk] || 0) ? curr : prev)
    : null;

  const matchedIds = data.matched_pattern_ids || [];
  const scoreFromData = data.risk_score_data
    ? Math.max(0, ...matchedIds.map(id => {
        const d = data.risk_score_data.find(r => r.id === id);
        return d ? d.score : 0;
      }))
    : 0;

  return {
    index, sql, matched: matchedRules, top,
    score: data.risk_score || scoreFromData || { HIGH: 70, MEDIUM: 40, LOW: 10 }[data.risk_level] || 0,
    risk: data.risk_level || 'LOW',
    recommended_ddl: data.recommended_ddl || null,
    reason: data.reason || null,
    estimated_improvement: data.estimated_improvement || null,
  };
}

export { matchPatterns, getHighestRisk, calcRiskScore, splitSQLs, analyzeSQL, calcSummary, processApiResult };
