import { useState, useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useReviewsStore } from '@/shared/store/useReviewsStore';

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
  padding: '24px',
  display: 'flex',
  flexDirection: 'column',
  gap: '16px',
};

// Strip LaTeX markup down to plain text for the short preview snippet below.
const stripLatexPreview = (latex) =>
  (latex || '')
    .replace(/\\documentclass[^\n]*\n?/g, '')
    .replace(/\\usepackage[^\n]*\n?/g, '')
    .replace(/\\(title|author|date)\{[^}]*\}\n?/g, '')
    .replace(/\\(begin|end)\{document\}\n?/g, '')
    .replace(/\\maketitle\n?/g, '')
    .replace(/\\(section|subsection|subsubsection)\*?\{([^}]*)\}/g, '$2. ')
    .replace(/\\(textbf|textit|emph)\{([^}]*)\}/g, '$2')
    .replace(/\\(begin|end)\{[a-zA-Z*]+\}/g, '')
    .replace(/\\item\s*/g, '')
    .replace(/[{}\\]/g, '')
    .trim();

// Inline toast that fades in from bottom
const Toast = ({ message, success }) => (
  <motion.div
    initial={{ opacity: 0, y: 8 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0 }}
    style={{
      position: 'fixed', bottom: '24px', left: '50%', transform: 'translateX(-50%)',
      background: success ? 'var(--color-paper-dark)' : '#c0392b',
      color: 'var(--color-paper-bg)',
      fontFamily: "'Noto Serif', serif", fontSize: '14px',
      padding: '10px 20px', borderRadius: '4px',
      boxShadow: '0 4px 16px rgba(0,0,0,0.2)',
      zIndex: 10001, whiteSpace: 'nowrap',
    }}
  >
    {message}
  </motion.div>
);

const SaveReviewModal = ({ isOpen, onClose, markdownContent, defaultTitle = '' }) => {
  const [title, setTitle] = useState(defaultTitle);
  const [toast, setToast] = useState(null);
  const saveReview = useReviewsStore((s) => s.saveReview);
  const saveLoading = useReviewsStore((s) => s.saveLoading);
  const inputRef = useRef(null);

  // Reset title/toast when the modal opens with a new defaultTitle — adjusted
  // during render (no effect needed for derived state, see React docs
  // "You Might Not Need an Effect").
  const [prevIsOpen, setPrevIsOpen] = useState(isOpen);
  const [prevDefaultTitle, setPrevDefaultTitle] = useState(defaultTitle);
  if (isOpen !== prevIsOpen || defaultTitle !== prevDefaultTitle) {
    setPrevIsOpen(isOpen);
    setPrevDefaultTitle(defaultTitle);
    if (isOpen) {
      setTitle(defaultTitle);
      setToast(null);
    }
  }

  // Focus the input shortly after opening — a real imperative side effect.
  useEffect(() => {
    if (!isOpen) return;
    const id = setTimeout(() => inputRef.current?.focus(), 60);
    return () => clearTimeout(id);
  }, [isOpen]);

  const handleSave = async () => {
    const trimmed = title.trim();
    if (!trimmed) return;
    try {
      await saveReview({ title: trimmed, query: defaultTitle, markdown_content: markdownContent });
      setToast({ message: 'Saved to My Reviews ✓', success: true });
      setTimeout(() => {
        setToast(null);
        onClose();
      }, 1400);
    } catch (e) {
      setToast({ message: e.message || 'Save failed', success: false });
      setTimeout(() => setToast(null), 3000);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !saveLoading) handleSave();
    if (e.key === 'Escape') onClose();
  };

  return createPortal(
    <>
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
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 8 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
              style={cardStyle}
            >
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <Icon icon="mdi:bookmark-plus-outline" style={{ width: 18, height: 18, color: 'var(--color-paper-mid)' }} />
                  <span style={{ fontFamily: "'Noto Serif', serif", fontSize: '15px', fontWeight: 600, color: 'var(--color-paper-dark)' }}>
                    Save to My Reviews
                  </span>
                </div>
                <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-light)', padding: 0, display: 'flex' }}>
                  <Icon icon="mdi:close" style={{ width: 18, height: 18 }} />
                </button>
              </div>

              {/* Title input */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-mid)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Review name
                </label>
                <input
                  ref={inputRef}
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Enter a review name..."
                  style={{
                    fontFamily: "'Noto Serif', serif", fontSize: '14px',
                    color: 'var(--color-paper-dark)',
                    border: '1px solid var(--color-paper-light)',
                    borderRadius: '4px',
                    padding: '8px 10px',
                    background: 'var(--color-paper-surface)',
                    outline: 'none',
                    width: '100%', boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Preview snippet */}
              {markdownContent && (
                <div style={{
                  background: 'var(--color-paper-surface)',
                  border: '1px solid var(--color-paper-light)',
                  borderRadius: '4px',
                  padding: '8px 10px',
                  fontFamily: "'Noto Serif', serif", fontSize: '12px',
                  color: 'var(--color-paper-light)',
                  lineHeight: '1.5',
                  maxHeight: '60px', overflow: 'hidden',
                }}>
                  {stripLatexPreview(markdownContent).slice(0, 160)}…
                </div>
              )}

              {/* Actions */}
              <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
                <button
                  onClick={onClose}
                  style={{
                    fontFamily: "'Noto Serif', serif", fontSize: '13px',
                    color: 'var(--color-paper-mid)',
                    border: '1px solid var(--color-paper-light)',
                    borderRadius: '4px', padding: '7px 16px',
                    background: 'none', cursor: 'pointer',
                  }}
                >
                  Cancel
                </button>
                <button
                  onClick={handleSave}
                  disabled={!title.trim() || saveLoading}
                  style={{
                    fontFamily: "'Noto Serif', serif", fontSize: '13px',
                    color: 'var(--color-paper-bg)',
                    background: title.trim() && !saveLoading ? 'var(--color-paper-dark)' : 'var(--color-paper-light)',
                    border: 'none', borderRadius: '4px', padding: '7px 16px',
                    cursor: title.trim() && !saveLoading ? 'pointer' : 'not-allowed',
                    display: 'flex', alignItems: 'center', gap: '6px',
                  }}
                >
                  {saveLoading && <Icon icon="mdi:loading" style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }} />}
                  Save to My Reviews
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Toast outside modal */}
      <AnimatePresence>
        {toast && <Toast key="toast" message={toast.message} success={toast.success} />}
      </AnimatePresence>

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </>,
    document.body
  );
};

export default SaveReviewModal;
