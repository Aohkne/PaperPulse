import { useRef, useEffect } from 'react';
import { Icon } from '@iconify/react';

const PipelineLog = ({ log = [], v2Running = false, query = '', planDescription = '' }) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [log.length]);

  if (log.length === 0 && !v2Running) return null;

  const loadingText = planDescription
    ? planDescription
    : query
      ? `Analyzing: "${query.length > 60 ? query.slice(0, 60) + '…' : query}"…`
      : 'Starting pipeline…';

  return (
    <div style={{ marginTop: '12px' }}>
      <p style={{
        fontSize: '11px',
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: 'var(--color-paper-light)',
        marginBottom: '6px',
        paddingLeft: '2px',
      }}>
        Log
      </p>
      <div style={{
        border: '1px solid var(--color-paper-surface)',
        borderRadius: '6px',
        maxHeight: '180px',
        overflowY: 'auto',
        background: 'var(--color-paper-bg)',
      }}>
        {v2Running && log.length === 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 10px',
            fontSize: '11px',
            color: 'var(--color-paper-light)',
          }}>
            <Icon icon="mdi:loading" className="animate-spin" style={{ fontSize: '12px', flexShrink: 0 }} />
            <span style={{ fontStyle: 'italic' }}>{loadingText}</span>
          </div>
        )}
        {log.map((entry, i) => (
          <div key={i} style={{
            padding: '5px 10px',
            fontSize: '11px',
            color: 'var(--color-paper-mid)',
            borderBottom: i < log.length - 1 ? '1px solid var(--color-paper-surface)' : 'none',
            lineHeight: '1.4',
          }}>
            <span style={{
              fontFamily: 'monospace',
              fontSize: '10px',
              background: 'var(--color-paper-surface)',
              padding: '1px 5px',
              borderRadius: '3px',
              marginRight: '6px',
              color: 'var(--color-brand-600)',
            }}>
              {entry.stepNum}
            </span>
            {entry.content}
            {entry.stat && (
              <span style={{
                marginLeft: '6px',
                fontFamily: 'monospace',
                fontSize: '10px',
                color: 'var(--color-paper-light)',
              }}>
                [{entry.stat}]
              </span>
            )}
          </div>
        ))}
        {/* Show active loading row after last completed step */}
        {v2Running && log.length > 0 && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '5px 10px',
            fontSize: '11px',
            color: 'var(--color-paper-light)',
            borderTop: '1px solid var(--color-paper-surface)',
            fontStyle: 'italic',
          }}>
            <Icon icon="mdi:loading" className="animate-spin" style={{ fontSize: '11px', flexShrink: 0 }} />
            Processing…
          </div>
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default PipelineLog;
