import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Icon } from '@iconify/react';
import GapQualityBadge from './GapQualityBadge';
import { friendlyError } from '@/shared/utils/errorMessage';
import { showError } from '@/shared/utils/toast';

function normalizeVi(text) {
  if (!text) return text;
  return text.normalize('NFC');
}

function formatApaAuthor(name) {
  if (!name) return '';
  const parts = name.trim().split(/\s+/);
  if (parts.length < 2) return name;
  const last = parts[parts.length - 1];
  const initials = parts.slice(0, -1).map(p => p[0] + '.').join(' ');
  return `${last}, ${initials}`;
}

function formatApaAuthors(authors) {
  if (!authors || authors.length === 0) return null;
  const fmt = authors.map(formatApaAuthor);
  if (authors.length === 1) return fmt[0];
  if (authors.length > 20) {
    return fmt.slice(0, 19).join(', ') + ', … ' + fmt[fmt.length - 1];
  }
  return fmt.slice(0, -1).join(', ') + ', & ' + fmt[fmt.length - 1];
}

function stripGapSummary(text) {
  if (!text) return text;
  return text
    .replace(/^Showing top .*?research gaps by quality .*?See details in each gap card below\.?\s*$/gim, '')
    .replace(/^Showing top .*?research gaps by quality .*?\n?/gim, '')
    .trim();
}

// Reuse the Review markdown styling so gap narrative renders consistently.
const citationStyle = { fontSize: '12px', background: 'var(--color-paper-surface)', color: 'var(--color-paper-mid)', padding: '1px 5px', borderRadius: '3px', fontFamily: 'var(--font-inknut)' };

const mdComponents = {
  h1: ({ children }) => <h1 style={{ fontSize: '21px', fontWeight: 700, fontFamily: 'var(--font-inknut)', color: 'var(--color-paper-dark)', margin: '0 0 16px' }}>{children}</h1>,
  h2: ({ children }) => <h2 style={{ fontSize: '16px', fontWeight: 700, fontFamily: 'var(--font-inknut)', color: 'var(--color-paper-dark)', margin: '20px 0 8px', borderBottom: '1px solid var(--color-paper-surface)', paddingBottom: '4px' }}>{children}</h2>,
  h3: ({ children }) => <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--color-paper-dark)', margin: '12px 0 4px' }}>{children}</h3>,
  p: ({ children }) => <p style={{ fontSize: '14px', lineHeight: '1.8', color: 'var(--color-paper-dark)', margin: '0 0 8px' }}>{children}</p>,
  ul: ({ children }) => <ul style={{ margin: '4px 0 8px', paddingLeft: '18px' }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ margin: '4px 0 8px', paddingLeft: '18px' }}>{children}</ol>,
  li: ({ children }) => <li style={{ fontSize: '14px', lineHeight: '1.8', color: 'var(--color-paper-dark)', marginBottom: '2px' }}>{children}</li>,
  hr: () => <hr style={{ border: 'none', borderTop: '1px solid var(--color-paper-surface)', margin: '16px 0' }} />,
  code: ({ children }) => <code style={citationStyle}>{children}</code>,
};

const Centered = ({ icon, children }) => (
  <div style={{
    display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
    minHeight: '320px', gap: '16px', fontFamily: 'var(--font-inknut)',
    background: 'var(--color-paper-surface)', border: '1px dashed var(--color-paper-light)',
    borderRadius: '14px', padding: '40px 24px',
  }}>
    <Icon icon={icon} style={{ fontSize: '65px', color: 'var(--color-paper-light)' }} />
    <p style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-paper-mid)', margin: 0, textAlign: 'center', maxWidth: '380px', lineHeight: '1.5' }}>{children}</p>
  </div>
);

// gap_type badge labels — 'topical' was the only one mapped to a proper
// display string before; 'methodological' and 'contradiction' fell through
// and rendered as raw lowercase API values, so badges looked inconsistent
// card to card.
const GAP_TYPE_LABELS = {
  topical: 'Topic gap',
  methodological: 'Methodological gap',
  contradiction: 'Contradiction',
};

const AXIS_ORDER = [
  { key: 'grounding', label: 'Grounding' },
  { key: 'novelty', label: 'Novelty' },
  { key: 'actionable', label: 'Actionable' },
  { key: 'corpus_evidence', label: 'Corpus evidence' },
];

const AXIS_STYLES = {
  grounding: { fill: 'var(--color-paper-mid)', track: 'rgba(90, 107, 51, 0.14)' },
  novelty: { fill: 'var(--color-paper-light)', track: 'rgba(181, 162, 63, 0.18)' },
  actionable: { fill: '#8B4A2F', track: 'rgba(139, 74, 47, 0.12)' },
  corpus_evidence: { fill: '#8A9A6A', track: 'rgba(138, 154, 106, 0.14)' },
};

function getDistinctSupportingCount(supportingPapers) {
  if (!Array.isArray(supportingPapers) || supportingPapers.length === 0) return 0;
  const seen = new Set();
  for (const paper of supportingPapers) {
    const key = paper?.paper_id || paper?.paperId || paper?.title || '';
    if (key) seen.add(String(key));
  }
  return seen.size || supportingPapers.length;
}

function QualityMiniBars({ gap }) {
  const axes = gap?.quality_breakdown;
  if (!axes) return null;
  return (
    <div style={{ display: 'grid', gap: '6px', marginTop: '10px' }}>
      {AXIS_ORDER.map(({ key, label }) => {
        const value = typeof axes[key] === 'number' ? axes[key] : 0;
        const axisStyle = AXIS_STYLES[key];
        return (
          <div key={key} style={{ display: 'grid', gap: '4px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '10px' }}>
              <span style={{ fontFamily: 'var(--font-inknut)', fontSize: '12px', fontWeight: 600, color: 'var(--color-paper-dark)' }}>{label}</span>
              <span style={{ fontFamily: 'var(--font-inknut)', fontSize: '12px', color: 'var(--color-paper-mid)', fontVariantNumeric: 'tabular-nums' }}>{Math.round(value * 100)}%</span>
            </div>
            <div style={{ height: '6px', borderRadius: '999px', background: axisStyle.track, overflow: 'hidden' }}>
              <div
                style={{
                  width: `${Math.round(value * 100)}%`,
                  height: '100%',
                  borderRadius: '999px',
                  background: axisStyle.fill,
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function GapCard({ gap }) {
  const [detailsOpen, setDetailsOpen] = useState(false);
  // Quality breakdown now lives inside the same collapsible as method/
  // falsifiability instead of always rendering — it was duplicating the
  // compact "Medium quality" badge already shown at the top of the card,
  // and adding ~150px of always-visible chart per card pushed the actual
  // gap statement (the thing worth reading first) further down the page.
  const hasDetails = Boolean(gap.suggested_method || gap.falsifiability_condition || gap.quality_score != null);

  return (
    <div className="gap-item" style={{ background: 'var(--color-paper-bg)', padding: '16px 16px 14px', borderRadius: '14px', border: '1px solid var(--color-paper-surface)', boxShadow: '0 8px 18px rgba(41, 17, 0, 0.03)', fontFamily: 'var(--font-inknut)', display: 'flex', flexDirection: 'column' }}>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', alignItems: 'center', marginBottom: '12px' }}>
        <span
          title={gap.gap_type === 'topical' ? 'A gap about an underexplored research topic or direction.' : undefined}
          className={`gap-badge ${gap.gap_type}`}
          style={{ display: 'inline-block', padding: '2px 8px', borderRadius: '12px', fontFamily: 'var(--font-inknut)', fontSize: '12px', fontWeight: 600, color: 'var(--color-paper-dark)', background: 'var(--color-paper-surface)', border: '1px solid var(--color-paper-light)' }}
        >
          {GAP_TYPE_LABELS[gap.gap_type] || gap.gap_type}
        </span>
        <GapQualityBadge quality={gap.quality_score ?? null} origin={gap.origin} />
      </div>

      <div style={{ marginBottom: '12px', padding: '12px 14px', borderLeft: '4px solid var(--color-paper-light)', borderRadius: '0 12px 12px 0', background: 'linear-gradient(90deg, var(--color-paper-surface) 0%, var(--color-paper-bg) 100%)' }}>
        <div style={{ fontFamily: 'var(--font-inknut)', fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--color-paper-mid)', marginBottom: '6px' }}>
          Gap
        </div>
        <div style={{ fontFamily: 'var(--font-inknut)', fontSize: '16px', lineHeight: '1.5', color: 'var(--color-paper-dark)' }}>
          {normalizeVi(gap.statement)}
        </div>
        {gap.evidence_quotes?.length > 0 && (
          <div style={{ marginTop: '8px', fontFamily: 'var(--font-inknut)', fontSize: '13px', lineHeight: '1.6', color: 'var(--color-paper-mid)', fontStyle: 'italic' }}>
            "{normalizeVi(gap.evidence_quotes[0])}"
          </div>
        )}
      </div>

      {hasDetails && (
        <div style={{ marginBottom: '10px' }}>
          <button
            onClick={() => setDetailsOpen((v) => !v)}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 10px', fontFamily: 'var(--font-inknut)', fontSize: '13px', fontWeight: 600,
              color: 'var(--color-paper-mid)', background: 'var(--color-paper-surface)',
              border: 'none', borderRadius: '8px', cursor: 'pointer',
            }}
          >
            <span>{detailsOpen ? 'Hide quality & method details' : 'Show quality & method details'}</span>
            <Icon icon="mdi:chevron-down" style={{ fontSize: '16px', transform: detailsOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} />
          </button>

          {detailsOpen && (
            <div style={{ display: 'grid', gap: '10px', margin: '8px 0 0', padding: '10px 12px', background: 'var(--color-paper-surface)', borderRadius: '8px' }}>
              {gap.quality_score != null && (
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '12px' }}>
                    <strong style={{ fontFamily: 'var(--font-inknut)', fontSize: '14px', color: 'var(--color-paper-dark)' }}>
                      Quality
                    </strong>
                    <span style={{ fontFamily: 'var(--font-inknut)', fontSize: '12px', color: 'var(--color-paper-mid)' }}>
                      Based on {getDistinctSupportingCount(gap.supporting_papers)} papers
                    </span>
                  </div>
                  <QualityMiniBars gap={gap} />
                </div>
              )}

              {gap.suggested_method && (
                <div style={{ fontFamily: 'var(--font-noto-serif)', fontSize: '14px', color: 'var(--color-paper-dark)', lineHeight: '1.6' }}>
                  <strong>Suggested method:</strong> {normalizeVi(gap.suggested_method)}
                </div>
              )}

              {gap.falsifiability_condition && (
                <div style={{ fontFamily: 'var(--font-noto-serif)', fontSize: '14px', color: 'var(--color-paper-mid)', lineHeight: '1.6' }}>
                  <strong>Falsifiable when:</strong> {normalizeVi(gap.falsifiability_condition)}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {gap.supporting_papers?.length > 0 && (
        <div style={{ borderTop: '1px solid var(--color-paper-surface)', paddingTop: '10px' }}>
          <div style={{ fontFamily: 'var(--font-inknut)', fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--color-paper-mid)', marginBottom: '6px' }}>
            References
          </div>
          <ul style={{ margin: '0', padding: '0', listStyle: 'none', fontFamily: 'var(--font-noto-serif)', fontWeight: 400, fontSize: '13px', color: 'var(--color-paper-mid)' }}>
            {gap.supporting_papers.map((p, idx) => {
              const n = p.citation_index ?? (idx + 1);
              const year = p.year != null ? `(${p.year})` : '(n.d.)';
              const title = normalizeVi(p.title) || '';
              const authorStr = formatApaAuthors(p.authors);
              const body = authorStr
                ? `${authorStr} ${year}. ${title}.`
                : `${title}. ${year}.`;
              const linkHref = p.url || (p.doi ? `https://doi.org/${p.doi}` : null);
              return (
                <li key={p.paper_id} style={{ marginBottom: '4px', lineHeight: '1.5' }}>
                  [{n}] {body}{p.venue ? <> <em>{normalizeVi(p.venue)}.</em></> : null}
                  {linkHref && (
                    <> <a
                      href={linkHref}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{ color: 'var(--color-paper-mid)', fontFamily: 'var(--font-noto-serif)', fontWeight: 400, textDecoration: 'none', marginLeft: '4px' }}
                    >↗</a></>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </div>
  );
}

const GapResultPanel = ({ narrative, gapReport, loading, error }) => {
  useEffect(() => {
    if (error) showError(error, "We couldn't analyze research gaps for this topic.");
  }, [error]);

  if (loading) return null;
  if (error) return <Centered icon="mdi:alert-circle-outline">{friendlyError(error, "We couldn't analyze research gaps for this topic.")}</Centered>;
  if (!narrative) return <Centered icon="mdi:lightbulb-search-outline">Enter a topic to begin analysis.</Centered>

  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <style>{`
        .gap-list {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 16px;
          align-items: start;
        }
        @media (max-width: 760px) {
          .gap-list { grid-template-columns: 1fr; }
        }
      `}</style>
      <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--color-paper-dark)', margin: '0 0 14px', fontFamily: 'var(--font-inknut)', flexShrink: 0 }}>
        Research Gaps
      </h2>
      {/* Border dropped in favor of the boxShadow (same as the two boxes
          above it) — the 1px paper-light border was the "big border" under
          the Research Gaps heading that pressed right up against every gap
          card's own border inside it. */}
      <div style={{ padding: '18px', background: 'var(--color-paper-surface)', borderRadius: '14px', fontFamily: 'var(--font-inknut)', boxShadow: '0 10px 28px rgba(41, 17, 0, 0.04)' }}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
          {normalizeVi(stripGapSummary(narrative))}
        </ReactMarkdown>

        {gapReport?.gaps?.length > 0 && (
          <div className="gap-list" style={{ marginTop: '20px' }}>
            {gapReport.gaps.map((gap, i) => (
              <GapCard key={i} gap={gap} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export default GapResultPanel;
