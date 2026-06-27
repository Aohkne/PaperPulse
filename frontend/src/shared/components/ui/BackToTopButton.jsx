import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';

const BackToTopButton = () => {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > 320);
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <AnimatePresence>
      {visible && (
        <motion.button
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 10 }}
          transition={{ duration: 0.18 }}
          onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
          title="Back to top"
          style={{
            position: 'fixed', bottom: 32, right: 32, zIndex: 200,
            width: 40, height: 40,
            background: 'var(--color-paper-dark)',
            border: '1px solid transparent',
            borderRadius: 4,
            cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'var(--color-paper-bg)',
            boxShadow: '0 4px 16px rgba(41,17,0,0.18)',
            transition: 'background 0.15s',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'var(--color-brand-600)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--color-paper-dark)'; }}
        >
          <Icon icon="mdi:chevron-up" style={{ fontSize: 22 }} />
        </motion.button>
      )}
    </AnimatePresence>
  );
};

export default BackToTopButton;
