import { Icon } from '@iconify/react';

/**
 * Placeholder — Research Gap testing is listed in the sidebar dropdown
 * ahead of its own pipeline being implemented (research-agent_SPEC_2.0.md
 * §Non-goals: gap identification is explicitly out of scope for the current
 * pipeline). Swap this in for a real testing UI once that feature exists.
 */
const ResearchGapTestingPage = () => (
  <div
    style={{
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      height: '100%',
      gap: 10,
      color: 'var(--color-admin-mid)',
      textAlign: 'center',
    }}
  >
    <Icon icon="mdi:wrench-clock-outline" style={{ fontSize: 32 }} />
    <h1 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--color-admin-text)' }}>
      Research Gap testing — coming soon
    </h1>
    <p style={{ margin: 0, fontSize: 13, maxWidth: 420 }}>
      The Research Gap detection pipeline hasn't been built yet. This page will get a testing UI
      (input + event streaming, same as Literature Review) once that feature ships.
    </p>
  </div>
);

export default ResearchGapTestingPage;
