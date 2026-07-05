import { create } from 'zustand';
import { escapeLatex } from '@/shared/utils/latex';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const BASE_URL = import.meta.env.VITE_API_URL ?? '';
const token = () => useAuthStore.getState().token;

// ── Step labels (pipeline Steps 0→10) ───────────────────────────────────────
const STEP_LABELS = {
  0: 'Analyzing intent',
  1: 'Searching papers',
  2: 'Removing duplicates',
  3: 'Citation snowball',
  4: 'Building embeddings',
  5: 'Generating outline',
  6: 'Writing sections',
  7: 'Extracting claims',
  8: 'Verifying claims',
  9: 'Routing claims',
  10: 'Exporting LaTeX',
};

const SSE_STEP_IDX = {
  0: 0,
  1: 1,
  2: 2,
  3: 3,
  4: 4,
  5: 5,
  6: 6,
  7: 7,
  8: 8,
  9: 9,
  10: 10,
};

const initialSteps = Object.fromEntries(Object.keys(STEP_LABELS).map((k) => [Number(k), 'idle']));

// ── SSE parser ───────────────────────────────────────────────────────────────
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
          try {
            yield JSON.parse(line.slice(6));
          } catch {
            /* skip */
          }
        }
      }
    }
  }
}

// ── Store ────────────────────────────────────────────────────────────────────
const useResearchStore = create((set, get) => ({
  // ── Core ────────────────────────────────────────────────────────────────────
  query: '',
  steps: { ...initialSteps },
  stepLabels: STEP_LABELS,
  error: null,
  quotaExceeded: false, // true on HTTP 402 — UI should prompt the user to upgrade
  activePanel: 'outline',

  // ── Pipeline state ───────────────────────────────────────────────────────────
  threadId: null,
  v2Running: false,
  pendingInterrupt: null, // null | { type: 'outline'|'routing', data }
  stepLog: [], // [{ stepNum, content, stat }]

  // ── Step 0 conversational states ────────────────────────────────────────────
  // mode: 'idle' | 'thinking' | 'replying' | 'greeting' | 'clarify' | 'pipeline'
  conversationMode: 'idle',
  thinkingText: '', // streaming tokens from intent_router (WHY this intent)
  replyText: '', // streaming tokens from reply_generator (the actual response)
  greetingReply: null, // string — complete reply shown after streaming
  clarifyQuestions: [], // list of strings — shown for user to answer
  conversationHistory: [], // [{role:'user'|'assistant', content}] — for multi-turn
  refinedQuery: '', // LLM-optimised search string (search intent)
  planDescription: '', // one-sentence plan description (search intent)
  stepTokens: {}, // { [stepNum: string]: string } — streaming narrator tokens per step

  // ── Research content ─────────────────────────────────────────────────────────
  papers: [],
  snowballedPapers: [],
  themes: [],
  themeContents: {},
  themeLoadingSet: new Set(),
  claims: [],
  reviewLatex: null,
  bibContent: null,

  // ── Helpers ──────────────────────────────────────────────────────────────────
  _setStep: (n, status) => set((s) => ({ steps: { ...s.steps, [n]: status } })),

  setQuery: (q) => set({ query: q }),
  setActivePanel: (p) => set({ activePanel: p }),

  // ── SSE event dispatcher ─────────────────────────────────────────────────────
  _handleEvent: (event) => {
    const { _setStep, steps } = get();

    switch (event.type) {
      case 'thread_id':
        set({ threadId: event.thread_id });
        break;

      // ── Pipeline step narrator token stream ──
      case 'step_token':
        set((s) => ({
          stepTokens: {
            ...s.stepTokens,
            [event.stepNum]: (s.stepTokens[event.stepNum] || '') + event.content,
          },
        }));
        break;

      // ── Step 0a: intent_router reasoning stream ──
      case 'thinking_token':
        set((s) => ({
          thinkingText: s.thinkingText + event.content,
          conversationMode: 'thinking',
        }));
        break;

      // ── Step 0b: reply_generator response stream ──
      // Fires for both greeting replies and clarify questions as they stream
      case 'reply_token':
        set((s) => ({
          replyText: s.replyText + event.content,
          conversationMode: 'replying',
        }));
        break;

      // ── Step 0: greeting complete (after reply_token stream) ──
      case 'greeting':
        set({
          greetingReply: event.content,
          conversationMode: 'greeting',
          v2Running: false,
          replyText: '', // streaming done — final text now in greetingReply
        });
        _setStep(0, 'done');
        break;

      // ── Step 0: clarify complete (after reply_token stream) ──
      case 'clarify':
        set((s) => ({
          clarifyQuestions: event.questions || [],
          conversationMode: 'clarify',
          v2Running: false,
          replyText: '', // streaming done
          conversationHistory: [
            ...s.conversationHistory,
            { role: 'assistant', content: event.questions.join('\n') },
          ],
        }));
        _setStep(0, 'done');
        break;

      // ── Pipeline step progress ──
      case 'step': {
        const idx = SSE_STEP_IDX[event.stepNum];
        if (idx !== undefined) {
          for (let i = 0; i < idx; i++) {
            if (steps[i] === 'idle' || steps[i] === 'loading') _setStep(i, 'done');
          }
          _setStep(idx, 'done');
          if (steps[idx + 1] === 'idle') _setStep(idx + 1, 'loading');
        }
        const storeUpdate = {
          conversationMode: 'pipeline',
          stepLog: undefined, // set below
        };
        // Step 0 carries the refined query and plan description
        if (event.stepNum === '0') {
          if (event.refined_query) storeUpdate.refinedQuery = event.refined_query;
          if (event.plan_description) storeUpdate.planDescription = event.plan_description;
        }
        set((s) => ({
          ...storeUpdate,
          stepLog: [
            ...s.stepLog,
            { stepNum: event.stepNum, content: event.content, stat: event.stat },
          ].slice(-60),
        }));
        break;
      }

      // ── Interrupt (outline ④ or routing ⑨) ──
      case 'interrupt': {
        const data = event.data || {};
        if (data.themes) {
          set({
            themes: data.themes,
            pendingInterrupt: { type: 'outline', data },
            activePanel: 'outline',
            v2Running: false,
          });
          _setStep(5, 'interrupt');
        } else if ('included' in data || 'removed' in data) {
          set({ pendingInterrupt: { type: 'routing', data }, v2Running: false });
          _setStep(9, 'interrupt');
        }
        break;
      }

      // ── Pipeline complete ──
      case 'done':
        _setStep(10, 'done');
        set({
          reviewLatex: event.content,
          bibContent: event.bib || null,
          activePanel: 'review',
          v2Running: false,
          pendingInterrupt: null,
          conversationMode: 'pipeline',
        });
        break;

      case 'error':
        set({ error: event.message, v2Running: false });
        break;

      default:
        break;
    }
  },

  // ── Generic SSE consumer ──────────────────────────────────────────────────────
  _consumeStream: async (response) => {
    const { _handleEvent } = get();
    try {
      for await (const event of parseSse(response)) {
        _handleEvent(event);
      }
    } catch (err) {
      set({ error: String(err), v2Running: false });
    }
  },

  // ── Start pipeline (first turn or clarify follow-up) ─────────────────────────
  runSearch: async (query) => {
    const { _consumeStream, _setStep, conversationHistory } = get();

    // Reset pipeline state but keep conversation history for clarify flow
    set({
      query,
      error: null,
      quotaExceeded: false,
      v2Running: true,
      pendingInterrupt: null,
      thinkingText: '',
      replyText: '',
      greetingReply: null,
      clarifyQuestions: [],
      refinedQuery: '',
      planDescription: '',
      stepTokens: {},
      papers: [],
      snowballedPapers: [],
      themes: [],
      themeContents: {},
      claims: [],
      reviewLatex: null,
      bibContent: null,
      stepLog: [],
      steps: { ...initialSteps },
      activePanel: 'outline',
      conversationMode: 'thinking',
      // keep existing conversationHistory (supports clarify multi-turn)
    });
    _setStep(0, 'loading');

    // Append the new user turn to history
    const updatedHistory = [...conversationHistory, { role: 'user', content: query }];
    set({ conversationHistory: updatedHistory });

    try {
      const body = {
        query,
        // Only send history on follow-up turns (first turn: empty)
        messages: conversationHistory.length > 0 ? conversationHistory : undefined,
      };
      const res = await fetch(`${BASE_URL}/api/research/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` },
        body: JSON.stringify(body),
      });
      if (res.status === 402) {
        set({ error: await res.text(), quotaExceeded: true, v2Running: false });
        return;
      }
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      await _consumeStream(res);
    } catch (err) {
      set({ error: String(err), v2Running: false });
    }
  },

  // ── User answers clarifying questions ────────────────────────────────────────
  submitClarifyAnswer: async (answer) => {
    const { runSearch, conversationHistory, clarifyQuestions } = get();
    // Build history: prior exchanges + the clarify questions the LLM asked
    const newHistory = [
      ...conversationHistory,
      // The assistant's clarify turn (already stored in conversationHistory if clarify was saved)
    ];
    // If the last clarify questions haven't been saved yet, add them
    if (clarifyQuestions.length > 0) {
      const lastEntry = newHistory[newHistory.length - 1];
      const questionsText = clarifyQuestions.join('\n');
      if (!lastEntry || lastEntry.content !== questionsText) {
        newHistory.push({ role: 'assistant', content: questionsText });
      }
    }
    set({ conversationHistory: newHistory });
    await runSearch(answer);
  },

  // ── Start fresh (new topic) ───────────────────────────────────────────────────
  startNewTopic: () => {
    set({
      conversationHistory: [],
      greetingReply: null,
      clarifyQuestions: [],
      thinkingText: '',
      replyText: '',
      conversationMode: 'idle',
    });
  },

  // ── Resume after interrupt ────────────────────────────────────────────────────
  resumePipeline: async (resumeValue = true) => {
    const { threadId, _consumeStream } = get();
    if (!threadId) return;
    set({ pendingInterrupt: null, v2Running: true });

    try {
      const res = await fetch(`${BASE_URL}/api/research/resume`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token()}` },
        body: JSON.stringify({ thread_id: threadId, resume_value: resumeValue }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}: ${await res.text()}`);
      await _consumeStream(res);
    } catch (err) {
      set({ error: String(err), v2Running: false });
    }
  },

  // ── Export ────────────────────────────────────────────────────────────────────
  exportLatex: () => {
    const { reviewLatex } = get();
    if (!reviewLatex) return;
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([reviewLatex], { type: 'text/x-tex' })),
      download: 'literature_review.tex',
    });
    a.click();
    URL.revokeObjectURL(a.href);
  },

  exportBib: () => {
    const { bibContent } = get();
    if (!bibContent) return;
    const a = Object.assign(document.createElement('a'), {
      href: URL.createObjectURL(new Blob([bibContent], { type: 'text/plain' })),
      download: 'references.bib',
    });
    a.click();
    URL.revokeObjectURL(a.href);
  },

  exportReview: () => get().exportLatex(),

  // ── Kept for ClaimVerifier ────────────────────────────────────────────────────
  approveClaim: (id) =>
    set((s) => ({
      claims: s.claims.map((c) =>
        c.id === id ? { ...c, status: 'supported', human_review: false } : c
      ),
    })),
  rejectClaim: (id) =>
    set((s) => ({
      claims: s.claims.map((c) =>
        c.id === id ? { ...c, status: 'unsupported', human_review: false } : c
      ),
    })),
  finaliseHumanReview: () => get()._setStep(8, 'done'),

  assembleReview: () => {
    const { query, themes, themeContents } = get();
    const sections = themes
      .filter((t) => themeContents[t.title])
      .map((t) => `\\section{${escapeLatex(t.title)}}\n\n${escapeLatex(themeContents[t.title])}`)
      .join('\n\n');
    const tex = `\\documentclass[11pt]{article}\n\\usepackage[utf8]{inputenc}\n\\usepackage{amsmath,amssymb}\n\\usepackage{hyperref}\n\\usepackage[margin=1in]{geometry}\n\n\\title{Literature Review: ${escapeLatex(query)}}\n\\date{}\n\n\\begin{document}\n\\maketitle\n\n${sections}\n\n\\end{document}\n`;
    set({ reviewLatex: tex, activePanel: 'review' });
  },

  reset: () =>
    set({
      query: '',
      steps: { ...initialSteps },
      papers: [],
      snowballedPapers: [],
      themes: [],
      themeContents: {},
      themeLoadingSet: new Set(),
      claims: [],
      reviewLatex: null,
      bibContent: null,
      error: null,
      activePanel: 'outline',
      threadId: null,
      v2Running: false,
      pendingInterrupt: null,
      stepLog: [],
      thinkingText: '',
      replyText: '',
      greetingReply: null,
      clarifyQuestions: [],
      refinedQuery: '',
      planDescription: '',
      stepTokens: {},
      conversationHistory: [],
      conversationMode: 'idle',
    }),
}));

export default useResearchStore;
