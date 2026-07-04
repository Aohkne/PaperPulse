import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import KnowledgeGraphViewer from '@/features/research/KnowledgeGraphViewer';

/**
 * KnowledgeGraphDrawer — right-anchored overlay drawer for the Knowledge Graph.
 * Triggered from the left Sidebar; slides in from the right edge of the screen.
 */
const KnowledgeGraphDrawer = ({ open, onClose, threadId }) => (
  createPortal(
    <AnimatePresence>
      {open && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            style={{
              position: 'fixed', inset: 0,
              background: 'rgba(0,0,0,0.35)',
              zIndex: 998,
            }}
          />

          {/* Sliding panel */}
          <motion.div
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ type: 'spring', stiffness: 320, damping: 32 }}
            style={{
              position: 'fixed', top: 0, right: 0, bottom: 0,
              width: 'min(560px, 92vw)',
              background: 'var(--color-paper-bg)',
              borderLeft: '1px solid var(--color-paper-light)',
              boxShadow: '-8px 0 32px rgba(0,0,0,0.18)',
              zIndex: 999,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Header */}
            <div style={{
              padding: '14px 16px',
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              borderBottom: '1px solid var(--color-paper-surface)',
              flexShrink: 0,
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <Icon icon="mdi:graph-outline" style={{ fontSize: 17, color: 'var(--color-brand-600)' }} />
                <span style={{
                  fontFamily: 'var(--font-inknut)', fontSize: 15, fontWeight: 600,
                  color: 'var(--color-paper-dark)',
                }}>
                  Knowledge Graph
                </span>
              </div>
              <button
                onClick={onClose}
                title="Close"
                style={{
                  background: 'transparent', border: '1px solid var(--color-paper-light)',
                  borderRadius: 4, cursor: 'pointer', padding: '4px 6px',
                  color: 'var(--color-paper-mid)', display: 'flex', alignItems: 'center',
                }}
              >
                <Icon icon="mdi:close" style={{ fontSize: 15 }} />
              </button>
            </div>

            {/* Body */}
            <div className="themed-scroll" style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
              {threadId ? (
                <KnowledgeGraphViewer threadId={threadId} />
              ) : (
                <div style={{
                  display: 'flex', flexDirection: 'column', alignItems: 'center',
                  justifyContent: 'center', height: '100%', textAlign: 'center',
                  color: 'var(--color-paper-mid)', gap: 8, padding: '40px 20px',
                }}>
                  <Icon icon="mdi:graph-outline" style={{ fontSize: 32 }} />
                  <p style={{ fontSize: 13, margin: 0 }}>
                    No knowledge graph yet — run a research session first.
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  )
);

export default KnowledgeGraphDrawer;
