import { useEffect } from 'react';
import { useBillingStore } from '@/shared/store/useBillingStore';

/**
 * useQuotaExhausted — true once the shared credit pool is empty. Token-weighted
 * billing uses ONE pool for all features, so `feature` no longer changes the
 * result (kept as an arg for call-site compatibility). Unlimited tier
 * (subscription_credit_balance === null) is never exhausted.
 */
export function useQuotaExhausted(/* feature */) {
  const account = useBillingStore((s) => s.account);
  const fetchAccount = useBillingStore((s) => s.fetchAccount);

  useEffect(() => { fetchAccount(); }, [fetchAccount]);

  if (!account) return false;
  const balance = account.subscription_credit_balance;
  if (balance === null || balance === undefined) return false; // unlimited
  return balance <= 0;
}
