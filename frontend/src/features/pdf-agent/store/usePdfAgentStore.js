import { create } from 'zustand';
import { pdfAgentApi, consumeUploadStream } from '@/features/pdf-agent/pdfAgentApi';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const getToken = () => useAuthStore.getState().token;

export const usePdfAgentStore = create((set, get) => ({
  docId: null,
  title: '',
  status: 'idle', // idle | uploading | streaming | ready | error | saving
  steps: [], // [{node, label, status: 'running'|'done', stats}]
  texContent: '',
  annotations: [],
  error: null,
  reviewId: null,
  selectionResult: null, // {explanation} | {oldText, newText} while a /explain or /rewrite is showing

  reset: () =>
    set({
      docId: null, title: '', status: 'idle', steps: [], texContent: '',
      annotations: [], error: null, reviewId: null, selectionResult: null,
    }),

  upload: async (file) => {
    set({
      status: 'uploading', error: null, steps: [], docId: null, annotations: [],
      texContent: '', reviewId: null, title: file.name.replace(/\.[^.]+$/, ''),
    });
    try {
      const res = await pdfAgentApi.upload(getToken(), file);
      set({ status: 'streaming' });
      await consumeUploadStream(res, (event) => get()._handleSSEEvent(event));
    } catch (e) {
      set({ status: 'error', error: e.message || 'Upload failed' });
    }
  },

  _handleSSEEvent: (event) => {
    switch (event.type) {
      case 'doc_id':
        set({ docId: event.doc_id });
        break;
      case 'step_start':
        set((s) => ({
          steps: [...s.steps.filter((st) => st.node !== event.node), { node: event.node, label: event.label, status: 'running' }],
        }));
        break;
      case 'step_done':
        set((s) => ({
          steps: s.steps.map((st) => (st.node === event.node ? { ...st, status: 'done', stats: event.stats } : st)),
        }));
        break;
      case 'error':
        set({ status: 'error', error: event.message });
        break;
      case 'done':
        get()._finishUpload();
        break;
      default:
        break; // heartbeat — ignored
    }
  },

  _finishUpload: async () => {
    const { docId } = get();
    if (!docId) {
      set({ status: 'error', error: 'Did not receive doc_id from server' });
      return;
    }
    try {
      const token = getToken();
      const [annosRes, contentRes] = await Promise.all([
        pdfAgentApi.listAnnotations(token, docId),
        pdfAgentApi.getContent(token, docId),
      ]);
      set({ status: 'ready', annotations: annosRes.annotations, texContent: contentRes.tex_content });
    } catch (e) {
      set({ status: 'error', error: e.message || 'Failed to load results' });
    }
  },

  loadFromResume: ({ docId, title, annotations, texContent }) => {
    set({ docId, title, annotations, texContent, status: 'ready', error: null, steps: [] });
  },

  setTexContent: (text) => set({ texContent: text }),
  setTitle: (title) => set({ title }),

  /** Push the live buffer to the server — required before accept/apply/save read or
   * write the server's copy of main.tex (see api/bundle.py sync_content docstring). */
  _syncBuffer: async () => {
    const { docId, texContent } = get();
    await pdfAgentApi.syncContent(getToken(), docId, texContent);
  },

  updateAnnotation: async (annotationId, action) => {
    const { docId } = get();
    await get()._syncBuffer();
    const res = await pdfAgentApi.updateAnnotation(getToken(), docId, annotationId, action);
    set((s) => ({
      annotations: s.annotations.map((a) => (a.id === annotationId ? { ...a, status: res.status } : a)),
      texContent: res.tex_content,
    }));
  },

  explainSelection: async (selection) => {
    const { docId } = get();
    set({ selectionResult: { loading: true, kind: 'explain' } });
    try {
      const res = await pdfAgentApi.explain(getToken(), docId, selection);
      set({ selectionResult: { kind: 'explain', explanation: res.explanation } });
    } catch (e) {
      set({ selectionResult: { kind: 'error', message: e.message } });
    }
  },

  rewriteSelection: async (selection, instruction) => {
    const { docId } = get();
    set({ selectionResult: { loading: true, kind: 'rewrite' } });
    try {
      const res = await pdfAgentApi.rewrite(getToken(), docId, { ...selection, instruction });
      set({ selectionResult: { kind: 'rewrite', oldText: res.old_text, newText: res.new_text } });
    } catch (e) {
      set({ selectionResult: { kind: 'error', message: e.message } });
    }
  },

  applyRewrite: async () => {
    const { docId, selectionResult } = get();
    if (!selectionResult || selectionResult.kind !== 'rewrite') return;
    await get()._syncBuffer();
    const res = await pdfAgentApi.apply(getToken(), docId, {
      oldText: selectionResult.oldText,
      newText: selectionResult.newText,
    });
    set({ texContent: res.tex_content, selectionResult: null });
  },

  clearSelectionResult: () => set({ selectionResult: null }),

  saveToReview: async () => {
    const { docId, title, texContent } = get();
    set({ status: 'saving' });
    try {
      const res = await pdfAgentApi.save(getToken(), docId, title, texContent);
      set({ status: 'ready', reviewId: res.id });
      return res;
    } catch (e) {
      set({ status: 'ready', error: e.message || 'Save failed' });
      throw e;
    }
  },
}));
