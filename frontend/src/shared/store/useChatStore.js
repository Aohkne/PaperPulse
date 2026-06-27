import { create } from 'zustand';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { API_ENDPOINTS } from '@/shared/constant/endpoints';

const authHeader = () => ({ Authorization: `Bearer ${useAuthStore.getState().token}` });

let _seq = 0;
const makeId = () => `${++_seq}-${Math.random().toString(36).slice(2, 8)}`;

let _sendInFlight = false;

const createSession = (overrides = {}) => ({
  id: makeId(),
  title: 'New Session',
  createdAt: new Date().toISOString(),
  messages: [],
  status: 'idle',
  error: null,
  threadId: null,
  persisted: false,
  feature: 'research',
  summary: null,
  lastMessageAt: null,
  ...overrides,
});

const normalizeMessage = (message) => ({
  ...message,
  timestamp: message.timestamp ?? message.created_at ?? new Date().toISOString(),
  steps: message.steps ?? [],
  pendingPlan: message.pendingPlan ?? null,
});

const normalizeNotification = (notification) => ({
  ...notification,
  created_at: notification.created_at ?? new Date().toISOString(),
  paper_ref: notification.paper_ref ?? {},
});

const hydrateServerSession = (chat, messages = []) => createSession({
  id: chat.id,
  title: chat.title,
  createdAt: chat.created_at,
  messages: messages.map((message) => normalizeMessage({
    id: message.id,
    role: message.role,
    content: message.content,
    timestamp: message.created_at,
    status: message.status,
    seq: message.seq,
    clientMessageId: message.client_message_id,
    metadata: message.metadata,
  })),
  status: chat.status ?? 'idle',
  error: null,
  threadId: chat.thread_id ?? null,
  persisted: true,
  feature: chat.feature ?? 'research',
  summary: chat.summary ?? null,
  lastMessageAt: chat.last_message_at ?? null,
});

const createOptimisticServerSession = (chat, existingSession = null) => createSession({
  id: chat.id,
  title: chat.title ?? existingSession?.title ?? 'Loading chat',
  createdAt: chat.created_at ?? existingSession?.createdAt ?? new Date().toISOString(),
  messages: existingSession?.messages ?? [],
  status: existingSession?.messages?.length ? (existingSession.status ?? chat.status ?? 'idle') : 'loading',
  error: null,
  threadId: chat.thread_id ?? existingSession?.threadId ?? null,
  persisted: true,
  feature: chat.feature ?? existingSession?.feature ?? 'research',
  summary: chat.summary ?? existingSession?.summary ?? null,
  lastMessageAt: chat.last_message_at ?? existingSession?.lastMessageAt ?? null,
});

const getChatActivityAt = (chat) => (
  chat?.last_message_at ??
  chat?.lastMessageAt ??
  chat?.created_at ??
  chat?.createdAt ??
  ''
);

const sortChatsByActivity = (items) => (
  [...items].sort((a, b) => {
    const activityCompare = getChatActivityAt(b).localeCompare(getChatActivityAt(a));
    if (activityCompare !== 0) return activityCompare;
    const createdCompare = (b?.created_at ?? b?.createdAt ?? '').localeCompare(a?.created_at ?? a?.createdAt ?? '');
    if (createdCompare !== 0) return createdCompare;
    return String(b?.id ?? '').localeCompare(String(a?.id ?? ''));
  })
);

const upsertSession = (sessions, session) => {
  const existingIndex = sessions.findIndex((item) => item.id === session.id);
  if (existingIndex === -1) return [session, ...sessions];
  const next = [...sessions];
  next[existingIndex] = { ...next[existingIndex], ...session };
  return next;
};

export const useChatStore = create((set, get) => ({
  sessions: [],
  activeSessionId: null,
  sidebarOpen: true,
  serverChats: [],
  chatsLoaded: false,
  chatsLoading: false,
  chatsError: null,
  chatMutationError: null,
  notifications: [],
  notificationsLoaded: false,
  notificationsLoading: false,
  notificationsError: null,
  notificationsPanelOpen: false,
  unreadNotificationCount: 0,
  topicInterests: [],
  topicInterestsLoaded: false,
  topicInterestsLoading: false,
  topicInterestsError: null,
  pauseAllInApp: false,
  notificationSettingsLoaded: false,
  topicInterestPendingById: {},

  loadNotifications: async () => {
    const token = useAuthStore.getState().token;
    if (!token) {
      set({
        notifications: [],
        notificationsLoaded: false,
        notificationsLoading: false,
        notificationsError: null,
        unreadNotificationCount: 0,
      });
      return [];
    }

    set({ notificationsLoading: true, notificationsError: null });
    try {
      const res = await fetch(API_ENDPOINTS.NOTIFICATIONS.BASE, { headers: authHeader() });
      if (!res.ok) throw new Error(`Failed to load notifications: ${res.status}`);
      const payload = await res.json();
      const items = (payload.items || []).map(normalizeNotification);
      set({
        notifications: items,
        unreadNotificationCount: payload.unread_count ?? items.filter((item) => !item.is_read).length,
        notificationsLoaded: true,
        notificationsLoading: false,
        notificationsError: null,
      });
      return items;
    } catch (err) {
      set({
        notificationsLoading: false,
        notificationsLoaded: true,
        notificationsError: err?.message ?? 'Failed to load notifications.',
      });
      return [];
    }
  },

  loadTopicInterests: async () => {
    const token = useAuthStore.getState().token;
    if (!token) {
      set({
        topicInterests: [],
        topicInterestsLoaded: false,
        topicInterestsLoading: false,
        topicInterestsError: null,
        pauseAllInApp: false,
        notificationSettingsLoaded: false,
      });
      return [];
    }

    set({ topicInterestsLoading: true, topicInterestsError: null });
    try {
      const res = await fetch(API_ENDPOINTS.TOPICS.INTERESTS, { headers: authHeader() });
      if (!res.ok) throw new Error(`Failed to load topic controls: ${res.status}`);
      const payload = await res.json();
      const items = (payload.items || []).map((item) => ({
        ...item,
        updated_at: item.updated_at ?? new Date().toISOString(),
      }));
      set({
        topicInterests: items,
        pauseAllInApp: Boolean(payload.pause_all_in_app),
        topicInterestsLoaded: true,
        topicInterestsLoading: false,
        topicInterestsError: null,
        notificationSettingsLoaded: true,
      });
      return items;
    } catch (err) {
      set({
        topicInterestsLoading: false,
        topicInterestsLoaded: true,
        topicInterestsError: err?.message ?? 'Failed to load topic controls.',
      });
      return [];
    }
  },

  setPauseAllInApp: async (pauseAllInApp) => {
    try {
      const res = await fetch(API_ENDPOINTS.NOTIFICATIONS.SETTINGS, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ pause_all_in_app: pauseAllInApp }),
      });
      if (!res.ok) throw new Error(`Failed to update notification settings: ${res.status}`);
      const payload = await res.json();
      set({ pauseAllInApp: Boolean(payload.pause_all_in_app), notificationSettingsLoaded: true });
      if (!pauseAllInApp) {
        await get().loadNotifications();
      }
      return true;
    } catch (err) {
      set({ topicInterestsError: err?.message ?? 'Failed to update notification settings.' });
      return false;
    }
  },

  updateTopicInterestState: async (topicId, state) => {
    set((store) => ({
      topicInterestsError: null,
      topicInterestPendingById: {
        ...store.topicInterestPendingById,
        [topicId]: true,
      },
    }));

    try {
      const res = await fetch(API_ENDPOINTS.TOPICS.INTEREST_ITEM(topicId), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ state }),
      });
      if (!res.ok) throw new Error(`Failed to update topic: ${res.status}`);
      const updated = await res.json();
      set((store) => ({
        topicInterests: store.topicInterests.map((item) => (item.topic_id === topicId ? { ...item, ...updated } : item)),
        topicInterestPendingById: {
          ...store.topicInterestPendingById,
          [topicId]: false,
        },
      }));
      void get().loadTopicInterests();
      return true;
    } catch (err) {
      set((store) => ({
        topicInterestsError: err?.message ?? 'Failed to update topic.',
        topicInterestPendingById: {
          ...store.topicInterestPendingById,
          [topicId]: false,
        },
      }));
      return false;
    }
  },

  deleteTopicInterest: async (topicId) => {
    try {
      const res = await fetch(API_ENDPOINTS.TOPICS.INTEREST_ITEM(topicId), {
        method: 'DELETE',
        headers: authHeader(),
      });
      if (!res.ok && res.status !== 204) throw new Error(`Failed to delete topic: ${res.status}`);
      await get().loadTopicInterests();
      return true;
    } catch (err) {
      set({ topicInterestsError: err?.message ?? 'Failed to delete topic.' });
      return false;
    }
  },
  markNotificationRead: async (notificationId) => {
    try {
      const res = await fetch(API_ENDPOINTS.NOTIFICATIONS.ITEM(notificationId), {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({ is_read: true }),
      });
      if (!res.ok) throw new Error(`Failed to update notification: ${res.status}`);
      const updated = normalizeNotification(await res.json());
      set((state) => {
        const notifications = state.notifications.map((item) => (item.id === updated.id ? updated : item));
        return {
          notifications,
          unreadNotificationCount: notifications.filter((item) => !item.is_read).length,
        };
      });
      return updated;
    } catch (err) {
      set({ notificationsError: err?.message ?? 'Failed to update notification.' });
      return null;
    }
  },

  markAllNotificationsRead: async () => {
    try {
      const res = await fetch(API_ENDPOINTS.NOTIFICATIONS.MARK_ALL_READ, {
        method: 'POST',
        headers: authHeader(),
      });
      if (!res.ok) throw new Error(`Failed to mark all notifications read: ${res.status}`);
      set((state) => ({
        notifications: state.notifications.map((item) => ({ ...item, is_read: true })),
        unreadNotificationCount: 0,
      }));
      return true;
    } catch (err) {
      set({ notificationsError: err?.message ?? 'Failed to update notifications.' });
      return false;
    }
  },

  setNotificationsPanelOpen: (open) => set({ notificationsPanelOpen: open }),
  toggleNotificationsPanel: () => set((state) => ({ notificationsPanelOpen: !state.notificationsPanelOpen })),
  clearNotificationsError: () => set({ notificationsError: null }),
  loadChats: async () => {
    const token = useAuthStore.getState().token;
    if (!token) {
      set({ serverChats: [], chatsLoaded: false, chatsLoading: false, chatsError: null });
      return [];
    }

    set({ chatsLoading: true, chatsError: null });
    try {
      const res = await fetch(API_ENDPOINTS.CHATS.BASE, { headers: authHeader() });
      if (!res.ok) throw new Error(`Failed to load chats: ${res.status}`);
      const chats = await res.json();
      const orderedChats = sortChatsByActivity(chats);
      set({ serverChats: orderedChats, chatsLoaded: true, chatsLoading: false, chatsError: null });
      return orderedChats;
    } catch (err) {
      set({ chatsLoading: false, chatsLoaded: true, chatsError: err?.message ?? 'Failed to load chats.' });
      return [];
    }
  },

  createServerChat: async (payload = {}, options = {}) => {
    const { replaceSessionId = null } = options;
    set({ chatMutationError: null });
    try {
      const res = await fetch(API_ENDPOINTS.CHATS.BASE, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(`Failed to create chat: ${res.status}`);
      const chat = await res.json();
      const session = hydrateServerSession(chat, []);
      set((state) => ({
        serverChats: sortChatsByActivity([chat, ...state.serverChats.filter((item) => item.id !== chat.id)]),
        sessions: upsertSession(
          state.sessions.filter((item) => item.id !== replaceSessionId),
          session
        ),
        activeSessionId: session.id,
      }));
      return session.id;
    } catch (err) {
      const message = err?.message ?? 'Failed to create chat.';
      set({ chatMutationError: message });
      throw err;
    }
  },

  openServerChat: async (chatId) => {
    set((state) => {
      const chat = state.serverChats.find((item) => item.id === chatId) ?? { id: chatId };
      const existingSession = state.sessions.find((item) => item.id === chatId) ?? null;
      const optimisticSession = createOptimisticServerSession(chat, existingSession);
      return {
        chatsError: null,
        chatMutationError: null,
        activeSessionId: chatId,
        sessions: upsertSession(state.sessions, optimisticSession),
      };
    });

    try {
      const res = await fetch(API_ENDPOINTS.CHATS.ITEM(chatId), { headers: authHeader() });
      if (!res.ok) throw new Error(`Failed to open chat: ${res.status}`);
      const detail = await res.json();
      const session = hydrateServerSession(detail.chat, detail.messages || []);
      set((state) => ({
        sessions: upsertSession(state.sessions, session),
        serverChats: sortChatsByActivity(state.serverChats.some((item) => item.id === detail.chat.id)
          ? state.serverChats.map((item) => (item.id === detail.chat.id ? detail.chat : item))
          : [detail.chat, ...state.serverChats]),
      }));
      return session.id;
    } catch (err) {
      const message = err?.message ?? 'Failed to open chat.';
      set((state) => ({
        chatsError: message,
        sessions: state.sessions.map((session) => (
          session.id === chatId ? { ...session, status: 'error', error: message } : session
        )),
      }));
      return null;
    }
  },

  deleteServerChat: async (chatId) => {
    set({ chatMutationError: null });
    try {
      const res = await fetch(API_ENDPOINTS.CHATS.ITEM(chatId), {
        method: 'DELETE',
        headers: authHeader(),
      });
      if (!res.ok && res.status !== 204) throw new Error(`Failed to delete chat: ${res.status}`);
      set((state) => ({
        serverChats: state.serverChats.filter((item) => item.id !== chatId),
        sessions: state.sessions.filter((item) => item.id !== chatId),
        activeSessionId: state.activeSessionId === chatId ? null : state.activeSessionId,
      }));
      return true;
    } catch (err) {
      set({ chatMutationError: err?.message ?? 'Failed to delete chat.' });
      return false;
    }
  },

  newSession: () => {
    const session = createSession();
    set((state) => ({
      sessions: [session, ...state.sessions],
      activeSessionId: session.id,
    }));
    return session.id;
  },

  setActiveSession: (id) => set({ activeSessionId: id }),

  ensureActiveSession: () => {
    const { activeSessionId, sessions, newSession } = get();
    if (activeSessionId && sessions.some((session) => session.id === activeSessionId)) {
      return activeSessionId;
    }
    return newSession();
  },

  sendMessage: async (text) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (_sendInFlight) return;
    _sendInFlight = true;

    try {
      await get()._sendMessageImpl(trimmed);
    } finally {
      _sendInFlight = false;
    }
  },

  _sendMessageImpl: async (trimmed) => {
    const token = useAuthStore.getState().token;
    let activeId = get().activeSessionId;
    let activeSession = get().sessions.find((session) => session.id === activeId);

    if (!activeSession && token) {
      try {
        activeId = await get().createServerChat({ title: trimmed.slice(0, 70) || 'New chat' });
        activeSession = get().sessions.find((session) => session.id === activeId);
      } catch {
        activeId = get().newSession();
        activeSession = get().sessions.find((session) => session.id === activeId);
      }
    }

    if (!activeSession) {
      activeId = get().ensureActiveSession();
      activeSession = get().sessions.find((session) => session.id === activeId);
    }

    if (!activeSession?.persisted && token) {
      try {
        const persistedId = await get().createServerChat(
          { title: activeSession?.title === 'New Session' ? trimmed.slice(0, 70) || 'New chat' : activeSession?.title },
          { replaceSessionId: activeId }
        );
        activeId = persistedId;
        activeSession = get().sessions.find((session) => session.id === activeId);
      } catch {
        activeSession = get().sessions.find((session) => session.id === activeId);
      }
    }

    if (activeSession?.status === 'loading' || activeSession?.status === 'awaiting_plan') return;

    const clientMessageId = makeId();
    const userMsg = {
      id: makeId(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
      clientMessageId,
    };
    const assistantId = makeId();
    const assistantPlaceholder = {
      id: assistantId,
      role: 'assistant',
      content: '',
      steps: [],
      pendingPlan: null,
      timestamp: new Date().toISOString(),
    };

    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === activeId
          ? {
              ...session,
              messages: [...session.messages, userMsg, assistantPlaceholder],
              title: session.messages.length === 0 ? trimmed.slice(0, 70) : session.title,
              status: 'loading',
              error: null,
            }
          : session
      ),
    }));

    try {
      const session = get().sessions.find((item) => item.id === activeId);
      const res = await fetch(API_ENDPOINTS.RESEARCH.STREAM, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({
          query: trimmed,
          thread_id: session?.threadId ?? null,
          chat_id: session?.persisted ? session.id : null,
          client_message_id: clientMessageId,
        }),
      });
      if (res.status === 402) {
        throw new Error(await res.text() || 'Literature Review quota exhausted - please upgrade your plan or top up.');
      }
      if (!res.ok) throw new Error(`Research stream failed: ${res.status}`);

      await get()._runStream(activeId, assistantId, res);
      const refreshedSession = get().sessions.find((item) => item.id === activeId);
      if (refreshedSession?.persisted) {
        await get().loadChats();
      }
    } catch (err) {
      get()._setError(activeId, err?.message ?? 'Research pipeline failed.');
    }
  },

  approvePlan: async (sessionId, plan) => {
    const session = get().sessions.find((item) => item.id === sessionId);
    if (!session?.threadId) return;
    const assistantMsg = [...session.messages].reverse().find((message) => message.role === 'assistant');
    if (!assistantMsg) return;

    set((state) => ({
      sessions: state.sessions.map((item) =>
        item.id === sessionId
          ? {
              ...item,
              status: 'loading',
              messages: item.messages.map((message) =>
                message.id === assistantMsg.id ? { ...message, pendingPlan: null } : message
              ),
            }
          : item
      ),
    }));

    try {
      const res = await fetch(API_ENDPOINTS.RESEARCH.RESUME, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({
          thread_id: session.threadId,
          chat_id: session.persisted ? session.id : null,
          resume_value: plan,
        }),
      });
      if (!res.ok) throw new Error(`Resume failed: ${res.status}`);
      await get()._runStream(sessionId, assistantMsg.id, res);
      if (session.persisted) {
        await get().loadChats();
      }
    } catch (err) {
      get()._setError(sessionId, err?.message ?? 'Resume failed.');
    }
  },

  _runStream: async (activeId, assistantId, firstResponse) => {
    let response = firstResponse;
    while (response) {
      const { interrupted, pendingApproval } = await get()._parseStream(activeId, assistantId, response);
      if (pendingApproval) {
        set((state) => ({
          sessions: state.sessions.map((session) => (session.id === activeId ? { ...session, status: 'awaiting_plan' } : session)),
        }));
        return;
      }
      if (!interrupted) break;

      const session = get().sessions.find((item) => item.id === activeId);
      const threadId = session?.threadId;
      if (!threadId) break;
      response = await fetch(API_ENDPOINTS.RESEARCH.RESUME, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeader() },
        body: JSON.stringify({
          thread_id: threadId,
          chat_id: session?.persisted ? session.id : null,
          resume_value: true,
        }),
      });
      if (!response.ok) throw new Error(`Resume failed: ${response.status}`);
    }

    const finalSession = get().sessions.find((session) => session.id === activeId);
    if (finalSession?.status === 'loading') {
      set((state) => ({
        sessions: state.sessions.map((session) => (session.id === activeId ? { ...session, status: 'idle' } : session)),
      }));
    }
  },

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
        const dataLine = part.split('\n').find((line) => line.startsWith('data: '));
        if (!dataLine) continue;
        let event;
        try {
          event = JSON.parse(dataLine.slice(6));
        } catch {
          continue;
        }

        switch (event.type) {
          case 'thread_id':
            get()._setThreadId(activeId, event.thread_id);
            break;
          case 'thinking_token':
          case 'reply_token':
            break;
          case 'greeting':
            get()._setContent(activeId, assistantId, event.content || 'Hello!');
            break;
          case 'clarify': {
            const questions = (event.questions || []).map((question, index) => `${index + 1}. ${question}`).join('\n');
            get()._setContent(activeId, assistantId, `I need a bit more context:\n\n${questions}`);
            break;
          }
          case 'step_token':
            get()._upsertRunningStep(activeId, assistantId, event.stepNum, event.content);
            break;
          case 'step':
            get()._completeStep(activeId, assistantId, event);
            break;
          case 'heartbeat':
            break;
          case 'interrupt': {
            const data = event.data || {};
            if (data.sub_queries) {
              get()._setPendingPlan(activeId, assistantId, data);
              pendingApproval = true;
            } else if (data.themes) {
              get()._addStep(activeId, assistantId, {
                stepNum: '5',
                type: 'observation',
                content: `Outline ready: ${data.themes.map((theme) => `"${theme.title}"`).join(', ')}`,
                stat: `${data.themes.length} themes`,
              });
            }
            interrupted = true;
            break;
          }
          case 'done':
            get()._setContent(activeId, assistantId, event.content || '*(Pipeline complete - no content returned)*');
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
      sessions: state.sessions.map((session) =>
        session.id === sessionId ? { ...session, threadId } : session
      ),
      serverChats: state.serverChats.map((chat) => (chat.id === sessionId ? { ...chat, thread_id: threadId } : chat)),
    })),

  _setPendingPlan: (sessionId, assistantId, data) =>
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              messages: session.messages.map((message) =>
                message.id === assistantId ? { ...message, pendingPlan: data } : message
              ),
            }
          : session
      ),
    })),

  _upsertRunningStep: (sessionId, assistantId, stepNum, token) =>
    set((state) => ({
      sessions: state.sessions.map((session) => {
        if (session.id !== sessionId) return session;
        return {
          ...session,
          messages: session.messages.map((message) => {
            if (message.id !== assistantId) return message;
            const steps = message.steps || [];
            const idx = steps.findIndex((step) => step.stepNum === stepNum && step.status === 'running');
            if (idx === -1) {
              return {
                ...message,
                steps: [...steps, { id: ++_seq, stepNum, type: 'thought', status: 'running', content: token }],
              };
            }
            const next = [...steps];
            next[idx] = { ...next[idx], content: next[idx].content + token };
            return { ...message, steps: next };
          }),
        };
      }),
    })),

  _completeStep: (sessionId, assistantId, event) =>
    set((state) => ({
      sessions: state.sessions.map((session) => {
        if (session.id !== sessionId) return session;
        return {
          ...session,
          messages: session.messages.map((message) => {
            if (message.id !== assistantId) return message;
            const steps = message.steps || [];
            const idx = steps.findIndex((step) => step.stepNum === event.stepNum && step.status === 'running');
            const finalised = {
              id: idx === -1 ? ++_seq : steps[idx].id,
              stepNum: event.stepNum,
              type: event.step_type ?? 'observation',
              status: 'done',
              content: event.content,
              stat: event.stat,
            };
            if (idx === -1) return { ...message, steps: [...steps, finalised] };
            const next = [...steps];
            next[idx] = finalised;
            return { ...message, steps: next };
          }),
        };
      }),
    })),

  _addStep: (sessionId, assistantId, step) =>
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              messages: session.messages.map((message) =>
                message.id === assistantId
                  ? { ...message, steps: [...(message.steps || []), { id: ++_seq, status: 'done', ...step }] }
                  : message
              ),
            }
          : session
      ),
    })),

  _setContent: (sessionId, assistantId, content) =>
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId
          ? {
              ...session,
              status: 'idle',
              lastMessageAt: new Date().toISOString(),
              messages: session.messages.map((message) => (message.id === assistantId ? { ...message, content } : message)),
            }
          : session
      ),
    })),

  _setError: (sessionId, message) =>
    set((state) => ({
      sessions: state.sessions.map((session) =>
        session.id === sessionId ? { ...session, status: 'error', error: message } : session
      ),
    })),

  clearError: (sessionId) =>
    set((state) => ({
      sessions: state.sessions.map((session) => (session.id === sessionId ? { ...session, error: null } : session)),
    })),

  clearChatMutationError: () => set({ chatMutationError: null }),
  clearChatsError: () => set({ chatsError: null }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
}));



