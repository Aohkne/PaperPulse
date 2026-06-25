/**
 * GapQualityBadge — displays quality_score and origin of a gap
 *
 * Receives origin as a lowercase string from BE ("explicit", "limitation", "inferred")
 * or undefined → fallback to INFERRED.
 *
 * Quality tiers:
 *   >= 0.7 → High quality   (green)
 *   >= 0.4 → Medium quality (amber)
 *   < 0.4  → Low quality    (red)
 *   null   → tier badge not shown
 */

const ORIGIN_CONFIG = {
  EXPLICIT: {
    label: 'Explicit',
    color: 'var(--color-paper-mid)',
    bg: 'rgba(90, 107, 51, 0.12)',
    title: 'Directly stated by author',
  },
  LIMITATION: {
    label: 'Limitation',
    color: 'var(--color-paper-dark)',
    bg: 'rgba(181, 162, 63, 0.18)',
    title: 'From paper limitation section',
  },
  INFERRED: {
    label: 'AI-inferred',
    color: 'var(--color-paper-dark)',
    bg: 'rgba(237, 232, 212, 0.92)',
    title: 'Suggested by the analysis model from the available papers and evidence.',
  },
};

function getQualityTier(score) {
  if (score == null) return null;
  if (score >= 0.7) return { label: 'High quality', color: 'var(--color-paper-mid)', bg: 'rgba(90, 107, 51, 0.14)' };
  if (score >= 0.4) return { label: 'Medium quality', color: '#7A6530', bg: 'rgba(181, 162, 63, 0.16)' };
  return { label: 'Low quality', color: '#8B4A2F', bg: 'rgba(139, 74, 47, 0.12)' };
}

export default function GapQualityBadge({ quality, origin }) {
  // BE sends lowercase ("explicit"), lookup uses uppercase key
  const originKey = (origin || '').toUpperCase();
  const originCfg = ORIGIN_CONFIG[originKey] || ORIGIN_CONFIG.INFERRED;
  const tier = getQualityTier(quality);

  return (
    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', margin: '4px 0' }}>
      {/* Origin badge */}
      <span
        title={originCfg.title}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          padding: '2px 8px',
          borderRadius: '9999px',
          fontFamily: 'var(--font-inknut)',
          fontSize: '12px',
          fontWeight: 600,
          color: originCfg.color,
          backgroundColor: originCfg.bg,
          border: originKey === 'INFERRED' ? '1px solid var(--color-paper-light)' : `1px solid ${originCfg.color}33`,
        }}
      >
        {originCfg.label}
      </span>

      {/* Quality tier badge — only shown when quality_score is present */}
      {tier && (
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            padding: '2px 8px',
            borderRadius: '9999px',
            fontFamily: 'var(--font-inknut)',
            fontSize: '12px',
            fontWeight: 600,
            color: tier.color,
            backgroundColor: tier.bg,
            border: `1px solid ${tier.color}33`,
          }}
        >
          {tier.label}
        </span>
      )}
    </div>
  );
}
