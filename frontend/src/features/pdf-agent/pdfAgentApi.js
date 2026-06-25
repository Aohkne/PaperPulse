import { API_ENDPOINTS } from '@/shared/constant/endpoints';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const E = API_ENDPOINTS.PDF_AGENT;

// Same 401-refresh-and-retry pattern as reviewsApi.js.
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

export const pdfAgentApi = {
  /**
   * POST /upload — multipart file, SSE response. EventSource can't carry a
   * Bearer header, so we use fetch + ReadableStream (same workaround as
   * useChatStore.js's research stream).
   */
  upload: async (token, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch(E.UPLOAD, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail ?? `Upload failed: ${res.status}`);
    }
    return res;
  },

  getContent: (token, docId) => _req(E.CONTENT(docId), { headers: authHeaders(token) }),

  /** PUT /content — push the live editor buffer to the server before a mutating action
   * (accept/apply/save all read or write the server's copy of main.tex). */
  syncContent: (token, docId, texContent) =>
    _req(E.CONTENT(docId), {
      method: 'PUT',
      headers: authHeaders(token),
      body: JSON.stringify({ tex_content: texContent }),
    }),

  listAnnotations: (token, docId) => _req(E.ANNOTATIONS(docId), { headers: authHeaders(token) }),

  updateAnnotation: (token, docId, annotationId, action) =>
    _req(E.ANNOTATION_ITEM(docId, annotationId), {
      method: 'PATCH',
      headers: authHeaders(token),
      body: JSON.stringify({ action }),
    }),

  explain: (token, docId, { selectedText, prefix = '', suffix = '' }) =>
    _req(E.EXPLAIN(docId), {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ selected_text: selectedText, prefix, suffix }),
    }),

  rewrite: (token, docId, { selectedText, prefix = '', suffix = '', instruction = null }) =>
    _req(E.REWRITE(docId), {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ selected_text: selectedText, prefix, suffix, instruction }),
    }),

  apply: (token, docId, { oldText, newText }) =>
    _req(E.APPLY(docId), {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ old_text: oldText, new_text: newText }),
    }),

  save: (token, docId, title, texContent) =>
    _req(E.SAVE(docId), {
      method: 'POST',
      headers: authHeaders(token),
      body: JSON.stringify({ title, tex_content: texContent }),
    }),

  resume: (token, reviewId) =>
    _req(E.RESUME(reviewId), { method: 'POST', headers: authHeaders(token) }),

  bundleDownloadUrl: (docId) => E.BUNDLE(docId),

  downloadBundle: async (token, docId) => {
    const res = await _fetchWithRefresh(E.BUNDLE(docId), { headers: { Authorization: `Bearer ${token}` } });
    if (!res.ok) throw new Error(`Download failed: ${res.status}`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${docId}.zip`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

/**
 * Parse the upload SSE response body, calling `onEvent({type, ...})` for each
 * `data: {...}` line — same buffering/parsing mechanics as useChatStore.js's
 * `_parseStream` (decode chunks, split on \n\n, parse the `data: ` line).
 */
export async function consumeUploadStream(response, onEvent) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() ?? '';

    for (const part of parts) {
      const dataLine = part.split('\n').find((l) => l.startsWith('data: '));
      if (!dataLine) continue;
      let event;
      try {
        event = JSON.parse(dataLine.slice(6));
      } catch {
        continue;
      }
      onEvent(event);
    }
  }
}
