import { useEffect, useState } from 'react';
import { Icon } from '@iconify/react';
import { useBillingStore } from '@/shared/store/useBillingStore';

const formatResetTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  const pad = (n) => String(n).padStart(2, '0');
  return `${pad(d.getHours())}:${pad(d.getMinutes())} ${pad(d.getDate())}-${pad(d.getMonth() + 1)}`;
};

const FEATURE_LABELS = { lr: 'Literature Review', pdf: 'PDF Agent', gap: 'Research Gap' };

const UsageExhaustedBanner = ({ feature = 'lr' }) => {
  const account = useBillingStore((s) => s.account);
  const fetchAccount = useBillingStore((s) => s.fetchAccount);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => { fetchAccount(); }, [fetchAccount]);

  const subscriptionQuota = account?.[`subscription_${feature}_quota`];
  const usedThisPeriod = account?.[`${feature}_used_this_period`];
  const topupBalance = account?.[`topup_${feature}_balance`];

  if (!account || subscriptionQuota === null || subscriptionQuota === undefined) return null;
  const remaining = (subscriptionQuota - usedThisPeriod) + topupBalance;
  if (remaining > 0 || dismissed) return null;

  return (
    <div style={{
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
      maxWidth: '680px', margin: '0 auto 10px',
      padding: '8px 14px', borderRadius: '4px',
      background: 'var(--color-brand-50)', border: '1px solid var(--color-brand-100)',
      fontFamily: 'Georgia, serif', fontSize: '13px', color: 'var(--color-brand-600)',
    }}>
      <span>
        You've used up your {FEATURE_LABELS[feature]} quota for this period. It resets on {formatResetTime(account.tier_period_end)}.
      </span>
      <button
        onClick={() => setDismissed(true)}
        title="Dismiss"
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-brand-600)', display: 'flex', flexShrink: 0 }}
      >
        <Icon icon="mdi:close" style={{ fontSize: 16 }} />
      </button>
    </div>
  );
};

export default UsageExhaustedBanner;
