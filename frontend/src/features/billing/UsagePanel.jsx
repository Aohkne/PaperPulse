import { useEffect } from 'react';
import { useBillingStore } from '@/shared/store/useBillingStore';

const TIER_LABELS = { free: 'Free', plus: 'Plus', unlimited: 'Unlimited' };

const cardStyle = {
  border: '1px solid var(--color-hairline-border)',
  borderRadius: '8px',
  padding: '20px',
  background: 'var(--color-paper-bg)',
};

// <70% green / 70-90% amber / >90% red (token.html §4 UI).
const barColor = (pct) => (pct > 90 ? '#A93E3E' : pct > 70 ? '#A8672A' : 'var(--color-brand-600)');

const UsagePanel = () => {
  const account = useBillingStore((s) => s.account);
  const accountLoading = useBillingStore((s) => s.accountLoading);
  const fetchAccount = useBillingStore((s) => s.fetchAccount);

  useEffect(() => {
    fetchAccount();
  }, [fetchAccount]);

  if (accountLoading && !account) return <p>Loading...</p>;
  if (!account) return null;

  const used = Number(account.credit_used_this_period ?? 0);
  const balance = account.subscription_credit_balance; // null = unlimited
  const unlimited = balance === null || balance === undefined;
  const budget = unlimited ? null : Math.max(0, Number(balance)) + used;
  const pct = budget ? Math.min(100, Math.round((used / budget) * 100)) : 0;

  return (
    <div style={cardStyle}>
      <p style={{ fontFamily: "'Newsreader', serif", fontWeight: 600, marginBottom: 12 }}>
        Current plan: {TIER_LABELS[account.tier] ?? account.tier}
        {account.pending_downgrade_tier && (
          <span style={{ fontSize: 12, color: 'var(--color-paper-mid)', fontWeight: 400 }}>
            {' '}
            (switching to {account.pending_downgrade_tier} next period)
          </span>
        )}
      </p>

      {/* Single shared credit budget bar (all features draw from one pool). */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          fontSize: 13.5,
          marginBottom: 6,
        }}
      >
        <span style={{ color: 'var(--color-paper-mid)' }}>
          {unlimited ? 'Usage this period' : 'Monthly budget used'}
        </span>
        <span
          style={{
            fontWeight: 700,
            color: unlimited ? 'var(--color-brand-600)' : barColor(pct),
            fontVariantNumeric: 'tabular-nums',
          }}
        >
          {unlimited ? `${used.toFixed(1)} credits` : `${pct}%`}
        </span>
      </div>
      {/* Progress bar only for capped tiers — Unlimited has no monthly cap. */}
      {!unlimited && (
        <div
          style={{
            height: 10,
            borderRadius: 999,
            background: 'var(--color-hairline-border)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              height: '100%',
              width: `${pct}%`,
              background: barColor(pct),
              borderRadius: 999,
            }}
          />
        </div>
      )}
      <p
        style={{
          fontSize: 12,
          color: 'var(--color-paper-mid)',
          marginTop: 6,
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {unlimited
          ? 'Unlimited plan — no monthly cap'
          : `${used.toFixed(1)} / ${budget.toFixed(0)} credits used · ${Math.max(0, Number(balance)).toFixed(1)} left`}
      </p>

      <p style={{ fontSize: 13, color: 'var(--color-paper-mid)', marginTop: 8 }}>
        Renews: {new Date(account.tier_period_end).toLocaleDateString('vi-VN')}
      </p>
    </div>
  );
};

export default UsagePanel;
