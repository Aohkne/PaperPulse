import { useRef, useEffect, useState } from 'react';
import { Icon } from '@iconify/react';

/**
 * ThinkingPanel — shows the LLM's streaming token output from the intent_router.
 *
 * Props:
 *   text        string   — accumulated raw token text (including <thinking> tags)
 *   isStreaming bool     — true while tokens are still arriving
 *   query       string   — the user's original question (shown as context header)
 *
 * Extracts content between <thinking>…</thinking> for display.
 * If no closing tag yet (still streaming), shows everything after <thinking>.
 */
const ThinkingPanel = ({ text = '', isStreaming = false, query = '' }) => {
  const bottomRef = useRef(null);
  const [collapsed, setCollapsed] = useState(false);

  // Extract inner text from <thinking> block
  const raw = text || '';
  let display = raw;
  if (raw.includes('<thinking>')) {
    const after = raw.split('<thinking>')[1] ?? '';
    display = after.includes('</thinking>')
      ? after.split('</thinking>')[0]
      : after; // still streaming
  }

  useEffect(() => {
    if (!collapsed) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [text, collapsed]);

  // Don't render if there's nothing yet and we're not streaming
  if (!text && !isStreaming) return null;

  return (
    <div style={{
      marginBottom: '12px',
      border: '1px solid rgba(139,92,246,0.25)',
      borderRadius: '8px',
      background: 'rgba(139,92,246,0.04)',
      overflow: 'hidden',
    }}>
      {/* Header */}
      <button
        onClick={() => setCollapsed((c) => !c)}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'center',
          gap: '7px',
          padding: '8px 12px',
          background: 'transparent',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {isStreaming && !collapsed
          ? <Icon icon="mdi:loading" className="animate-spin"
              style={{ fontSize: '13px', color: '#7c3aed', flexShrink: 0 }} />
          : <Icon icon="mdi:brain"
              style={{ fontSize: '13px', color: '#7c3aed', flexShrink: 0 }} />
        }
        <span style={{ fontSize: '11px', fontWeight: 700, color: '#6d28d9', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Thinking
        </span>
        {query && (
          <span style={{
            fontSize: '11px', color: '#7c3aed', opacity: 0.75,
            fontWeight: 400, marginLeft: '4px',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
            maxWidth: '260px',
          }}>
            — "{query}"
          </span>
        )}
        {isStreaming && (
          <span style={{ fontSize: '10px', color: '#7c3aed', marginLeft: '4px' }}>…</span>
        )}
        <Icon
          icon={collapsed ? 'mdi:chevron-down' : 'mdi:chevron-up'}
          style={{ fontSize: '14px', color: '#7c3aed', marginLeft: 'auto' }}
        />
      </button>

      {/* Body — only render when there's actual content to show */}
      {!collapsed && display && (
        <div style={{
          padding: '0 12px 10px',
          maxHeight: '200px',
          overflowY: 'auto',
          fontSize: '12px',
          lineHeight: '1.7',
          color: '#5b21b6',
          fontStyle: 'italic',
          whiteSpace: 'pre-wrap',
          wordBreak: 'break-word',
        }}>
          {display}
          {isStreaming && (
            <span style={{
              display: 'inline-block',
              width: '2px',
              height: '13px',
              background: '#7c3aed',
              marginLeft: '2px',
              verticalAlign: 'text-bottom',
              animation: 'blink 0.9s step-end infinite',
            }} />
          )}
          <div ref={bottomRef} />
        </div>
      )}

      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
};

export default ThinkingPanel;
