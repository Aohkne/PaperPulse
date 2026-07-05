import { Icon } from '@iconify/react';
import KnowledgeGraph from './KnowledgeGraph';

const GraphPanel = ({ onClose, papers = [] }) => {
  const paperCount = papers.length;
  const authorCount = new Set(papers.flatMap((p) => p.authors ?? [])).size;
  const statsLabel =
    paperCount > 0
      ? `${paperCount} papers · ${authorCount} authors`
      : '34 papers · 12 authors · 8 topics';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div
        style={{
          padding: '14px 14px 10px',
          flexShrink: 0,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <p
            style={{
              fontFamily: 'var(--font-inknut)',
              color: 'var(--color-paper-dark)',
              fontSize: '15px',
              fontWeight: 600,
              margin: 0,
              lineHeight: 1.3,
            }}
          >
            Knowledge Graph
          </p>
          <p
            style={{
              color: 'var(--color-paper-mid)',
              fontSize: '12px',
              margin: '3px 0 0',
              fontFamily: "'Newsreader', serif",
            }}
          >
            {statsLabel}
          </p>
        </div>

        <button
          onClick={onClose}
          title="Close Knowledge Graph"
          style={{
            background: 'transparent',
            border: '1px solid var(--color-paper-light)',
            borderRadius: '4px',
            cursor: 'pointer',
            padding: '4px 6px',
            color: 'var(--color-paper-mid)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <Icon icon="mdi:panel-right-close" style={{ fontSize: '15px' }} />
        </button>
      </div>

      {/* Graph fills remaining space */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <KnowledgeGraph papers={papers} />
      </div>
    </div>
  );
};

export default GraphPanel;
