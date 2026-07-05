import { API_ENDPOINTS } from '@/shared/constant/endpoints';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const E = API_ENDPOINTS.REVIEWS;

// Long-running flows (a literature review pipeline can take several minutes)
// commonly outlive the access token's TTL. On a 401 "Token expired" response,
// refresh once via the stored refresh_token and retry the same request with
// the new access token before giving up.
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

export const reviewsApi = {
  create: (token, { title, query, markdown_content }) =>
    _req(E.BASE, {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ title, query, markdown_content }),
    }),

  list: (token, { page = 1, limit = 5, search = '' } = {}) => {
    const params = new URLSearchParams({ page, limit });
    if (search) params.set('search', search);
    return _req(`${E.BASE}?${params}`, { headers: authHeaders(token) });
  },

  get: (token, id) => _req(E.ITEM(id), { headers: authHeaders(token) }),

  update: (token, id, patch) =>
    _req(E.ITEM(id), {
      method: 'PATCH',
      headers: authHeaders(token),
      body: JSON.stringify(patch),
    }),

  delete: (token, id) => _req(E.ITEM(id), { method: 'DELETE', headers: authHeaders(token) }),

  download: async (token, id, format = 'tex') => {
    const res = await _fetchWithRefresh(`${E.EXPORT(id)}?format=${format}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const disposition = res.headers.get('Content-Disposition') ?? '';
    const match = disposition.match(/filename="?([^";\n]+)"?/);
    const extension =
      format === 'pdf' ? 'pdf' : format === 'tex' ? 'tex' : format === 'zip' ? 'zip' : 'md';
    const filename = match ? match[1] : `review.${extension}`;
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },

  duplicate: (token, id, title) =>
    _req(E.DUPLICATE(id), {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify(title ? { title } : {}),
    }),
};
