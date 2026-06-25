import { Icon } from '@iconify/react';

const ASPECT_LABELS = {
  clarity: 'Clarity',
  terminology: 'Terminology',
  flow: 'Flow',
  redundancy: 'Redundancy',
  citation_not_found: 'Citation not found',
  metadata_mismatch: 'Citation metadata mismatch',
  broken_link: 'Broken link',
  missing_asset: 'Missing image file',
};

const AnnotationCard = ({ annotation, onAction, onClick, active }) => {
  const isWarning = annotation.type === 'warning';
  const accent = isWarning ? '#c0392b' : '#b8860b';
  const accentBg = isWarning ? '#fdf0ee' : '#fdf6e3';

  return (
    <div
      onClick={onClick}
      style={{
        border: `1px solid ${active ? accent : 'var(--color-paper-light)'}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: '6px',
        padding: '10px 12px',
        marginBottom: '8px',
        background: active ? accentBg : 'var(--color-paper-bg)',
        cursor: 'pointer',
        transition: 'background 0.12s, border-color 0.12s',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
        <Icon
          icon={isWarning ? 'mdi:alert-circle-outline' : 'mdi:lightbulb-outline'}
          style={{ width: 14, height: 14, color: accent, flexShrink: 0 }}
        />
        <span style={{ fontFamily: 'Georgia, serif', fontSize: '11px', fontWeight: 700, color: accent, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {ASPECT_LABELS[annotation.aspect] ?? annotation.aspect}
        </span>
      </div>

      <div style={{ fontFamily: 'Georgia, serif', fontSize: '12px', color: 'var(--color-paper-mid)', fontStyle: 'italic', marginBottom: '6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        "{annotation.anchor.exact}"
      </div>

      <div style={{ fontFamily: 'Georgia, serif', fontSize: '13px', color: 'var(--color-paper-dark)', marginBottom: annotation.suggested_fix ? '8px' : 0 }}>
        {annotation.comment}
      </div>

      {annotation.suggested_fix && (
        <div style={{ fontFamily: 'Georgia, serif', fontSize: '13px', color: '#1f7a3d', background: '#eef8f0', borderRadius: '4px', padding: '6px 8px', marginBottom: '8px' }}>
          → {annotation.suggested_fix}
        </div>
      )}

      {annotation.evidence?.title && (
        <div style={{ fontFamily: 'Georgia, serif', fontSize: '11px', color: 'var(--color-paper-light)', marginBottom: '8px' }}>
          Closely matches: {annotation.evidence.title} ({annotation.evidence.year ?? '?'})
        </div>
      )}

      <div style={{ display: 'flex', gap: '6px' }} onClick={(e) => e.stopPropagation()}>
        {isWarning ? (
          <button
            onClick={() => onAction('dismiss')}
            style={{ fontFamily: 'Georgia, serif', fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '3px 9px', background: 'none', cursor: 'pointer' }}
          >
            Dismiss
          </button>
        ) : (
          <>
            <button
              onClick={() => onAction('accept')}
              style={{ display: 'flex', alignItems: 'center', gap: '3px', fontFamily: 'Georgia, serif', fontSize: '12px', color: '#fff', background: '#1f7a3d', border: 'none', borderRadius: '4px', padding: '3px 9px', cursor: 'pointer' }}
            >
              <Icon icon="mdi:check" style={{ width: 12, height: 12 }} /> Accept
            </button>
            <button
              onClick={() => onAction('reject')}
              style={{ display: 'flex', alignItems: 'center', gap: '3px', fontFamily: 'Georgia, serif', fontSize: '12px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '4px', padding: '3px 9px', background: 'none', cursor: 'pointer' }}
            >
              <Icon icon="mdi:close" style={{ width: 12, height: 12 }} /> Reject
            </button>
          </>
        )}
      </div>
    </div>
  );
};

export default AnnotationCard;
