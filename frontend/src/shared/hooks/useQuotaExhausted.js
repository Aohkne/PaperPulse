import { useEffect } from 'react';
import { useBillingStore } from '@/shared/store/useBillingStore';

/**
 * useQuotaExhausted — true once the user has no quota left for `feature`
 * ('lr' | 'pdf' | 'gap'). Mirrors the remaining-quota math in
 * UsageExhaustedBanner so input components can block submission, not just
 * show a dismissible warning.
 */
export function useQuotaExhausted(feature) {
  const account = useBillingStore((s) => s.account);
  const fetchAccount = useBillingStore((s) => s.fetchAccount);

  useEffect(() => { fetchAccount(); }, [fetchAccount]);

  const subscriptionQuota = account?.[`subscription_${feature}_quota`];
  if (!account || subscriptionQuota === null || subscriptionQuota === undefined) return false;

  const usedThisPeriod = account?.[`${feature}_used_this_period`];
  const topupBalance = account?.[`topup_${feature}_balance`];
  const remaining = (subscriptionQuota - usedThisPeriod) + topupBalance;
  return remaining <= 0;
}
