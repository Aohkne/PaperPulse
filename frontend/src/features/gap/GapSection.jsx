import useGapStore from './useGapStore';
import ColdStartInput from './ColdStartInput';
import GapResultPanel from './GapResultPanel';
import GapProgressPanel from './GapProgressPanel';

/**
 * GapSection — Gaps tab panel content (TIP-G07: cold-start flow).
 *
 * Layout:
 *   ┌─────────────────────────────┐
 *   │  ColdStartInput (topic UI)  │
 *   ├─────────────────────────────┤
 *   │  GapResultPanel (results)   │
 *   └─────────────────────────────┘
 *
 * Entry point is now ColdStartInput — no gate on session papers.
 * GapResultPanel handles loading / error / insufficient / success states.
 *
 * GapButton is kept exported for backward-compat (warm-start re-enable path),
 * but is no longer mounted in this component.
 */

// warm-start disabled (Lưu ý 2) — re-enable later
// export const GapButton = ({ papers = [], snowballedPapers = [] }) => {
//   const { findResearchGaps, gapLoading } = useGapStore();
//   const disabled = (papers.length + snowballedPapers.length) === 0 || gapLoading;
//   return (
//     <button
//       onClick={findResearchGaps}
//       disabled={disabled}
//       style={{
//         display: 'flex', alignItems: 'center', gap: '6px', padding: '6px 12px',
//         fontSize: '12px', fontWeight: 600,
//         background: disabled ? 'var(--color-paper-surface)' : 'var(--color-brand-600)',
//         color: disabled ? 'var(--color-paper-light)' : '#fff',
//         border: 'none', borderRadius: '5px', cursor: disabled ? 'default' : 'pointer',
//         width: '100%', justifyContent: 'center', transition: 'background 0.15s',
//       }}
//     >
//       <Icon icon="mdi:lightbulb-search-outline" style={{ fontSize: '13px' }} />
//       ⑨ Find Research Gap
//     </button>
//   );
// };

const GapSection = () => {
  const { gapNarrative, gapReport, gapLoading, gapError, streamEvents, streamGaps } = useGapStore();

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
      {/* ① Topic input — always visible, no paper-count gate */}
      <ColdStartInput onSubmit={streamGaps} />

      {/* ② Progress Panel - shows during streaming */}
      <GapProgressPanel events={streamEvents} loading={gapLoading} />

      {/* ③ Results panel — flows naturally in page scroll */}
      <GapResultPanel narrative={gapNarrative} gapReport={gapReport} loading={gapLoading} error={gapError} />
    </div>
  );
};

export default GapSection;
