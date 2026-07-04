import { Icon } from '@iconify/react';
import GapSection from '@/features/gap/GapSection';

const ResearchPage = () => (
  <div className="themed-scroll" style={{ flex: 1, display: 'flex', flexDirection: 'column', overflowY: 'auto', minHeight: 0 }}>
    {/* Toolbar */}
    <div style={{
      position: 'sticky', top: 0, zIndex: 10,
      flexShrink: 0, boxShadow: '0 1px 3px rgba(41, 17, 0, 0.08)',
      padding: '10px 20px', display: 'flex', alignItems: 'center', gap: '8px',
      background: 'var(--color-paper-bg)',
    }}>
      <Icon icon="mdi:lightbulb-search-outline" style={{ width: 18, height: 18, color: 'var(--color-paper-mid)', flexShrink: 0 }} />
      <span style={{ flex: 1, fontFamily: 'var(--font-inknut)', fontSize: '20px', fontWeight: 700, color: 'var(--color-paper-dark)' }}>
        Research Gap — Find Contradictions &amp; Understudied Angles
      </span>
      <button
        onClick={() => window.Supademo?.open('cmqyjgpno068kw60j9xtqnwe8')}
        title="How it works"
        style={{
          flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: 28, height: 28, borderRadius: '50%',
          border: '1px solid var(--color-paper-light)', background: 'var(--color-paper-bg)',
          color: 'var(--color-paper-mid)', cursor: 'pointer',
        }}
      >
        {/* Plain "?" glyph (mdi:help), not mdi:help-circle-outline — that
            icon already draws its own circle, which doubled up with this
            button's own circular border into a nested ring-in-a-ring look. */}
        <Icon icon="mdi:help" style={{ width: 14, height: 14 }} />
      </button>
    </div>

    {/* Body */}
    <div style={{ flexShrink: 0, padding: '20px' }}>
      <GapSection />
    </div>
  </div>
);

export default ResearchPage;
