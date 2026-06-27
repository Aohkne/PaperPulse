import { API_ENDPOINTS } from '@/shared/constant/endpoints';

const E = API_ENDPOINTS.ADMIN;

async function get(url, token, params = {}) {
  const qs = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
  ).toString();
  const res = await fetch(qs ? `${url}?${qs}` : url, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

async function post(url, token, body = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export const adminApi = {
  getStats: (token) => get(E.STATS, token),

  getUsers: (token, { page = 1, limit = 10, search, role, is_banned } = {}) =>
    get(E.USERS, token, { page, limit, search, role, is_banned }),

  getActivity: (token, { page = 1, limit = 10, event_type, since } = {}) =>
    get(E.ACTIVITY, token, { page, limit, event_type, since }),

  banUser: (token, id, reason) => post(E.USER_BAN(id), token, { reason }),
  unbanUser: (token, id) => post(E.USER_UNBAN(id), token, {}),

  getBillingAccounts: (token, { page = 1, limit = 10, search } = {}) =>
    get(E.BILLING_ACCOUNTS, token, { page, limit, search }),
  resetUsage: (token, id) => post(E.USAGE_RESET(id), token, {}),
  topupUsage: (token, id, { lr = 0, pdf = 0, gap = 0 } = {}) =>
    post(E.USAGE_TOPUP(id), token, { lr, pdf, gap }),

  getContributions: (token, { status, page = 1, limit = 20 } = {}) =>
    get(E.CONTRIBUTIONS, token, { status, page, limit }),
  approveContribution: (token, id) => post(E.CONTRIBUTION_APPROVE(id), token, {}),
  rejectContribution: (token, id, reason) => post(E.CONTRIBUTION_REJECT(id), token, { reason }),

  getRevenue: (token) => get(E.REVENUE, token),
};
