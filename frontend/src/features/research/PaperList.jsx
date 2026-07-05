import { useState } from 'react';
import { Icon } from '@iconify/react';

const PaperItem = ({ paper }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <li
      style={{
        padding: '10px 12px',
        borderBottom: '1px solid var(--color-paper-surface)',
        background: 'transparent',
      }}
    >
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          gap: '8px',
          alignItems: 'flex-start',
        }}
      >
        <p
          style={{
            fontSize: '12px',
            fontWeight: 600,
            color: 'var(--color-paper-dark)',
            lineHeight: '1.4',
            flex: 1,
            margin: 0,
          }}
        >
          {paper.title}
        </p>
        {paper.citationCount != null && (
          <span
            style={{
              fontSize: '11px',
              color: 'var(--color-paper-mid)',
              whiteSpace: 'nowrap',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '3px',
            }}
          >
            <Icon icon="mdi:format-quote-close" style={{ fontSize: '12px' }} />
            {paper.citationCount}
          </span>
        )}
      </div>

      <p
        style={{
          fontSize: '11px',
          color: 'var(--color-paper-light)',
          margin: '3px 0 0',
          lineHeight: '1.3',
        }}
      >
        {paper.authors?.slice(0, 3).join(', ')}
        {paper.authors?.length > 3 ? ' et al.' : ''}
        {paper.year ? ` · ${paper.year}` : ''}
      </p>

      {paper.abstract && (
        <>
          <p
            style={{
              fontSize: '11px',
              color: 'var(--color-paper-dark)',
              marginTop: '6px',
              lineHeight: '1.5',
              display: '-webkit-box',
              WebkitBoxOrient: 'vertical',
              WebkitLineClamp: expanded ? 'unset' : 2,
              overflow: 'hidden',
            }}
          >
            {paper.abstract}
          </p>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '11px',
              color: 'var(--color-brand-500)',
              padding: '2px 0',
              display: 'flex',
              alignItems: 'center',
              gap: '2px',
            }}
          >
            <Icon
              icon={expanded ? 'mdi:chevron-up' : 'mdi:chevron-down'}
              style={{ fontSize: '13px' }}
            />
            {expanded ? 'Less' : 'More'}
          </button>
        </>
      )}
    </li>
  );
};

const PaperList = ({ papers = [], snowballedPapers = [] }) => {
  const [showSnowballed, setShowSnowballed] = useState(false);
  const displayed = showSnowballed ? [...papers, ...snowballedPapers] : papers;

  if (displayed.length === 0) return null;

  return (
    <div style={{ marginTop: '12px' }}>
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '6px',
        }}
      >
        <p
          style={{ fontSize: '11px', fontWeight: 600, color: 'var(--color-paper-mid)', margin: 0 }}
        >
          {papers.length} papers
          {snowballedPapers.length > 0 && ` (+ ${snowballedPapers.length} snowballed)`}
        </p>
        {snowballedPapers.length > 0 && (
          <button
            onClick={() => setShowSnowballed(!showSnowballed)}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              fontSize: '11px',
              color: 'var(--color-brand-500)',
            }}
          >
            {showSnowballed ? 'Hide snowball' : 'Show snowball'}
          </button>
        )}
      </div>
      <ul
        style={{
          listStyle: 'none',
          margin: 0,
          padding: 0,
          border: '1px solid var(--color-paper-surface)',
          borderRadius: '6px',
          maxHeight: '340px',
          overflowY: 'auto',
        }}
      >
        {displayed.map((p) => (
          <PaperItem key={p.paperId} paper={p} />
        ))}
      </ul>
    </div>
  );
};

export default PaperList;
