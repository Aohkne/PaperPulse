import { create } from 'zustand';
import { reviewsApi } from '@/features/reviews/reviewsApi';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const token = () => useAuthStore.getState().token;

export const useReviewsStore = create((set, get) => ({
  // list state
  items: [],
  pagination: { page: 1, limit: 5, total: 0, has_more: false },
  search: '',
  listLoading: false,
  listError: null,

  // detail state
  current: null,
  detailLoading: false,
  detailError: null,

  // save state
  saveLoading: false,
  saveError: null,

  setSearch: (search) =>
    set({ search, items: [], pagination: { page: 1, limit: 5, total: 0, has_more: false } }),

  fetchList: async (page = 1) => {
    const { search } = get();
    set({ listLoading: true, listError: null });
    try {
      const data = await reviewsApi.list(token(), { page, limit: 5, search });
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

  fetchDetail: async (id) => {
    set({ detailLoading: true, detailError: null, current: null });
    try {
      const data = await reviewsApi.get(token(), id);
      set({ current: data, detailLoading: false });
    } catch (e) {
      set({ detailError: e.message, detailLoading: false });
    }
  },

  saveReview: async ({ title, query, markdown_content }) => {
    set({ saveLoading: true, saveError: null });
    try {
      const result = await reviewsApi.create(token(), { title, query, markdown_content });
      set({ saveLoading: false });
      return result;
    } catch (e) {
      set({ saveError: e.message, saveLoading: false });
      throw e;
    }
  },

  updateCurrent: async (id, patch) => {
    const data = await reviewsApi.update(token(), id, patch);
    set({ current: data });
    return data;
  },

  deleteReview: async (id) => {
    await reviewsApi.delete(token(), id);
    set((s) => ({
      items: s.items.filter((r) => r.id !== id),
      pagination: { ...s.pagination, total: Math.max(0, s.pagination.total - 1) },
    }));
  },

  duplicateReview: async (id, title) => {
    const result = await reviewsApi.duplicate(token(), id, title);
    // refresh list from beginning
    get().fetchList(1);
    return result;
  },
}));
