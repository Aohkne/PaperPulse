import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { QRCodeSVG } from 'qrcode.react';
import { useBillingStore } from '@/shared/store/useBillingStore';
import { friendlyError } from '@/shared/utils/errorMessage';

// Lora has full Vietnamese Unicode support — fixes "đ" rendering
const PRICE_FONT = "'Lora', 'Newsreader', serif";

// Token-weighted billing: one shared monthly credit pool per tier (credits=null
// → unlimited). All features (LR · PDF · Research Gap) draw from it.
const TIERS = [
  { key: 'free',      label: 'Free',      price: '0đ',              credits: 50 },
  { key: 'plus',      label: 'Plus',      price: '19.000đ/month',   credits: 100, popular: true },
  { key: 'unlimited', label: 'Unlimited', price: '299.000đ/month',  credits: null },
];

const sectionTitle = {
  fontFamily: "'Lora', 'Newsreader', serif",
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
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(41,17,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 10001,
      }}
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.92, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.95, y: 8 }}
        transition={{ type: 'spring', stiffness: 340, damping: 28 }}
        style={{
          background: 'var(--color-paper-bg)',
          border: '1px solid var(--color-paper-surface)',
          borderRadius: '10px',
          padding: '28px', maxWidth: '360px', textAlign: 'center',
          boxShadow: '0 16px 48px rgba(41,17,0,0.22)',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <AnimatePresence mode="wait">
          {status === 'paid' ? (
            <motion.div
              key="success"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.div
                initial={{ scale: 0, rotate: -45 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: 'spring', stiffness: 320, damping: 14, delay: 0.05 }}
              >
                <Icon icon="mdi:check-circle" style={{ fontSize: 56, color: '#10b981' }} />
              </motion.div>
              <p style={{ marginTop: 14, fontFamily: PRICE_FONT, fontSize: 16, fontWeight: 600, color: 'var(--color-paper-dark)' }}>
                Payment successful
              </p>
              <p style={{ marginTop: 4, fontFamily: PRICE_FONT, fontSize: 13, color: 'var(--color-paper-mid)' }}>
                Your account has been updated.
              </p>
            </motion.div>
          ) : (
            <motion.div
              key="pending"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <p style={{ fontFamily: PRICE_FONT, fontSize: 14, fontWeight: 600, color: 'var(--color-paper-dark)', margin: '0 0 4px' }}>
                Scan to pay
              </p>
              <p style={{ fontFamily: PRICE_FONT, fontSize: 22, fontWeight: 700, color: 'var(--color-brand-600)', margin: '0 0 18px' }}>
                {checkout.amount_vnd.toLocaleString('vi-VN')}đ
              </p>

              <div style={{ position: 'relative', width: 236, height: 236, margin: '0 auto' }}>
                <motion.div
                  animate={{ opacity: [0.55, 0.15, 0.55], scale: [1, 1.045, 1] }}
                  transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
                  style={{
                    position: 'absolute', inset: 0, borderRadius: 14,
                    border: '2px solid var(--color-brand-500)', pointerEvents: 'none',
                  }}
                />
                <div style={{
                  position: 'relative', width: '100%', height: '100%',
                  background: '#fff', borderRadius: 12, padding: 8, boxSizing: 'border-box',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  boxShadow: '0 4px 16px rgba(41,17,0,0.10)',
                }}>
                  <QRCodeSVG value={checkout.qr_code} size={204} />
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 16 }}>
                <motion.span
                  animate={{ opacity: [1, 0.3, 1] }}
                  transition={{ duration: 1.4, repeat: Infinity, ease: 'easeInOut' }}
                  style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--color-paper-light)', display: 'inline-block', flexShrink: 0 }}
                />
                <p style={{ fontSize: 12, color: 'var(--color-paper-mid)', fontFamily: PRICE_FONT, margin: 0 }}>
                  {status === 'pending' ? 'Waiting for payment...' : `Status: ${status}`}
                </p>
              </div>

              <a href={checkout.checkout_url} target="_blank" rel="noreferrer"
                style={{ display: 'inline-block', marginTop: 10, fontSize: 13, color: 'var(--color-brand-600)', fontFamily: PRICE_FONT, textDecoration: 'underline' }}>
                Open banking app
              </a>
            </motion.div>
          )}
        </AnimatePresence>

        <button style={{ ...baseButtonStyle, marginTop: 18 }} onClick={onClose}>Close</button>
      </motion.div>
    </motion.div>
  );
};

const BillingPanel = () => {
  const account = useBillingStore((s) => s.account);
  const fetchAccount = useBillingStore((s) => s.fetchAccount);
  const checkoutSubscription = useBillingStore((s) => s.checkoutSubscription);
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
                fontFamily: "'Fraunces', 'Newsreader', serif",
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
                {(tier.credits === null
                  ? ['Unlimited usage — no monthly cap', 'All tools — LR · PDF · Research Gap', 'Knowledge Graph included free']
                  : [`${tier.credits} credits / month`, 'One shared pool — LR · PDF · Research Gap', 'Knowledge Graph included free']
                ).map((line) => (
                  <p key={line} style={{
                    fontSize: 13, margin: 0,
                    fontFamily: PRICE_FONT,
                    color: 'var(--color-paper-mid)',
                    display: 'flex', alignItems: 'center', gap: 6,
                  }}>
                    <Icon icon="mdi:check" style={{ fontSize: 14, color: 'var(--color-paper-mid)', flexShrink: 0 }} />
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

      <p style={{ fontSize: 13, color: 'var(--color-paper-mid)', fontFamily: PRICE_FONT, marginTop: 4 }}>
        All features share one monthly credit pool. When it runs out, upgrade or wait for the next period — there is no top-up.
      </p>

      <AnimatePresence>
        {pendingCheckout && <CheckoutModal checkout={pendingCheckout} onClose={clearPendingCheckout} />}
      </AnimatePresence>
    </div>
  );
};

export default BillingPanel;
