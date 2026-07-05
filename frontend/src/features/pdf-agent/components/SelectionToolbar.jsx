import { useState } from 'react';
import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * Fixed bar above the editor (not a floating popup pinned to the cursor) — same
 * functional contract as PLAN §7 Phase 7 (2 fixed actions, appears on selection),
 * simpler/more robust than tracking Monaco scroll position for an on-canvas popup.
 */
const SelectionToolbar = ({ selection, onExplain, onRewrite }) => {
  const [instruction, setInstruction] = useState('');

  return (
    <AnimatePresence>
      {selection && (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          style={{
            flexShrink: 0,
            overflow: 'hidden',
            borderBottom: '1px solid var(--color-paper-light)',
            background: 'var(--color-paper-surface)',
            padding: '8px 14px',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <Icon
            icon="mdi:cursor-text"
            style={{ width: 14, height: 14, color: 'var(--color-paper-mid)', flexShrink: 0 }}
          />
          <span
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: '12px',
              color: 'var(--color-paper-mid)',
              flexShrink: 0,
            }}
          >
            {selection.selectedText.length} characters selected
          </span>
          <input
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="Instruction for rewrite (optional)..."
            style={{
              flex: 1,
              minWidth: 0,
              fontFamily: "'Newsreader', serif",
              fontSize: '12px',
              border: '1px solid var(--color-paper-light)',
              borderRadius: '4px',
              padding: '4px 8px',
              background: 'var(--color-paper-bg)',
              outline: 'none',
            }}
          />
          <button
            onClick={onExplain}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              flexShrink: 0,
              fontFamily: "'Newsreader', serif",
              fontSize: '12px',
              color: 'var(--color-paper-dark)',
              border: '1px solid var(--color-paper-light)',
              borderRadius: '4px',
              padding: '4px 10px',
              background: 'var(--color-paper-bg)',
              cursor: 'pointer',
            }}
          >
            <Icon icon="mdi:help-circle-outline" style={{ width: 13, height: 13 }} />
            Explain
          </button>
          <button
            onClick={() => onRewrite(instruction.trim() || null)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              flexShrink: 0,
              fontFamily: "'Newsreader', serif",
              fontSize: '12px',
              color: 'var(--color-paper-bg)',
              border: 'none',
              borderRadius: '4px',
              padding: '4px 10px',
              background: 'var(--color-paper-dark)',
              cursor: 'pointer',
            }}
          >
            <Icon icon="mdi:auto-fix" style={{ width: 13, height: 13 }} />
            Rewrite
          </button>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default SelectionToolbar;
