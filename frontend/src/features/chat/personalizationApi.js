import { API_ENDPOINTS } from '@/shared/constant/endpoints';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const E = API_ENDPOINTS.MEMORY;

// Mirrors billingApi.js / reviewsApi.js refresh-on-401 pattern.
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

const authHeaders = (token) => ({
  'Content-Type': 'application/json',
  Authorization: `Bearer ${token}`,
});

export const personalizationApi = {
  getInstructions: (token) => _req(E.INSTRUCTIONS, { headers: authHeaders(token) }),

  saveInstructions: (token, { call_name, instructions }) =>
    _req(E.INSTRUCTIONS, {
      method: 'PUT',
      headers: authHeaders(token),
      body: JSON.stringify({ call_name, instructions }),
    }),
};
