import { create } from 'zustand';
import { communityApi } from '@/features/community/communityApi';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const token = () => useAuthStore.getState().token;

export const useCommunityStore = create((set, get) => ({
  // feed
  items: [],
  pagination: { page: 1, limit: 10, total: 0, has_more: false },
  sort: 'new', // 'new' | 'top'
  listLoading: false,
  listError: null,

  // leaderboard
  leaderboard: [],
  leaderboardLoading: false,
  leaderboardError: null,

  // submit
  submitLoading: false,
  submitError: null,

  setSort: (sort) => {
    set({ sort, items: [], pagination: { page: 1, limit: 10, total: 0, has_more: false } });
    get().fetchList(1);
  },

  fetchList: async (page = 1) => {
    const { sort } = get();
    set({ listLoading: true, listError: null });
    try {
      const data = await communityApi.list(token(), { sort, page, limit: 10 });
      set((s) => ({
        items: page === 1 ? data.data : [...s.items, ...data.data],
        pagination: data.pagination,
        listLoading: false,
      }));
    } catch (e) {
      set({ listError: e.message, listLoading: false });
    }
  },

  loadMore: () => {
    const { pagination } = get();
    if (pagination.has_more) get().fetchList(pagination.page + 1);
  },

  fetchLeaderboard: async () => {
    set({ leaderboardLoading: true, leaderboardError: null });
    try {
      const data = await communityApi.leaderboard();
      set({ leaderboard: data, leaderboardLoading: false });
    } catch (e) {
      set({ leaderboardError: e.message, leaderboardLoading: false });
    }
  },

  submit: async ({ title, content, review_id }) => {
    set({ submitLoading: true, submitError: null });
    try {
      const result = await communityApi.create(token(), { title, content, review_id });
      set({ submitLoading: false });
      return result;
    } catch (e) {
      set({ submitError: e.message, submitLoading: false });
      throw e;
    }
  },

  toggleVote: async (id) => {
    const { items } = get();
    const idx = items.findIndex((c) => c.id === id);
    if (idx === -1) return;

    const prev = items[idx];
    const optimistic = {
      ...prev,
      voted_by_me: !prev.voted_by_me,
      total_votes: prev.total_votes + (prev.voted_by_me ? -1 : 1),
    };
    set((s) => ({ items: s.items.map((c) => (c.id === id ? optimistic : c)) }));

    try {
      const result = await communityApi.vote(token(), id);
      set((s) => ({
        items: s.items.map((c) =>
          c.id === id ? { ...c, voted_by_me: result.voted, total_votes: result.total_votes } : c
        ),
      }));
    } catch (e) {
      // roll back on failure
      set((s) => ({ items: s.items.map((c) => (c.id === id ? prev : c)) }));
      throw e;
    }
  },
}));
