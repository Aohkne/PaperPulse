import { useEffect } from 'react';
import { useBillingStore } from '@/shared/store/useBillingStore';

const TIER_LABELS = { free: 'Free', plus: 'Plus', unlimited: 'Unlimited' };

const cardStyle = {
  border: '1px solid var(--color-paper-light)',
  borderRadius: '8px',
  padding: '20px',
  background: 'var(--color-paper-bg)',
};

const QuotaRow = ({ label, used, remaining, total }) => (
  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '14px', color: 'var(--color-paper-mid)', marginBottom: '4px' }}>
    <span>{label}</span>
    <span>{total === null ? `${used} used` : `${remaining}/${total}`}</span>
  </div>
);

const UsagePanel = () => {
  const account = useBillingStore((s) => s.account);
  const accountLoading = useBillingStore((s) => s.accountLoading);
  const fetchAccount = useBillingStore((s) => s.fetchAccount);

  useEffect(() => { fetchAccount(); }, [fetchAccount]);

  if (accountLoading && !account) return <p>Loading...</p>;
  if (!account) return null;

  return (
    <div style={cardStyle}>
      <p style={{ fontFamily: 'Georgia, serif', fontWeight: 600 }}>
        Current plan: {TIER_LABELS[account.tier] ?? account.tier}
        {account.pending_downgrade_tier && (
          <span style={{ fontSize: 12, color: 'var(--color-paper-mid)', fontWeight: 400 }}>
            {' '}(switching to {account.pending_downgrade_tier} next period)
          </span>
        )}
      </p>
      <div style={{ marginTop: '8px' }}>
        <QuotaRow
          label="Literature Review"
          used={account.lr_used_this_period}
          remaining={account.subscription_lr_quota}
          total={account.subscription_lr_quota === null ? null : account.lr_used_this_period + account.subscription_lr_quota}
        />
        <QuotaRow
          label="PDF Agent"
          used={account.pdf_used_this_period}
          remaining={account.subscription_pdf_quota}
          total={account.subscription_pdf_quota === null ? null : account.pdf_used_this_period + account.subscription_pdf_quota}
        />
        <QuotaRow
          label="Research Gap"
          used={account.gap_used_this_period}
          remaining={account.subscription_gap_quota}
          total={account.subscription_gap_quota === null ? null : account.gap_used_this_period + account.subscription_gap_quota}
        />
      </div>
      <p style={{ fontSize: 13, color: 'var(--color-paper-light)', marginTop: '8px' }}>
        Top-up balance: {account.topup_lr_balance} LR · {account.topup_pdf_balance} PDF · {account.topup_gap_balance} Gap
      </p>
      <p style={{ fontSize: 13, color: 'var(--color-paper-light)' }}>
        Renews: {new Date(account.tier_period_end).toLocaleDateString('vi-VN')}
      </p>
    </div>
  );
};

export default UsagePanel;
