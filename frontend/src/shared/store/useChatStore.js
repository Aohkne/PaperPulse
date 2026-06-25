import { create } from 'zustand';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const authHeader = () => ({ Authorization: `Bearer ${useAuthStore.getState().token}` });

let _seq = 0;
const makeId = () => `${++_seq}-${Math.random().toString(36).slice(2, 8)}`;

const createSession = () => ({
  id: makeId(),
  title: 'New Session',
  createdAt: new Date(),
  messages: [],
  status: 'idle', // 'idle' | 'loading' | 'awaiting_plan' | 'error'
  error: null,
  threadId: null, // LangGraph thread — needed to resume after an interrupt
});

export const useChatStore = create((set, get) => ({
  sessions: [],
  activeSessionId: null,
  sidebarOpen: true,

  newSession: () => {
    const session = createSession();
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSessionId: session.id,
    }));
    return session.id;
  },

  setActiveSession: (id) => set({ activeSessionId: id }),

  // Guarantees an active session exists, creating one on demand —
  // covers entry points that don't go through newSession (e.g. fresh page load).
  ensureActiveSession: () => {
    const { activeSessionId, sessions, newSession } = get();
    if (activeSessionId && sessions.some((s) => s.id === activeSessionId)) {
      return activeSessionId;
    }
    return newSession();
  },

  sendMessage: async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;

    const activeId = get().ensureActiveSession();
    const activeSession = get().sessions.find((s) => s.id === activeId);
    if (activeSession?.status === 'loading' || activeSession?.status === 'awaiting_plan') return;

    const userMsg = { id: makeId(), role: 'user', content: trimmed, timestamp: new Date() };
    // Placeholder assistant message — steps fill in live via SSE
    const assistantId = makeId();
    const assistantPlaceholder = {
      id: assistantId,
      role: 'assistant',
      content: '',
      steps: [],
      pendingPlan: null, // {sub_queries, sources, plan_description} while awaiting approval
      timestamp: new Date(),
    };

    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === activeId
          ? {
              ...s,
              messages: [...s.messages, userMsg, assistantPlaceholder],
              title: s.messages.length === 0 ? trimmed.slice(0, 70) : s.title,
              status: 'loading',
              error: null,
            }
          : s
      ),
    }));

    try {
      const res = await fetch('/api/research/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ query: trimmed }),
      });
      if (res.status === 402) {
        throw new Error(await res.text() || 'Literature Review quota exhausted — please upgrade your plan or top up.');
      }
      if (!res.ok) throw new Error(`Research stream failed: ${res.status}`);

      await get()._runStream(activeId, assistantId, res);
    } catch (err) {
      get()._setError(activeId, err?.message ?? 'Research pipeline failed.');
    }
  },

  // ── User approves the Step 0c research plan (sub_queries / sources) ──────────
  approvePlan: async (sessionId, plan) => {
    const session = get().sessions.find((s) => s.id === sessionId);
    if (!session?.threadId) return;
    const assistantMsg = [...session.messages].reverse().find((m) => m.role === 'assistant');
    if (!assistantMsg) return;

    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              status: 'loading',
              messages: s.messages.map((m) =>
                m.id === assistantMsg.id ? { ...m, pendingPlan: null } : m
              ),
            }
          : s
      ),
    }));

    try {
      const res = await fetch('/api/research/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ thread_id: session.threadId, resume_value: plan }),
      });
      if (!res.ok) throw new Error(`Resume failed: ${res.status}`);
      await get()._runStream(sessionId, assistantMsg.id, res);
    } catch (err) {
      get()._setError(sessionId, err?.message ?? 'Resume failed.');
    }
  },

  // ── Internal: parse one SSE response, auto-resuming interrupts EXCEPT the
  //    plan-review one (which pauses for explicit user approval). ────────────
  _runStream: async (activeId, assistantId, firstResponse) => {
    let response = firstResponse;
    while (response) {
      const { interrupted, pendingApproval } = await get()._parseStream(activeId, assistantId, response);
      if (pendingApproval) {
        set((state) => ({
          sessions: state.sessions.map((s) => (s.id === activeId ? { ...s, status: 'awaiting_plan' } : s)),
        }));
        return;
      }
      if (!interrupted) break;

      const threadId = get().sessions.find((s) => s.id === activeId)?.threadId;
      if (!threadId) break;
      response = await fetch('/api/research/resume', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ thread_id: threadId, resume_value: true }),
      });
      if (!response.ok) throw new Error(`Resume failed: ${response.status}`);
    }

    // Ensure status is idle even if 'done' was the last SSE (no trailing \n\n)
    const finalSession = get().sessions.find((s) => s.id === activeId);
    if (finalSession?.status === 'loading') {
      set((state) => ({
        sessions: state.sessions.map((s) => (s.id === activeId ? { ...s, status: 'idle' } : s)),
      }));
    }
  },

  // ── Internal: stream a single fetch Response, dispatching SSE events into
  //    the active session's assistant message. Returns whether the graph
  //    paused (interrupted) and whether that pause needs explicit user
  //    approval (plan-review) rather than auto-resume. ────────────────────────
  _parseStream: async (activeId, assistantId, response) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let interrupted = false;
    let pendingApproval = false;

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
        try { event = JSON.parse(dataLine.slice(6)); } catch { continue; }

        switch (event.type) {
          case 'thread_id':
            get()._setThreadId(activeId, event.thread_id);
            break;
          case 'thinking_token':
          case 'reply_token':
            // Chat uses the final 'greeting'/'clarify' event instead of streaming these.
            break;
          case 'greeting':
            get()._setContent(activeId, assistantId, event.content || 'Hello!');
            break;
          case 'clarify': {
            const qs = (event.questions || []).map((q, i) => `${i + 1}. ${q}`).join('\n');
            get()._setContent(activeId, assistantId, `I need a bit more context:\n\n${qs}`);
            break;
          }
          case 'step_token':
            get()._upsertRunningStep(activeId, assistantId, event.stepNum, event.content);
            break;
          case 'step':
            get()._completeStep(activeId, assistantId, event);
            break;
          case 'heartbeat':
            break; // keepalive only — no UI change
          case 'interrupt': {
            const data = event.data || {};
            if (data.sub_queries) {
              get()._setPendingPlan(activeId, assistantId, data);
              pendingApproval = true;
            } else if (data.themes) {
              get()._addStep(activeId, assistantId, {
                stepNum: '5',
                type: 'observation',
                content: `Outline ready: ${data.themes.map((t) => `"${t.title}"`).join(', ')}`,
                stat: `${data.themes.length} themes`,
              });
            }
            interrupted = true;
            break;
          }
          case 'done':
            get()._setContent(activeId, assistantId, event.content || '*(Pipeline complete — no content returned)*');
            break;
          case 'error':
            get()._setError(activeId, event.message);
            break;
          default:
            break;
        }
      }
    }
    return { interrupted, pendingApproval };
  },

  _setThreadId: (sessionId, threadId) =>
    set((state) => ({
      sessions: state.sessions.map((s) => (s.id === sessionId ? { ...s, threadId } : s)),
    })),

  _setPendingPlan: (sessionId, assistantId, data) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.id === assistantId ? { ...m, pendingPlan: data } : m
              ),
            }
          : s
      ),
    })),

  // Step started streaming its narrator sentence — create (or keep appending
  // to) a 'running' entry so ReActTrace shows a live spinner + live text.
  _upsertRunningStep: (sessionId, assistantId, stepNum, token) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) => {
            if (m.id !== assistantId) return m;
            const steps = m.steps || [];
            const idx = steps.findIndex((st) => st.stepNum === stepNum && st.status === 'running');
            if (idx === -1) {
              return {
                ...m,
                steps: [
                  ...steps,
                  { id: ++_seq, stepNum, type: 'thought', status: 'running', content: token },
                ],
              };
            }
            const next = [...steps];
            next[idx] = { ...next[idx], content: next[idx].content + token };
            return { ...m, steps: next };
          }),
        };
      }),
    })),

  // Step's "step" completion event arrived — finalise the matching running
  // entry (or add a fresh 'done' one if no narrator tokens were seen for it).
  _completeStep: (sessionId, assistantId, event) =>
    set((state) => ({
      sessions: state.sessions.map((s) => {
        if (s.id !== sessionId) return s;
        return {
          ...s,
          messages: s.messages.map((m) => {
            if (m.id !== assistantId) return m;
            const steps = m.steps || [];
            const idx = steps.findIndex((st) => st.stepNum === event.stepNum && st.status === 'running');
            const finalised = {
              id: idx === -1 ? ++_seq : steps[idx].id,
              stepNum: event.stepNum,
              type: event.step_type ?? 'observation',
              status: 'done',
              content: event.content,
              stat: event.stat,
            };
            if (idx === -1) return { ...m, steps: [...steps, finalised] };
            const next = [...steps];
            next[idx] = finalised;
            return { ...m, steps: next };
          }),
        };
      }),
    })),

  // Generic step append (used for the outline-ready announcement) — always 'done'.
  _addStep: (sessionId, assistantId, step) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              messages: s.messages.map((m) =>
                m.id === assistantId
                  ? { ...m, steps: [...(m.steps || []), { id: ++_seq, status: 'done', ...step }] }
                  : m
              ),
            }
          : s
      ),
    })),

  _setContent: (sessionId, assistantId, content) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId
          ? {
              ...s,
              status: 'idle',
              messages: s.messages.map((m) => (m.id === assistantId ? { ...m, content } : m)),
            }
          : s
      ),
    })),

  _setError: (sessionId, message) =>
    set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === sessionId ? { ...s, status: 'error', error: message } : s
      ),
    })),

  clearError: (sessionId) =>
    set((state) => ({
      sessions: state.sessions.map((s) => (s.id === sessionId ? { ...s, error: null } : s)),
    })),

  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));
