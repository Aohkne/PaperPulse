import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { ROUTES } from '@/shared/constant/routes';

const overlayStyle = {
  position: 'fixed', inset: 0,
  background: 'rgba(0,0,0,0.35)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 10000,
};

const cardStyle = {
  background: 'var(--color-paper-bg)',
  border: '1px solid var(--color-paper-light)',
  borderRadius: '6px',
  boxShadow: '0 16px 48px rgba(0,0,0,0.18)',
  width: '420px',
  padding: '16px',
  display: 'flex',
  flexDirection: 'column',
  gap: '12px',
};

// One entry per AI tool — adding a new app later is a one-line change here.
const APPS = [
  { key: 'research-gap', label: 'Research Gap', description: 'Find contradictions and understudied angles across papers', icon: 'mdi:lightbulb-on-outline', route: ROUTES.RESEARCH },
  { key: 'pdf-agent', label: 'PDF Agent', description: 'Upload PDF/LaTeX, critique + verify citations', icon: 'mdi:file-search-outline', route: ROUTES.PDF_AGENT },
];

const AppLauncherModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const inputRef = useRef(null);

  // Reset the search box when the modal re-opens — adjusted during render
  // (no effect needed for derived state, see React docs "You Might Not Need
  // an Effect"), same pattern as SaveReviewModal.jsx.
  const [prevIsOpen, setPrevIsOpen] = useState(isOpen);
  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (isOpen) setQuery('');
  }

  // Focus the input shortly after opening — a real imperative side effect.
  useEffect(() => {
    if (!isOpen) return;
    const id = setTimeout(() => inputRef.current?.focus(), 60);
    return () => clearTimeout(id);
  }, [isOpen]);

  const results = APPS.filter((app) =>
    app.label.toLowerCase().includes(query.trim().toLowerCase())
  );

  const handleSelect = (app) => {
    onClose();
    navigate(app.route);
  };

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          style={overlayStyle}
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
          onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            style={cardStyle}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '8px 10px' }}>
              <Icon icon="mdi:magnify" style={{ width: 16, height: 16, color: 'var(--color-paper-light)', flexShrink: 0 }} />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search applications..."
                style={{
                  fontFamily: "'Noto Serif', serif", fontSize: '14px',
                  color: 'var(--color-paper-dark)', border: 'none', outline: 'none',
                  background: 'none', width: '100%',
                }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {results.map((app) => (
                <button
                  key={app.key}
                  onClick={() => handleSelect(app)}
                  style={{
                    width: '100%', textAlign: 'left', padding: '10px 10px',
                    background: 'none', border: 'none', borderRadius: '4px', cursor: 'pointer',
                    display: 'flex', alignItems: 'center', gap: '10px',
                    transition: 'background 0.12s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-paper-surface)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                >
                  <Icon icon={app.icon} style={{ width: 20, height: 20, color: 'var(--color-paper-mid)', flexShrink: 0 }} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontSize: '14px', fontFamily: "'Noto Serif', serif", color: 'var(--color-paper-dark)' }}>
                      {app.label}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--color-paper-light)', fontFamily: "'Noto Serif', serif" }}>
                      {app.description}
                    </div>
                  </div>
                </button>
              ))}
              {results.length === 0 && (
                <p style={{ textAlign: 'center', fontSize: '13px', color: 'var(--color-paper-light)', fontFamily: "'Noto Serif', serif", padding: '12px 0' }}>
                  No applications found.
                </p>
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default AppLauncherModal;
