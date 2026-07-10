import { useState } from 'react';
import { Icon } from '@iconify/react';

const ALL_SOURCES = [
  { key: 'semantic_scholar', label: 'Semantic Scholar', locked: true },
  { key: 'openalex', label: 'OpenAlex' },
  { key: 'arxiv', label: 'arXiv' },
  { key: 'pubmed', label: 'PubMed' },
];

/**
 * ResearchPlanCard — Step 0c: shown when the graph pauses at plan_review,
 * before any search API calls are made. User can edit the sub-queries and
 * the selected sources, then approve to continue the pipeline.
 *
 * Props:
 *   planDescription   string
 *   subQueries        string[]
 *   sources           string[]   — subset of ALL_SOURCES keys
 *   onApprove         ({ sub_queries, sources }) => void
 */
const ResearchPlanCard = ({ planDescription = '', subQueries = [], sources = [], onApprove }) => {
  const [queries, setQueries] = useState(subQueries.length ? subQueries : ['']);
  const [selectedSources, setSelectedSources] = useState(
    sources.length ? sources : ['semantic_scholar', 'arxiv']
  );

  const updateQuery = (i, value) => setQueries((qs) => qs.map((q, idx) => (idx === i ? value : q)));

  const removeQuery = (i) => setQueries((qs) => qs.filter((_, idx) => idx !== i));

  const addQuery = () => setQueries((qs) => [...qs, '']);

  const toggleSource = (key) =>
    setSelectedSources((cur) => (cur.includes(key) ? cur.filter((s) => s !== key) : [...cur, key]));

  const handleApprove = () => {
    const cleaned = queries.map((q) => q.trim()).filter(Boolean);
    onApprove({
      sub_queries: cleaned,
      sources: selectedSources.length ? selectedSources : ['semantic_scholar'],
    });
  };

  return (
    <div
      style={{
        maxWidth: '620px',
        margin: '0 auto',
        padding: '24px',
        background: 'var(--color-paper-bg)',
        border: '1px solid var(--color-paper-surface)',
        borderRadius: '12px',
        boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
      }}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
        <div
          style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'rgba(99,102,241,0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          <Icon
            icon="mdi:clipboard-text-search-outline"
            style={{ fontSize: '18px', color: 'var(--color-brand-600)' }}
          />
        </div>
        <div>
          <p
            style={{
              fontSize: '13px',
              fontWeight: 700,
              color: 'var(--color-paper-dark)',
              margin: 0,
            }}
          >
            Step 0 — Research plan ready
          </p>
          <p style={{ fontSize: '11px', color: 'var(--color-paper-mid)', margin: 0 }}>
            Review or edit before any search API calls are made.
          </p>
        </div>
      </div>

      {planDescription && (
        <p
          style={{
            fontSize: '13px',
            lineHeight: '1.6',
            color: 'var(--color-paper-dark)',
            background: 'var(--color-paper-surface)',
            borderRadius: '8px',
            padding: '10px 12px',
            margin: '0 0 16px',
          }}
        >
          {planDescription}
        </p>
      )}

      {/* Sub-queries */}
      <p
        style={{
          fontSize: '11px',
          fontWeight: 700,
          color: 'var(--color-paper-mid)',
          margin: '0 0 8px',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Sub-queries ({queries.length})
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '14px' }}>
        {queries.map((q, i) => (
          <div key={i} style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
            <input
              value={q}
              onChange={(e) => updateQuery(i, e.target.value)}
              style={{
                flex: 1,
                padding: '7px 10px',
                fontSize: '12px',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '6px',
                background: 'var(--color-paper-bg)',
                color: 'var(--color-paper-dark)',
                outline: 'none',
                fontFamily: 'inherit',
              }}
            />
            <button
              type="button"
              onClick={() => removeQuery(i)}
              title="Remove"
              style={{
                width: '26px',
                height: '26px',
                flexShrink: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                background: 'transparent',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--color-paper-mid)',
                borderRadius: '5px',
              }}
            >
              <Icon icon="mdi:close" style={{ fontSize: '14px' }} />
            </button>
          </div>
        ))}
        <button
          type="button"
          onClick={addQuery}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '5px',
            alignSelf: 'flex-start',
            fontSize: '11px',
            color: 'var(--color-brand-600)',
            background: 'transparent',
            border: 'none',
            cursor: 'pointer',
            padding: '4px 2px',
          }}
        >
          <Icon icon="mdi:plus" style={{ fontSize: '13px' }} />
          Add sub-query
        </button>
      </div>

      {/* Sources */}
      <p
        style={{
          fontSize: '11px',
          fontWeight: 700,
          color: 'var(--color-paper-mid)',
          margin: '0 0 8px',
          textTransform: 'uppercase',
          letterSpacing: '0.04em',
        }}
      >
        Sources
      </p>
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '20px' }}>
        {ALL_SOURCES.map(({ key, label, locked }) => {
          const active = selectedSources.includes(key);
          return (
            <button
              key={key}
              type="button"
              disabled={locked}
              onClick={() => !locked && toggleSource(key)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 12px',
                fontSize: '11px',
                fontWeight: 600,
                borderRadius: '20px',
                cursor: locked ? 'default' : 'pointer',
                border: active
                  ? '1px solid var(--color-brand-600)'
                  : '1px solid var(--color-paper-light)',
                background: active ? 'rgba(99,102,241,0.1)' : 'transparent',
                color: active ? 'var(--color-brand-600)' : 'var(--color-paper-light)',
                opacity: locked ? 0.85 : 1,
              }}
            >
              <Icon
                icon={active ? 'mdi:check-circle' : 'mdi:circle-outline'}
                style={{ fontSize: '13px' }}
              />
              {label}
              {locked && <span style={{ fontSize: '9px', opacity: 0.7 }}>(always on)</span>}
            </button>
          );
        })}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <button
          onClick={handleApprove}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '8px 18px',
            fontSize: '13px',
            fontWeight: 700,
            background: 'var(--color-brand-600)',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          <Icon icon="mdi:play-circle-outline" style={{ fontSize: '15px' }} />
          Approve & Search →
        </button>
      </div>
    </div>
  );
};

export default ResearchPlanCard;
