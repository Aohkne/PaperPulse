import { useState, useRef, useCallback } from 'react';
import { Icon } from '@iconify/react';
import GraphPanel from '@/features/graph/GraphPanel';
import { useIsMobile } from '@/shared/hooks/useIsMobile';

const MOBILE_TABS = [
  { key: 'left', label: 'Search' },
  { key: 'center', label: 'Outline' },
  { key: 'right', label: 'Graph' },
];

/**
 * 3-panel resizable layout for the Research Assistant:
 *   Left: search/progress/papers
 *   Center: outline / review editor
 *   Right: knowledge graph + claim verifier
 *
 * Below the mobile breakpoint, the 3 side-by-side panels (24%/flex/28% width)
 * become unusably narrow — swap to one full-width panel at a time with a tab
 * switcher instead, same pattern as PDFAgentPage's editor/annotations tabs.
 */
const ResearchLayout = ({ left, center, right, papers }) => {
  const isMobile = useIsMobile(860);
  const [mobileTab, setMobileTab] = useState('center');
  const [leftW, setLeftW] = useState(24);
  const [rightW, setRightW] = useState(28);
  const [rightOpen, setRightOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef(null);
  const dragging = useRef(null);

  const onMouseDown = useCallback(
    (side) => (e) => {
      e.preventDefault();
      dragging.current = side;
      setIsDragging(true);

      const onMove = (e) => {
        if (!containerRef.current || !dragging.current) return;
        const { left: cLeft, width } = containerRef.current.getBoundingClientRect();
        const pct = ((e.clientX - cLeft) / width) * 100;

        if (dragging.current === 'left') {
          setLeftW(Math.max(16, Math.min(32, pct)));
        } else {
          setRightW(Math.max(18, Math.min(40, 100 - pct)));
        }
      };

      const onUp = () => {
        dragging.current = null;
        setIsDragging(false);
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };

      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    },
    []
  );

  const divider = {
    width: '1px',
    flexShrink: 0,
    cursor: 'col-resize',
    background: 'var(--color-paper-light)',
    transition: 'background 0.15s',
  };

  const panelBase = {
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    height: '100%',
  };

  if (isMobile) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minHeight: 0,
          background: 'var(--color-paper-bg)',
        }}
      >
        <div
          style={{
            flexShrink: 0,
            display: 'flex',
            borderBottom: '1px solid var(--color-paper-light)',
          }}
        >
          {MOBILE_TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setMobileTab(tab.key)}
              style={{
                flex: 1,
                padding: '12px 8px',
                minHeight: 44,
                border: 'none',
                borderBottom:
                  mobileTab === tab.key
                    ? '2px solid var(--color-paper-dark)'
                    : '2px solid transparent',
                background: 'none',
                cursor: 'pointer',
                fontFamily: "'Newsreader', serif",
                fontSize: '13px',
                fontWeight: mobileTab === tab.key ? 600 : 400,
                color: mobileTab === tab.key ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            display: mobileTab === 'left' ? 'flex' : 'none',
            flexDirection: 'column',
            padding: '16px',
          }}
        >
          {left}
        </div>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            display: mobileTab === 'center' ? 'flex' : 'none',
            flexDirection: 'column',
            padding: '16px',
          }}
        >
          {center}
        </div>
        <div
          style={{
            flex: 1,
            minHeight: 0,
            overflowY: 'auto',
            display: mobileTab === 'right' ? 'flex' : 'none',
            flexDirection: 'column',
          }}
        >
          <GraphPanel papers={papers} onClose={() => setMobileTab('center')} />
          <div style={{ padding: '0 12px 12px' }}>{right}</div>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        flex: 1,
        minHeight: 0,
        background: 'var(--color-paper-bg)',
        userSelect: isDragging ? 'none' : 'auto',
      }}
    >
      {/* ── Left panel ─────────────────────────────────────────────────── */}
      <div
        style={{
          ...panelBase,
          width: `${leftW}%`,
          flexShrink: 0,
          overflowY: 'auto',
          padding: '20px 16px',
        }}
      >
        {left}
      </div>

      <div
        style={divider}
        onMouseDown={onMouseDown('left')}
        onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-paper-mid)')}
        onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-paper-light)')}
      />

      {/* ── Center panel ───────────────────────────────────────────────── */}
      <div style={{ ...panelBase, flex: 1, minWidth: 0, padding: '20px', position: 'relative' }}>
        {!rightOpen && (
          <button
            onClick={() => setRightOpen(true)}
            title="Open Graph & Claims"
            style={{
              position: 'absolute',
              top: '12px',
              right: '10px',
              zIndex: 10,
              background: 'var(--color-paper-bg)',
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
            <Icon icon="mdi:graph-outline" style={{ fontSize: '15px' }} />
          </button>
        )}
        {center}
      </div>

      {/* ── Right panel ────────────────────────────────────────────────── */}
      {rightOpen && (
        <>
          <div
            style={divider}
            onMouseDown={onMouseDown('right')}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-paper-mid)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-paper-light)')}
          />
          <div style={{ ...panelBase, width: `${rightW}%`, flexShrink: 0, overflowY: 'auto' }}>
            <GraphPanel papers={papers} onClose={() => setRightOpen(false)} />
            <div style={{ padding: '0 12px 12px' }}>{right}</div>
          </div>
        </>
      )}
    </div>
  );
};

export default ResearchLayout;
