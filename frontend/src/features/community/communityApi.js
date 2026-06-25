import { API_ENDPOINTS } from '@/shared/constant/endpoints';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const E = API_ENDPOINTS.COMMUNITY;

// Same 401-retry pattern as reviewsApi.js — vote/submit calls can outlive a
// short-lived access token.
async function _fetchWithRefresh(url, options) {
  let res = await fetch(url, options);
  if (res.status !== 401) return res;

  let newToken;
  try {
    newToken = await useAuthStore.getState().refreshAccessToken();
  } catch {
    throw new Error('Session expired — please log in again.');
  }
  return fetch(url, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${newToken}` },
  });
}

async function _req(url, options = {}) {
  const res = await _fetchWithRefresh(url, options);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

const authHeaders = (token) => (token ? { Authorization: `Bearer ${token}` } : {});
const jsonHeaders = (token) => ({ 'Content-Type': 'application/json', ...authHeaders(token) });

export const communityApi = {
  // token is optional — anonymous browsing of the public feed is allowed
  list: (token, { sort = 'new', page = 1, limit = 10 } = {}) => {
    const params = new URLSearchParams({ sort, page, limit });
    return _req(`${E.LIST}?${params}`, { headers: authHeaders(token) });
  },

  get: (token, id) => _req(E.ITEM(id), { headers: authHeaders(token) }),

  create: (token, { title, content, review_id }) =>
    _req(E.LIST, {
      method: 'POST',
      headers: jsonHeaders(token),
      body: JSON.stringify({ title, content, review_id }),
    }),

  update: (token, id, patch) =>
    _req(E.ITEM(id), { method: 'PATCH', headers: jsonHeaders(token), body: JSON.stringify(patch) }),

  delete: (token, id) => _req(E.ITEM(id), { method: 'DELETE', headers: authHeaders(token) }),

  vote: (token, id) => _req(E.VOTE(id), { method: 'POST', headers: jsonHeaders(token) }),

  leaderboard: (limit = 20) => _req(`${E.LEADERBOARD}?limit=${limit}`),
};
