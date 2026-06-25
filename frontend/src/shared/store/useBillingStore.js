import { create } from 'zustand';
import { billingApi } from '@/features/billing/billingApi';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const token = () => useAuthStore.getState().token;

export const useBillingStore = create((set, get) => ({
  account: null,
  accountLoading: false,
  accountError: null,

  checkoutLoading: false,
  checkoutError: null,
  pendingCheckout: null, // { transaction_id, checkout_url, qr_code, amount_vnd }

  fetchAccount: async () => {
    set({ accountLoading: true, accountError: null });
    try {
      const data = await billingApi.getMe(token());
      set({ account: data, accountLoading: false });
    } catch (e) {
      set({ accountError: e.message, accountLoading: false });
    }
  },

  checkoutSubscription: async (tier) => {
    set({ checkoutLoading: true, checkoutError: null, pendingCheckout: null });
    try {
      const result = await billingApi.checkoutSubscription(token(), tier);
      set({ pendingCheckout: result, checkoutLoading: false });
      return result;
    } catch (e) {
      set({ checkoutError: e.message, checkoutLoading: false });
      throw e;
    }
  },

  checkoutTopup: async (pack) => {
    set({ checkoutLoading: true, checkoutError: null, pendingCheckout: null });
    try {
      const result = await billingApi.checkoutTopup(token(), pack);
      set({ pendingCheckout: result, checkoutLoading: false });
      return result;
    } catch (e) {
      set({ checkoutError: e.message, checkoutLoading: false });
      throw e;
    }
  },

  downgrade: async (tier) => {
    await billingApi.downgrade(token(), tier);
    await get().fetchAccount();
  },

  clearPendingCheckout: () => set({ pendingCheckout: null }),

  // Poll a just-created transaction until PayOS's webhook settles it (or the
  // caller gives up). Returns the final status.
  pollTransaction: async (transactionId, { intervalMs = 3000, maxAttempts = 20 } = {}) => {
    for (let i = 0; i < maxAttempts; i++) {
      const txn = await billingApi.getTransaction(token(), transactionId);
      if (txn.status !== 'pending') {
        if (txn.status === 'paid') await get().fetchAccount();
        return txn.status;
      }
      await new Promise((r) => setTimeout(r, intervalMs));
    }
    return 'pending';
  },
}));
