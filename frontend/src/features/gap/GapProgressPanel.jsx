import { useState } from 'react';
import { Icon } from '@iconify/react';

const NODE_LABELS = {
  extractor: 'Document extraction',
  topical_detector: 'Topical gap detection',
  method_detector: 'Methodological gap detection',
  contradiction_detector: 'Contradiction detection',
  verifier: 'Gap verification',
  counter_search: 'Counter-evidence check',
  synthesizer: 'Report synthesis',
};

const NODE_ORDER = [
  'extractor',
  'topical_detector',
  'method_detector',
  'contradiction_detector',
  'verifier',
  'counter_search',
  'synthesizer',
];

const STEP_COLORS = {
  pending: 'var(--color-paper-light)',
  active: 'var(--color-paper-mid)',
  passed: 'var(--color-paper-dark)',
};

const GapProgressPanel = ({ events = [], loading }) => {
  const [collapsed, setCollapsed] = useState(false);

  if (!loading && events.length === 0) return null;

  const activeNodes = events.filter((e) => e.type === 'node_start').map((e) => e.node);
  const isDone = events.some((e) => e.type === 'done');
  const currentNode =
    !isDone && activeNodes.length > 0 ? activeNodes[activeNodes.length - 1] : null;
  const passedNodes = activeNodes.slice(0, -1);
  if (isDone) passedNodes.push(...activeNodes.filter((n) => !passedNodes.includes(n)));

  // No outer border — paper-surface is near-white, so it read as a plain
  // white outline. boxShadow alone is enough to lift this card off the
  // page. (The borderBottom on the header button below stays — that one
  // actually separates the header from the step list, it's a real content
  // divider, not decorative ambient framing.)
  return (
    <section
      style={{
        borderRadius: '14px',
        background: 'var(--color-paper-bg)',
        boxShadow: '0 10px 28px rgba(41, 17, 0, 0.05)',
        overflow: 'hidden',
      }}
    >
      <button
        onClick={() => setCollapsed((v) => !v)}
        style={{
          width: '100%',
          padding: '16px 20px 14px',
          borderBottom: collapsed ? 'none' : '1px solid var(--color-paper-surface)',
          display: 'flex',
          alignItems: 'center',
          gap: '10px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        <Icon
          icon={loading && !isDone ? 'mdi:loading' : 'mdi:progress-check'}
          style={{
            fontSize: '19px',
            color: 'var(--color-paper-mid)',
            animation: loading && !isDone ? 'spin 1s linear infinite' : 'none',
            flexShrink: 0,
          }}
        />
        <div style={{ flex: 1 }}>
          <h3
            style={{
              fontFamily: 'var(--font-inknut)',
              fontSize: '15px',
              fontWeight: 700,
              color: 'var(--color-paper-dark)',
              margin: 0,
            }}
          >
            Analysis progress
          </h3>
          <p className="gap-pipeline-subtitle" style={{ margin: '2px 0 0', fontSize: '14px' }}>
            The pipeline updates as evidence is checked and gaps are synthesized.
          </p>
        </div>
        <Icon
          icon="mdi:chevron-down"
          style={{
            fontSize: '19px',
            color: 'var(--color-paper-mid)',
            flexShrink: 0,
            transform: collapsed ? 'rotate(-90deg)' : 'none',
            transition: 'transform 0.15s',
          }}
        />
      </button>

      {!collapsed && (
        <div style={{ padding: '14px 20px 16px' }}>
          <div style={{ display: 'grid', gap: '8px' }}>
            {NODE_ORDER.map((nodeId) => {
              const isPassed = passedNodes.includes(nodeId) || isDone;
              const isActive = currentNode === nodeId;
              const isPending = !isPassed && !isActive;

              let icon = 'mdi:circle-outline';
              let color = STEP_COLORS.pending;
              let spin = false;

              if (isPassed) {
                icon = 'mdi:check-circle';
                color = STEP_COLORS.passed;
              } else if (isActive) {
                icon = 'mdi:loading';
                color = STEP_COLORS.active;
                spin = true;
              }

              return (
                <div
                  key={nodeId}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                    fontFamily: 'var(--font-inknut)',
                    fontSize: '14px',
                    color: isPending ? 'var(--color-paper-light)' : 'var(--color-paper-dark)',
                    minHeight: '22px',
                  }}
                >
                  <Icon
                    icon={icon}
                    style={{
                      fontSize: '17px',
                      color,
                      flexShrink: 0,
                      animation: spin ? 'spin 1s linear infinite' : 'none',
                    }}
                  />
                  <span style={{ lineHeight: 1.4 }}>{NODE_LABELS[nodeId] || nodeId}</span>
                </div>
              );
            })}
          </div>
        </div>
      )}
      <style>{`
        @keyframes spin { 100% { transform: rotate(360deg); } }
        .gap-pipeline-subtitle { font-family: var(--font-noto-serif); font-weight: 400; color: #5a4a37; }
        html.dark .gap-pipeline-subtitle { color: var(--color-paper-light); }
      `}</style>
    </section>
  );
};

export default GapProgressPanel;
