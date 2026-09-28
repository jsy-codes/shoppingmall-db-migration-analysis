// ─── Mock 설정 ─────────────────────────────────────────────────
// const IS_MOCK = import.meta.env.VITE_MOCK === 'true';
const IS_MOCK = false;

const API_BASE = 'http://localhost:8000';

const getAnonId = () => {
  let anonId = localStorage.getItem('anon_id');
  if (!anonId) {
    anonId = `anon_${Math.random().toString(36).slice(2, 14)}`;
    localStorage.setItem('anon_id', anonId);
  }
  return anonId;
};

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  if (token) return { Authorization: `Bearer ${token}` };
  return { 'X-Anon-Id': getAnonId() };
};

export { IS_MOCK, API_BASE, getAnonId, getAuthHeaders };
