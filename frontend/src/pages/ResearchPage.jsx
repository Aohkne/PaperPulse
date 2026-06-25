import { Icon } from '@iconify/react';
import GapSection from '@/features/gap/GapSection';

const ResearchPage = () => (
  <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
    {/* ── Toolbar ───────────────────────────────────────────────────── */}
    <div style={{
      flexShrink: 0, borderBottom: '1px solid var(--color-paper-light)',
      padding: '10px 20px', display: 'flex', alignItems: 'center', gap: '8px',
      background: 'var(--color-paper-bg)',
    }}>
      <Icon icon="mdi:lightbulb-search-outline" style={{ width: 18, height: 18, color: 'var(--color-paper-mid)', flexShrink: 0 }} />
      <span style={{ flex: 1, fontFamily: 'var(--font-inknut)', fontSize: '20px', fontWeight: 700, color: 'var(--color-paper-dark)' }}>
        Research Gap — Find Contradictions &amp; Understudied Angles
      </span>
    </div>

    {/* ── Body ──────────────────────────────────────────────────────── */}
    <div style={{ flex: 1, minHeight: 0, padding: '20px' }}>
      <GapSection />
    </div>
  </div>
);

export default ResearchPage;
