import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { ROUTES } from '@/shared/constant/routes';
import { useChatStore } from '@/shared/store/useChatStore';

const overlayStyle = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.35)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 10000,
};

const cardStyle = {
  background: 'var(--color-paper-surface)',
  border: '1px solid rgba(41, 17, 0, 0.08)',
  borderRadius: '16px',
  boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 16px 48px rgba(41, 17, 0, 0.18)',
  width: '560px',
  maxWidth: '90vw',
  padding: '24px',
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
};

// One entry per AI tool — adding a new app later is a one-line change here.
// `prefill` (instead of a standalone route) opens a fresh chat session with
// the textarea pre-seeded, for tools that live inside the chat flow rather
// than on their own page (see Literature Review pillar in ChatPage.jsx).
const APPS = [
  {
    key: 'literature-review',
    label: 'Literature Review',
    description: 'Search, screen, and summarise papers on any topic',
    icon: 'mdi:text-search',
    route: ROUTES.APP,
    prefill: 'Literature Review: ',
  },
  {
    key: 'research-gap',
    label: 'Research Gap',
    description: 'Find contradictions and understudied angles across papers',
    icon: 'mdi:lightbulb-on-outline',
    route: ROUTES.RESEARCH,
  },
  {
    key: 'pdf-agent',
    label: 'PDF Agent',
    description: 'Upload PDF/LaTeX, critique + verify citations',
    icon: 'mdi:file-search-outline',
    route: ROUTES.PDF_AGENT,
  },
];

const AppLauncherModal = ({ isOpen, onClose }) => {
  const navigate = useNavigate();
  const newSession = useChatStore((s) => s.newSession);
  const createServerChat = useChatStore((s) => s.createServerChat);
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

  const handleSelect = async (app) => {
    onClose();
    if (app.prefill) {
      try {
        await createServerChat();
      } catch {
        newSession();
      }
      navigate(app.route, { state: { prefillText: app.prefill } });
      return;
    }
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
          onClick={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
          onKeyDown={(e) => {
            if (e.key === 'Escape') onClose();
          }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            style={cardStyle}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                border: '1px solid rgba(41, 17, 0, 0.12)',
                borderRadius: '10px',
                padding: '12px 14px',
                background: 'var(--color-paper-bg)',
              }}
            >
              <Icon
                icon="mdi:magnify"
                style={{ width: 19, height: 19, color: 'var(--color-paper-mid)', flexShrink: 0 }}
              />
              <input
                ref={inputRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search applications..."
                style={{
                  fontFamily: "'Newsreader', serif",
                  fontSize: '16px',
                  color: 'var(--color-paper-dark)',
                  border: 'none',
                  outline: 'none',
                  background: 'none',
                  width: '100%',
                }}
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {results.map((app) => (
                <button
                  key={app.key}
                  onClick={() => handleSelect(app)}
                  style={{
                    width: '100%',
                    textAlign: 'left',
                    padding: '14px 14px',
                    background: 'none',
                    border: 'none',
                    borderRadius: '10px',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '14px',
                    transition: 'background 0.12s',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-paper-bg)')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
                >
                  <Icon
                    icon={app.icon}
                    style={{
                      width: 26,
                      height: 26,
                      color: 'var(--color-brand-500)',
                      flexShrink: 0,
                    }}
                  />
                  <div style={{ minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: '16px',
                        fontWeight: 600,
                        fontFamily: "'Newsreader', serif",
                        color: 'var(--color-paper-dark)',
                      }}
                    >
                      {app.label}
                    </div>
                    <div
                      style={{
                        fontSize: '14px',
                        color: 'var(--color-paper-mid)',
                        fontFamily: "'Newsreader', serif",
                        marginTop: '2px',
                      }}
                    >
                      {app.description}
                    </div>
                  </div>
                </button>
              ))}
              {results.length === 0 && (
                <p
                  style={{
                    textAlign: 'center',
                    fontSize: '14px',
                    color: 'var(--color-paper-mid)',
                    fontFamily: "'Newsreader', serif",
                    padding: '14px 0',
                  }}
                >
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
