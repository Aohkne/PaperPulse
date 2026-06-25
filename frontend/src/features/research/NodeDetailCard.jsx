import { Icon } from '@iconify/react';
import { motion } from 'framer-motion';

const VERDICT_CFG = {
  supported:   { icon: 'mdi:check-circle',  color: '#16a34a', label: 'Supported' },
  partial:     { icon: 'mdi:circle-half-full', color: '#d97706', label: 'Partially supported' },
  uncertain:   { icon: 'mdi:help-circle',   color: '#71717a', label: 'Uncertain' },
  unsupported: { icon: 'mdi:close-circle',  color: '#dc2626', label: 'Unsupported' },
  pending:     { icon: 'mdi:dots-horizontal-circle', color: '#94a3b8', label: 'Pending' },
};

const INTENT_EDGE_CFG = {
  supports: { color: '#16a34a', label: 'Supports' },
  contradicts: { color: '#dc2626', label: 'Contradicts' },
  mentions: { color: '#9BAD5A', label: 'Mentions' },
};

const cardShell = {
  width: '100%', maxHeight: 280, overflowY: 'auto', boxSizing: 'border-box',
  background: 'var(--color-paper-bg)', border: '1px solid var(--color-paper-light)',
  borderRadius: 8, boxShadow: '0 2px 12px rgba(0,0,0,0.08)', padding: 14,
};

const CloseButton = ({ onClose }) => (
  <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-light)' }}>
    <Icon icon="mdi:close" style={{ fontSize: 16 }} />
  </button>
);

// ── Topic card — query + aggregate stats ──────────────────────────────────────
const TopicCard = ({ node, stats, onClose }) => (
  <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon icon="mdi:target" style={{ fontSize: 16, color: '#d97706' }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: '#d97706', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Topic</span>
      </div>
      <CloseButton onClose={onClose} />
    </div>
    <p style={{ fontSize: 14, lineHeight: 1.5, color: 'var(--color-paper-dark)', fontWeight: 600, margin: '0 0 12px' }}>
      {node.label}
    </p>
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
      {[
        ['mdi:file-document-outline', stats?.papers ?? 0, 'Papers'],
        ['mdi:shape-outline', stats?.themes ?? 0, 'Themes'],
        ['mdi:comment-quote-outline', stats?.claims ?? 0, 'Claims'],
        ['mdi:sword-cross', stats?.contradicts_edges ?? 0, 'Contradicts'],
      ].map(([icon, value, label]) => (
        <div key={label} style={{ padding: '8px 10px', background: 'var(--color-paper-surface)', borderRadius: 6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--color-paper-mid)' }}>
            <Icon icon={icon} style={{ fontSize: 13 }} />
            <span style={{ fontSize: 16, fontWeight: 700, color: 'var(--color-paper-dark)' }}>{value}</span>
          </div>
          <span style={{ fontSize: 10, color: 'var(--color-paper-light)' }}>{label}</span>
        </div>
      ))}
    </div>
  </>
);

// ── Theme card — paper list + supports/contradicts/mentions breakdown ────────
const ThemeCard = ({ node, themeId, raw, onClose }) => {
  const paperIds = (raw?.edges || [])
    .filter((e) => e.type === 'belongs_to' && e.target === themeId)
    .map((e) => e.source);
  const papers = paperIds
    .map((id) => raw.nodes.find((n) => n.id === id))
    .filter(Boolean);

  const breakdown = { supports: 0, contradicts: 0, mentions: 0 };
  for (const e of raw?.edges || []) {
    if (e.target === themeId && e.type in breakdown) breakdown[e.type] += 1;
  }

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon icon="mdi:shape-outline" style={{ fontSize: 16, color: '#94a3b8' }} />
          <span style={{ fontSize: 11, fontWeight: 700, color: '#71717a', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Theme</span>
        </div>
        <CloseButton onClose={onClose} />
      </div>
      <p style={{ fontSize: 14, lineHeight: 1.5, color: 'var(--color-paper-dark)', fontWeight: 600, margin: '0 0 10px' }}>
        {node.label}
      </p>

      <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
        {Object.entries(breakdown).map(([key, count]) => (
          <span key={key} style={{
            fontSize: 11, fontWeight: 600, padding: '2px 8px', borderRadius: 20,
            color: INTENT_EDGE_CFG[key].color,
            background: `${INTENT_EDGE_CFG[key].color}1a`,
          }}>
            {INTENT_EDGE_CFG[key].label}: {count}
          </span>
        ))}
      </div>

      <p style={{ fontSize: 11, color: 'var(--color-paper-light)', margin: '0 0 4px', fontWeight: 600 }}>
        Papers ({papers.length})
      </p>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
        {papers.map((p) => (
          <div key={p.id} style={{ fontSize: 12, color: 'var(--color-paper-dark)', padding: '4px 6px', background: 'var(--color-paper-surface)', borderRadius: 4 }}>
            {p.label}{p.year ? ` (${p.year})` : ''}
          </div>
        ))}
      </div>
    </>
  );
};

// ── Paper card — metadata + PDF link ──────────────────────────────────────────
const PaperCard = ({ node, onClose }) => (
  <>
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Icon icon="mdi:file-document-outline" style={{ fontSize: 16, color: '#4f86c6' }} />
        <span style={{ fontSize: 11, fontWeight: 700, color: '#4f86c6', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Paper</span>
      </div>
      <CloseButton onClose={onClose} />
    </div>
    <p style={{ fontSize: 14, lineHeight: 1.5, color: 'var(--color-paper-dark)', fontWeight: 600, margin: '0 0 10px' }}>
      {node.label}
    </p>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12, color: 'var(--color-paper-mid)' }}>
      {node.year && <div><Icon icon="mdi:calendar-outline" style={{ fontSize: 13, marginRight: 5 }} />{node.year}</div>}
      <div><Icon icon="mdi:format-quote-close" style={{ fontSize: 13, marginRight: 5 }} />{node.citation_count ?? 0} citations</div>
      {node.source && <div><Icon icon="mdi:database-outline" style={{ fontSize: 13, marginRight: 5 }} />{node.source}</div>}
    </div>
    {node.url && (
      <a
        href={node.url} target="_blank" rel="noreferrer"
        style={{
          display: 'inline-flex', alignItems: 'center', gap: 5, marginTop: 10,
          fontSize: 12, fontWeight: 600, color: '#4f86c6', textDecoration: 'none',
        }}
      >
        <Icon icon="mdi:open-in-new" style={{ fontSize: 13 }} />
        Open PDF
      </a>
    )}
  </>
);

// ── Claim card — verdict + confidence + evidence (Step ⑧ 3-tier verification) ──
const ClaimCard = ({ node, raw, onClose }) => {
  const cfg = VERDICT_CFG[node.verdict] || VERDICT_CFG.pending;
  const sourcePaper = raw?.nodes.find((n) => n.id === node.source_paper_id);

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <Icon icon={cfg.icon} style={{ fontSize: 16, color: cfg.color }} />
          <span style={{ fontSize: 12, fontWeight: 700, color: cfg.color }}>{cfg.label}</span>
        </div>
        <CloseButton onClose={onClose} />
      </div>

      <p style={{ fontSize: 13, lineHeight: 1.55, color: 'var(--color-paper-dark)', margin: '0 0 10px' }}>
        {node.label}
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
        <span style={{ fontSize: 11, color: 'var(--color-paper-light)' }}>Confidence</span>
        <div style={{ flex: 1, height: 5, background: 'var(--color-paper-surface)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{ width: `${(node.confidence ?? 0) * 100}%`, height: '100%', background: cfg.color }} />
        </div>
        <span style={{ fontSize: 11, color: 'var(--color-paper-mid)', fontFamily: 'monospace' }}>
          {Math.round((node.confidence ?? 0) * 100)}%
        </span>
      </div>

      {node.low_confidence && (
        <p style={{ fontSize: 11, color: '#d97706', margin: '4px 0 0', display: 'flex', alignItems: 'center', gap: 4 }}>
          <Icon icon="mdi:alert-outline" />
          Verified from abstract only (conservative) — review before trusting.
        </p>
      )}

      {node.snippet && (
        <blockquote style={{
          fontSize: 11, color: 'var(--color-paper-mid)', margin: '10px 0 0', padding: '6px 10px',
          borderLeft: '2px solid var(--color-paper-light)', fontStyle: 'italic',
        }}>
          "{node.snippet}"
        </blockquote>
      )}

      {sourcePaper && (
        <p style={{ fontSize: 10, color: 'var(--color-paper-light)', margin: '8px 0 0' }}>
          source: {sourcePaper.label}
        </p>
      )}
    </>
  );
};

/**
 * NodeDetailCard — generalized detail card for the Knowledge Graph
 * (renamed from ClaimEvidenceSidebar; knowledge-graph_SPEC_2.0.md §Nội dung
 * card theo node type). Renders different content per node `type`.
 */
const NodeDetailCard = ({ node, nodeId, raw, stats, onClose }) => {
  if (!node) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      style={cardShell}
    >
      {node.type === 'topic' && <TopicCard node={node} stats={stats} onClose={onClose} />}
      {node.type === 'theme' && <ThemeCard node={node} themeId={nodeId} raw={raw} onClose={onClose} />}
      {node.type === 'paper' && <PaperCard node={node} onClose={onClose} />}
      {node.type === 'claim' && <ClaimCard node={node} raw={raw} onClose={onClose} />}
    </motion.div>
  );
};

export default NodeDetailCard;
