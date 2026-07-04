import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';

// The spinner + "Thinking…" pill itself, reusable standalone or nested inside
// an existing message bubble (ChatMessage already renders its own avatar).
const TypingPill = () => (
  <div style={{
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '8px 12px',
    background: 'var(--color-paper-surface)',
    border: '1px solid var(--color-paper-light)',
    borderRadius: '16px',
    minHeight: '38px',
  }}>
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
      style={{ flexShrink: 0 }}
    >
      <Icon icon="mdi:loading" style={{ fontSize: '13px', color: 'var(--color-brand-500)' }} />
    </motion.div>
    <span style={{
      fontFamily: "'Newsreader', serif",
      fontSize: '13px',
      fontStyle: 'italic',
      color: 'var(--color-paper-dark)',
      opacity: 0.75,
    }}>
      Thinking…
    </span>
  </div>
);

const TypingIndicator = ({ inline = false }) => {
  if (inline) return <TypingPill />;

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 4 }}
      transition={{ duration: 0.2 }}
      style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '20px' }}
    >
      {/* Avatar */}
      <div style={{
        width: '28px', height: '28px',
        backgroundColor: 'var(--color-paper-mid)',
        borderRadius: '10px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0,
      }}>
        <span style={{ fontFamily: 'var(--font-inknut)', color: 'var(--color-paper-bg)', fontSize: '14px', fontWeight: 600, lineHeight: 1 }}>
          P
        </span>
      </div>

      <TypingPill />
    </motion.div>
  );
};

export default TypingIndicator;
