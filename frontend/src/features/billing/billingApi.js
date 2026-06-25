import { API_ENDPOINTS } from '@/shared/constant/endpoints';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const E = API_ENDPOINTS.BILLING;

// Mirrors reviewsApi.js's refresh-on-401 pattern.
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

export const billingApi = {
  getMe: (token) => _req(E.ME, { headers: authHeaders(token) }),

  checkoutSubscription: (token, tier) =>
    _req(E.CHECKOUT_SUBSCRIPTION, {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ tier }),
    }),

  checkoutTopup: (token, pack) =>
    _req(E.CHECKOUT_TOPUP, {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ pack }),
    }),

  downgrade: (token, tier) =>
    _req(E.DOWNGRADE, {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ tier }),
    }),

  getTransaction: (token, id) => _req(E.TRANSACTION(id), { headers: authHeaders(token) }),
};
