import { create } from 'zustand';

/**
 * Survey/Research store for the Lit Surveyor literature-review feature.
 *
 * State shape:
 *   - query      {string}  Free-text research question.
 *   - results    {Array}   Ranked list of papers returned by the backend.
 *   - status     {string}  "idle" | "loading" | "success" | "error".
 *   - error      {string|null} Last error message, if any.
 *   - history    {Array}   Recent queries (most recent first, capped).
 *
 * Actions:
 *   - setQuery   Update the current query text.
 *   - runSearch  Trigger a search; sets status and (mock) populates results.
 *   - clearResults Reset results and status back to idle.
 *   - reset      Restore the entire store to its initial state.
 */
const MAX_HISTORY = 10;

const initialState = {
  query: '',
  results: [],
  status: 'idle', // 'idle' | 'loading' | 'success' | 'error'
  error: null,
  history: [],
};

export const useSurveyStore = create((set, get) => ({
  ...initialState,

  setQuery: (query) => set({ query }),

  /**
   * Run a literature search for the current query.
   * In a real implementation this would call the FastAPI backend at
   * POST /api/survey/search. Here we simulate the network round-trip
   * so the UI can be wired up end-to-end before the backend is ready.
   *
   * @param {string} [overrideQuery] - Optional query to use instead of state.
   * @returns {Promise<void>}
   */
  runSearch: async (overrideQuery) => {
    const query = (overrideQuery ?? get().query).trim();
    if (!query) {
      set({ error: 'Please enter a research question first.', status: 'error' });
      return;
    }

    set({ status: 'loading', error: null });

    try {
      const res = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, limit: 20 }),
      });
      if (!res.ok) throw new Error(`Search failed: ${res.status}`);
      const data = await res.json();

      const results = (data.papers ?? []).map((p) => ({
        id: p.paperId,
        title: p.title,
        authors: p.authors ?? [],
        year: p.year,
        abstract: p.abstract,
        citations: p.citationCount,
        url: p.url ?? p.openAccessPdf,
      }));

      set((state) => ({
        results,
        status: 'success',
        history: [query, ...state.history].slice(0, MAX_HISTORY),
      }));
    } catch (err) {
      set({
        status: 'error',
        error: err?.message ?? 'Something went wrong while searching.',
      });
    }
  },

  clearResults: () => set({ results: [], status: 'idle', error: null }),

  reset: () => set({ ...initialState, history: [...get().history] }),
}));
