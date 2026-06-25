import { create } from 'zustand';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const BASE_URL = import.meta.env.VITE_API_URL ?? '';
const authHeader = () => ({ Authorization: `Bearer ${useAuthStore.getState().token}` });

// ── SSE parser — same protocol as useResearchStore, kept separate so this
// admin debug tool never depends on (or mutates) live app session state ──
async function* parseSse(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const blocks = buf.split('\n\n');
    buf = blocks.pop() ?? '';
    for (const block of blocks) {
      for (const line of block.split('\n')) {
        if (line.startsWith('data: ')) {
          try { yield JSON.parse(line.slice(6)); } catch { /* skip */ }
        }
      }
    }
  }
}

const makeId = () => `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

/**
 * useAdminTestStore — drives the admin "Literature Review" pipeline testing
 * page (research-agent_SPEC_2.0.md / PLAN_2.0.md §SSE Event Protocol).
 *
 * Unlike useResearchStore (which curates a polished UX), this store keeps
 * EVERY raw SSE event in a chronological `timeline` for visual inspection:
 * consecutive token events of the same stream are grouped into one growing
 * text block, while discrete events (step/interrupt/done/error/...) each
 * become their own entry — so an admin can watch both the LLM "thinking"
 * stream and the pipeline step-by-step progress as they happen.
 */
const useAdminTestStore = create((set, get) => ({
  query: '',
  setQuery: (q) => set({ query: q }),

  running: false,
  threadId: null,
  timeline: [],            // [{id, kind, stepNum?, text?, data?, ts}]
  error: null,
  pendingInterrupt: null,  // {data} — set on "interrupt" event, cleared on resume
  conversationHistory: [], // [{role, content}] — supports clarify multi-turn testing

  reset: () =>
    set({
      query: '', running: false, threadId: null, timeline: [],
      error: null, pendingInterrupt: null, conversationHistory: [],
    }),

  _appendDiscrete: (kind, data) =>
    set((s) => ({ timeline: [...s.timeline, { id: makeId(), kind, data, ts: Date.now() }] })),

  _appendToken: (kind, stepNum, content) =>
    set((s) => {
      const timeline = [...s.timeline];
      const last = timeline[timeline.length - 1];
      if (last && last.kind === kind && last.stepNum === stepNum) {
        timeline[timeline.length - 1] = { ...last, text: last.text + content };
      } else {
        timeline.push({ id: makeId(), kind, stepNum, text: content, ts: Date.now() });
      }
      return { timeline };
    }),

  _handleEvent: (event) => {
    const { _appendDiscrete, _appendToken } = get();
    switch (event.type) {
      case 'thread_id':
        set({ threadId: event.thread_id });
        break;

      case 'thinking_token':
        _appendToken('thinking_token', null, event.content);
        break;

      case 'reply_token':
        _appendToken('reply_token', null, event.content);
        break;

      case 'step_token':
        _appendToken('step_token', event.stepNum, event.content);
        break;

      case 'step':
        _appendDiscrete('step', event);
        break;

      case 'greeting':
        _appendDiscrete('greeting', event);
        set((s) => ({
          running: false,
          conversationHistory: [...s.conversationHistory, { role: 'assistant', content: event.content }],
        }));
        break;

      case 'clarify':
        _appendDiscrete('clarify', event);
        set((s) => ({
          running: false,
          conversationHistory: [
            ...s.conversationHistory,
            { role: 'assistant', content: (event.questions || []).join('\n') },
          ],
        }));
        break;

      case 'interrupt':
        _appendDiscrete('interrupt', event);
        set({ running: false, pendingInterrupt: { data: event.data } });
        break;

      case 'done':
        _appendDiscrete('done', event);
        set({ running: false });
        break;

      case 'error':
        _appendDiscrete('error', event);
        set({ error: event.message, running: false });
        break;

      default:
        _appendDiscrete(event.type ?? 'unknown', event);
    }
  },

  _consumeStream: async (response) => {
    const { _handleEvent } = get();
    try {
      for await (const event of parseSse(response)) _handleEvent(event);
    } catch (err) {
      set({ error: String(err) });
    } finally {
      set({ running: false });
    }
  },

  // First turn or a clarify follow-up — mirrors useResearchStore.runSearch,
  // but APPENDS to the existing timeline instead of clearing it, so the
  // full multi-turn conversation stays visible for inspection.
  submit: async (text) => {
    const trimmed = (text ?? '').trim();
    if (!trimmed) return;
    const { conversationHistory } = get();
    const isFollowUp = conversationHistory.length > 0;

    set((s) => ({
      query: trimmed,
      running: true,
      error: null,
      pendingInterrupt: null,
      timeline: [...s.timeline, { id: makeId(), kind: 'user_turn', text: trimmed, ts: Date.now() }],
    }));

    const updatedHistory = [...conversationHistory, { role: 'user', content: trimmed }];
    set({ conversationHistory: updatedHistory });

    try {
      const body = {
        query: trimmed,
        messages: isFollowUp ? conversationHistory : undefined,
      };
      const res = await fetch(`${BASE_URL}/api/research/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      await get()._consumeStream(res);
    } catch (err) {
      set({ error: String(err), running: false });
    }
  },

  // Resume after an interrupt (outline approval / claim routing review).
  resume: async (resumeValue = true) => {
    const { threadId } = get();
    if (!threadId) return;

    set((s) => ({
      running: true,
      pendingInterrupt: null,
      timeline: [...s.timeline, { id: makeId(), kind: 'resume_action', data: { resumeValue }, ts: Date.now() }],
    }));

    try {
      const res = await fetch(`${BASE_URL}/api/research/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ thread_id: threadId, resume_value: resumeValue }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      await get()._consumeStream(res);
    } catch (err) {
      set({ error: String(err), running: false });
    }
  },
}));

export default useAdminTestStore;
