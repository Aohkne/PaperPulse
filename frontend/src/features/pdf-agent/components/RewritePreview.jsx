import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';
import { friendlyError } from '@/shared/utils/errorMessage';

/**
 * Banner shown under SelectionToolbar for the result of /explain (plain text, no
 * approval needed) or /rewrite (old/new diff blocks — only written to the doc when
 * the user clicks Apply, per Non-goals: never auto-apply an LLM edit).
 */
const RewritePreview = ({ result, onApply, onClose }) => {
  if (!result) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, height: 0 }}
        animate={{ opacity: 1, height: 'auto' }}
        exit={{ opacity: 0, height: 0 }}
        style={{
          flexShrink: 0,
          overflow: 'hidden',
          borderBottom: '1px solid var(--color-paper-light)',
          background: 'var(--color-paper-bg)',
          padding: '12px 16px',
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start',
            gap: '8px',
          }}
        >
          <div style={{ flex: 1, minWidth: 0 }}>
            {result.loading && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  fontFamily: "'Newsreader', serif",
                  fontSize: '13px',
                  color: 'var(--color-paper-mid)',
                }}
              >
                <Icon
                  icon="mdi:loading"
                  style={{ width: 14, height: 14, animation: 'spin 1s linear infinite' }}
                />
                {result.kind === 'rewrite' ? 'Rewriting...' : 'Explaining...'}
              </div>
            )}

            {result.kind === 'error' && (
              <div
                style={{ fontFamily: "'Newsreader', serif", fontSize: '13px', color: '#c0392b' }}
              >
                {friendlyError(result.message, 'Something went wrong.')}
              </div>
            )}

            {result.kind === 'explain' && !result.loading && (
              <div
                style={{
                  fontFamily: "'Newsreader', serif",
                  fontSize: '13px',
                  color: 'var(--color-paper-dark)',
                  lineHeight: 1.6,
                }}
              >
                {result.explanation}
              </div>
            )}

            {result.kind === 'rewrite' && !result.loading && (
              <div>
                <div
                  style={{
                    fontFamily: "'Newsreader', serif",
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--color-paper-mid)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    marginBottom: '4px',
                  }}
                >
                  Current
                </div>
                <div
                  style={{
                    fontFamily: "'Newsreader', serif",
                    fontSize: '13px',
                    color: '#c0392b',
                    background: '#fdf0ee',
                    borderRadius: '4px',
                    padding: '6px 8px',
                    marginBottom: '8px',
                    textDecoration: 'line-through',
                  }}
                >
                  {result.oldText}
                </div>
                <div
                  style={{
                    fontFamily: "'Newsreader', serif",
                    fontSize: '11px',
                    fontWeight: 600,
                    color: 'var(--color-paper-mid)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    marginBottom: '4px',
                  }}
                >
                  Suggested
                </div>
                <div
                  style={{
                    fontFamily: "'Newsreader', serif",
                    fontSize: '13px',
                    color: '#1f7a3d',
                    background: '#eef8f0',
                    borderRadius: '4px',
                    padding: '6px 8px',
                  }}
                >
                  {result.newText}
                </div>
              </div>
            )}
          </div>

          <button
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-paper-mid)',
              padding: 0,
              flexShrink: 0,
            }}
          >
            <Icon icon="mdi:close" style={{ width: 16, height: 16 }} />
          </button>
        </div>

        {result.kind === 'rewrite' && !result.loading && (
          <div style={{ marginTop: '10px', display: 'flex', gap: '6px' }}>
            <button
              onClick={onApply}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                fontFamily: "'Newsreader', serif",
                fontSize: '12px',
                color: '#fff',
                background: '#1f7a3d',
                border: 'none',
                borderRadius: '4px',
                padding: '5px 12px',
                cursor: 'pointer',
              }}
            >
              <Icon icon="mdi:check" style={{ width: 13, height: 13 }} /> Apply
            </button>
            <button
              onClick={onClose}
              style={{
                fontFamily: "'Newsreader', serif",
                fontSize: '12px',
                color: 'var(--color-paper-mid)',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '4px',
                padding: '5px 12px',
                background: 'none',
                cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </div>
        )}
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </motion.div>
    </AnimatePresence>
  );
};

export default RewritePreview;
