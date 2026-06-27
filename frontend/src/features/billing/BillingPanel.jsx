import { useEffect, useState } from 'react';
import { Icon } from '@iconify/react';
import { QRCodeSVG } from 'qrcode.react';
import { useBillingStore } from '@/shared/store/useBillingStore';
import { friendlyError } from '@/shared/utils/errorMessage';

// Lora has full Vietnamese Unicode support — fixes "đ" rendering
const PRICE_FONT = "'Lora', 'Noto Serif', serif";

const TIERS = [
  { key: 'free',      label: 'Free',      price: '0đ',              lr: 3,   pdf: 5,   gap: 3   },
  { key: 'plus',      label: 'Plus',      price: '19.000đ/month',   lr: 5,   pdf: 10,  gap: 5,  popular: true },
  { key: 'unlimited', label: 'Unlimited', price: '299.000đ/month',  lr: '∞', pdf: '∞', gap: '∞' },
];

const TOPUP_PACKS = [
  { key: 'pdf_5',  label: '5 PDF Agent',          price: '10.000đ' },
  { key: 'lr_5',   label: '5 Literature Review',   price: '10.000đ' },
  { key: 'gap_5',  label: '5 Research Gap',         price: '10.000đ' },
  { key: 'combo',  label: 'Combo (5 PDF + 5 LR)',   price: '18.000đ', combo: true },
];

const sectionTitle = {
  fontFamily: "'Lora', 'Noto Serif', serif",
  fontSize: '16px',
  fontWeight: 600,
  color: 'var(--color-paper-dark)',
  margin: '24px 0 12px',
  letterSpacing: '0.01em',
};

const baseButtonStyle = {
  width: '100%',
  padding: '8px 12px',
  border: '1px solid var(--color-paper-surface)',
  borderRadius: '4px',
  background: 'var(--color-paper-surface)',
  cursor: 'pointer',
  fontSize: '14px',
  fontFamily: PRICE_FONT,
  color: 'var(--color-paper-dark)',
  marginTop: '14px',
  transition: 'background 0.12s, border-color 0.12s',
};

const CheckoutModal = ({ checkout, onClose }) => {
  const pollTransaction = useBillingStore((s) => s.pollTransaction);
  const [status, setStatus] = useState('pending');

  useEffect(() => {
    let cancelled = false;
    pollTransaction(checkout.transaction_id).then((result) => {
      if (!cancelled) setStatus(result);
    });
    return () => { cancelled = true; };
  }, [checkout.transaction_id, pollTransaction]);

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(41,17,0,0.35)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10001,
    }} onClick={onClose}>
      <div
        style={{
          background: 'var(--color-paper-bg)',
          border: '1px solid var(--color-paper-surface)',
          borderRadius: '4px',
          padding: '24px', maxWidth: '360px', textAlign: 'center',
          boxShadow: '0 8px 32px rgba(41,17,0,0.12)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {status === 'paid' ? (
          <>
            <Icon icon="mdi:check-circle" style={{ fontSize: 48, color: 'var(--color-paper-mid)' }} />
            <p style={{ marginTop: 12, fontFamily: PRICE_FONT }}>Payment successful.</p>
          </>
        ) : (
          <>
            <p style={{ fontFamily: PRICE_FONT, marginBottom: 12 }}>
              Scan QR to pay {checkout.amount_vnd.toLocaleString('vi-VN')}đ
            </p>
            <QRCodeSVG value={checkout.qr_code} size={220} />
            <p style={{ fontSize: 12, color: 'var(--color-paper-light)', marginTop: 12, fontFamily: PRICE_FONT }}>
              {status === 'pending' ? 'Waiting for payment...' : `Status: ${status}`}
            </p>
            <a href={checkout.checkout_url} target="_blank" rel="noreferrer"
              style={{ fontSize: 13, color: 'var(--color-brand-600)', fontFamily: PRICE_FONT }}>
              Open banking app
            </a>
          </>
        )}
        <button style={{ ...baseButtonStyle, marginTop: 16 }} onClick={onClose}>Close</button>
      </div>
    </div>
  );
};

const BillingPanel = () => {
  const account = useBillingStore((s) => s.account);
  const fetchAccount = useBillingStore((s) => s.fetchAccount);
  const checkoutSubscription = useBillingStore((s) => s.checkoutSubscription);
  const checkoutTopup = useBillingStore((s) => s.checkoutTopup);
  const downgrade = useBillingStore((s) => s.downgrade);
  const pendingCheckout = useBillingStore((s) => s.pendingCheckout);
  const clearPendingCheckout = useBillingStore((s) => s.clearPendingCheckout);
  const checkoutError = useBillingStore((s) => s.checkoutError);

  useEffect(() => { fetchAccount(); }, [fetchAccount]);

  const currentTierIndex = TIERS.findIndex((t) => t.key === account?.tier);

  const handleTierAction = async (tierKey) => {
    if (!account) return;
    const targetIndex = TIERS.findIndex((t) => t.key === tierKey);
    if (targetIndex === currentTierIndex) return;
    if (targetIndex > currentTierIndex) {
      await checkoutSubscription(tierKey);
    } else {
      await downgrade(tierKey);
    }
  };

  return (
    <div>
      {checkoutError && (
        <p style={{ color: 'var(--color-brand-600)', fontFamily: PRICE_FONT, fontSize: 13, marginBottom: 12 }}>
          {friendlyError(checkoutError, "Couldn't start checkout — please try again.")}
        </p>
      )}

      <h2 style={{ ...sectionTitle, marginTop: 0 }}>Subscription plans</h2>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        {TIERS.map((tier, idx) => {
          const isCurrent = idx === currentTierIndex;
          const isPopular = tier.popular;

          return (
            <div
              key={tier.key}
              style={{
                border: isPopular
                  ? '1.5px solid #6F1F06'
                  : '1px solid var(--color-paper-surface)',
                borderRadius: '4px',
                padding: '16px 18px',
                background: isPopular ? 'var(--color-paper-surface)' : 'var(--color-paper-bg)',
                flex: 1,
                minWidth: '180px',
                position: 'relative',
              }}
            >
              {/* Popular badge */}
              {isPopular && (
                <div style={{
                  position: 'absolute', top: -1, right: 12,
                  background: '#6F1F06',
                  color: 'var(--color-paper-bg)',
                  fontSize: 9, fontFamily: PRICE_FONT, fontWeight: 700,
                  letterSpacing: '0.08em', textTransform: 'uppercase',
                  padding: '2px 8px',
                  borderRadius: '0 0 3px 3px',
                }}>
                  Popular
                </div>
              )}

              <p style={{
                fontFamily: "'Inknut Antiqua', 'Noto Serif', serif",
                fontWeight: 500, fontSize: '15px',
                color: 'var(--color-paper-dark)', margin: '0 0 4px',
              }}>
                {tier.label}
              </p>

              <p style={{
                fontFamily: PRICE_FONT,
                fontSize: '18px', fontWeight: 600,
                color: 'var(--color-brand-600)',
                margin: '0 0 12px',
              }}>
                {tier.price}
              </p>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {[
                  `${tier.lr} Literature Review/month`,
                  `${tier.pdf} PDF Agent/month`,
                  `${tier.gap} Research Gap/month`,
                ].map((line) => (
                  <p key={line} style={{
                    fontSize: 13, margin: 0,
                    fontFamily: PRICE_FONT,
                    color: 'var(--color-paper-mid)',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <Icon icon="mdi:check" style={{ fontSize: 14, color: 'var(--color-paper-light)', flexShrink: 0 }} />
                    {line}
                  </p>
                ))}
              </div>

              <button
                style={{
                  ...baseButtonStyle,
                  ...(isCurrent ? {
                    background: 'transparent',
                    border: '1px solid var(--color-paper-surface)',
                    color: 'var(--color-paper-light)',
                    cursor: 'default',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  } : isPopular ? {
                    background: '#6F1F06',
                    border: '1px solid #6F1F06',
                    color: 'var(--color-paper-bg)',
                  } : {}),
                }}
                disabled={isCurrent}
                onClick={() => !isCurrent && handleTierAction(tier.key)}
                onMouseEnter={(e) => {
                  if (!isCurrent && !isPopular) e.currentTarget.style.borderColor = 'var(--color-paper-dark)';
                }}
                onMouseLeave={(e) => {
                  if (!isCurrent && !isPopular) e.currentTarget.style.borderColor = 'var(--color-paper-surface)';
                }}
              >
                {isCurrent && <Icon icon="mdi:check-circle-outline" style={{ fontSize: 15 }} />}
                {isCurrent ? 'Current plan' : idx > currentTierIndex ? 'Upgrade' : 'Downgrade'}
              </button>
            </div>
          );
        })}
      </div>

      <h2 style={sectionTitle}>Top-up</h2>
      <p style={{ fontSize: 13, color: 'var(--color-paper-light)', fontFamily: PRICE_FONT, marginTop: '-8px', marginBottom: 12 }}>
        Available for Free/Plus only — Unlimited does not need top-ups.
      </p>
      <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
        {TOPUP_PACKS.map((pack) => (
          <div key={pack.key} style={{
            border: pack.combo
              ? '1.5px solid var(--color-brand-600)'
              : '1px solid var(--color-paper-surface)',
            borderRadius: '4px',
            padding: '16px 18px',
            background: pack.combo ? 'var(--color-brand-50)' : 'var(--color-paper-bg)',
            flex: 1, minWidth: '150px',
          }}>
            <p style={{ fontFamily: "'Inknut Antiqua', 'Noto Serif', serif", fontWeight: 500, fontSize: 14, margin: '0 0 2px', color: 'var(--color-paper-dark)' }}>
              {pack.label}
            </p>
            <p style={{ fontFamily: PRICE_FONT, fontSize: 17, fontWeight: 600, color: 'var(--color-brand-600)', margin: '0 0 6px' }}>
              {pack.price}
            </p>
            {pack.combo && (
              <p style={{ fontSize: 11, fontFamily: PRICE_FONT, color: 'var(--color-brand-600)', margin: '0 0 4px', fontStyle: 'italic' }}>
                Bundle and save
              </p>
            )}
            <button
              style={{
                ...baseButtonStyle,
                ...(pack.combo ? {
                  background: 'var(--color-brand-600)',
                  border: '1px solid var(--color-brand-600)',
                  color: '#fff',
                } : {}),
              }}
              onClick={() => checkoutTopup(pack.key)}
              onMouseEnter={(e) => {
                if (!pack.combo) e.currentTarget.style.borderColor = 'var(--color-paper-dark)';
              }}
              onMouseLeave={(e) => {
                if (!pack.combo) e.currentTarget.style.borderColor = 'var(--color-paper-surface)';
              }}
            >
              Buy
            </button>
          </div>
        ))}
      </div>

      {pendingCheckout && <CheckoutModal checkout={pendingCheckout} onClose={clearPendingCheckout} />}
    </div>
  );
};

export default BillingPanel;
