import { create } from 'zustand';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

// warm-start disabled (Lưu ý 2) — re-enable later
// import useResearchStore from '@/shared/store/useResearchStore';

const authHeader = () => ({ Authorization: `Bearer ${useAuthStore.getState().token}` });

const useGapStore = create((set) => ({
  // ── State ──────────────────────────────────────────────────────────────
  gapReport: null,       // full GapReport object from API
  gapNarrative: null,    // backward-compat alias (GapResultPanel reads this)
  gapLoading: false,
  gapError: null,
  streamEvents: [],      // SSE events for progress UI

  // ── Cold-start action (TIP-G07) ────────────────────────────────────────
  /**
   * POST /api/gap {topic} → GapReport.
   * Completely decoupled from useResearchStore.
   */
  findGapsFromTopic: async (topic) => {
    const trimmed = (topic || '').trim();
    if (!trimmed || trimmed.length < 3) {
      set({ gapError: 'Please enter a topic of at least 3 characters.', gapLoading: false });
      return;
    }

    set({ gapLoading: true, gapError: null, gapReport: null, gapNarrative: null });

    try {
      const res = await fetch('/api/gap', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ topic: trimmed }),
      });

      if (!res.ok) {
        let detail = `Error ${res.status}`;
        try { detail = (await res.json()).detail ?? detail; } catch { /* no JSON body */ }
        throw new Error(detail);
      }

      const data = await res.json();
      set({
        gapReport: data,
        gapNarrative: data.narrative ?? null,
        gapLoading: false,
      });
    } catch (e) {
      set({ gapError: e.message ?? 'An unknown error occurred.', gapLoading: false });
    }
  },

  streamGaps: async (topic) => {
    const trimmed = (topic || '').trim();
    if (!trimmed || trimmed.length < 3) {
      set({ gapError: 'Please enter a topic of at least 3 characters.', gapLoading: false });
      return;
    }

    set({ gapLoading: true, gapError: null, gapReport: null, gapNarrative: null, streamEvents: [] });

    try {
      const res = await fetch(`/api/gap/stream?topic=${encodeURIComponent(trimmed)}`, {
        headers: { ...authHeader() },
      });
      if (!res.ok) {
        let detail = `Error ${res.status}`;
        try { detail = (await res.json()).detail ?? detail; } catch { /* no JSON body */ }
        throw new Error(detail);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop();

        for (const part of parts) {
          const line = part.split('\n').find(l => l.startsWith('data: '));
          if (!line) continue;
          
          try {
            const event = JSON.parse(line.slice(6));
            if (event.type === 'node_start') {
              set(s => ({ streamEvents: [...s.streamEvents, event] }));
            } else if (event.type === 'done') {
              const report = event.report;
              set(s => ({ 
                streamEvents: [...s.streamEvents, event],
                gapReport: report,
                gapNarrative: report?.narrative ?? null,
                gapLoading: false 
              }));
            } else if (event.type === 'insufficient') {
              set({ gapNarrative: event.narrative, gapLoading: false });
            } else if (event.type === 'error') {
              set({ gapError: event.message, gapLoading: false });
            }
          } catch (err) {
            console.error('Failed to parse SSE event', err, line);
          }
        }
      }
    } catch (e) {
      set({ gapError: e.message ?? 'An unknown error occurred.', gapLoading: false });
    }
  },


  // ── warm-start disabled (Lưu ý 2) — re-enable later ───────────────────
  // findResearchGaps: async () => {
  //   const { papers, snowballedPapers, setActivePanel } = useResearchStore.getState();
  //   const merged = [];
  //   const seen = new Set();
  //   for (const p of [...papers, ...snowballedPapers]) {
  //     if (p.paperId && !seen.has(p.paperId)) {
  //       seen.add(p.paperId);
  //       merged.push({ paper_id: p.paperId, title: p.title, year: p.year ?? null, url: p.url ?? null });
  //     }
  //   }
  //   setActivePanel('gaps');
  //   set({ gapLoading: true, gapError: null });
  //   try {
  //     const res = await fetch('/api/gap', {
  //       method: 'POST',
  //       headers: { 'Content-Type': 'application/json' },
  //       body: JSON.stringify({ papers: merged }),
  //     });
  //     if (!res.ok) throw new Error(await res.text());
  //     const data = await res.json();
  //     set({ gapNarrative: data.narrative, gapLoading: false });
  //   } catch (e) {
  //     set({ gapError: e.message, gapLoading: false });
  //   }
  // },

  reset: () => set({ gapReport: null, gapNarrative: null, gapLoading: false, gapError: null, streamEvents: [] }),
}));

export default useGapStore;
