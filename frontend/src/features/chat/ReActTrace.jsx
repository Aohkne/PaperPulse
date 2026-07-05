import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';

// ─── Phase mapping ────────────────────────────────────────────────────────────
// The Literature Review pipeline is a FIXED backend graph (see
// backend/module/research_agent/api/research.py, _NODE_STEP_NUM) — stepNum
// "0".."7" always means the same node in the same order for this feature:
//   0 intent/plan · 1 search+dedup · 2 embed · 3 cluster · 4 write ·
//   5 extract+verify · 6 route+KG · 7 export
// Labels are English to stay consistent with the (English) step messages and
// the English literature-review output. If the backend reorders or adds nodes,
// this map is the one place to update.
const PHASE_DEFS = [
  { key: 'search', label: 'Search', icon: 'mdi:magnify', stepNums: ['0', '1'] },
  { key: 'cluster', label: 'Embed & cluster', icon: 'mdi:group', stepNums: ['2', '3'] },
  {
    key: 'analyze',
    label: 'Analyze & verify',
    icon: 'mdi:text-box-check-outline',
    stepNums: ['4', '5', '6'],
  },
  { key: 'export', label: 'Export', icon: 'mdi:file-export-outline', stepNums: ['7'] },
];

const TYPE_CFG = {
  thought: { icon: 'mdi:brain', label: 'Thought', color: '#B5A23F' },
  action: { icon: 'mdi:code-tags', label: 'Action', color: '#8040e8' },
  observation: {
    icon: 'mdi:eye-check-outline',
    label: 'Observation',
    color: 'var(--color-paper-mid)',
  },
};

// Groups the flat step list into the 4 fixed phases above. Phases with no
// steps yet (pipeline hasn't reached them) still render — as a pending node —
// so the trace reads as "step 2 of 4" progress instead of a list that just
// grows, matching the reassurance purpose Thư confirmed for this card.
function groupIntoPhases(steps) {
  const phases = PHASE_DEFS.map((def) => ({ ...def, steps: [] }));
  const unmatched = [];
  for (const s of steps) {
    const phase = phases.find((p) => p.stepNums.includes(String(s.stepNum)));
    if (phase) phase.steps.push(s);
    else unmatched.push(s);
  }
  if (unmatched.length) {
    phases.push({ key: 'other', label: 'Other', icon: 'mdi:dots-horizontal', steps: unmatched });
  }
  return phases;
}

function phaseStatus(phase) {
  if (!phase.steps.length) return 'pending';
  if (phase.steps.some((s) => s.status === 'error')) return 'error';
  if (phase.steps.some((s) => s.status === 'running')) return 'running';
  return 'done';
}

// Pulls the one all-in-one tally stat (e.g. "papers=67 themes=8 claims=45
// contradicts=0", emitted by the export step) into a plain sentence instead
// of dumping every step's raw `stat` string as a wall of chips. Falls back to
// nothing if the trace hasn't reached export yet — no half-finished tallies.
const STAT_LABELS = {
  papers: 'bài báo',
  themes: 'chủ đề',
  claims: 'trích dẫn',
  contradicts: 'mâu thuẫn',
};
function finalTally(steps) {
  const kvStats = steps
    .map((s) => s.stat)
    .filter((stat) => stat && /^(\w+=\S+\s*)+$/.test(stat.trim()));
  const raw = kvStats[kvStats.length - 1];
  if (!raw) return null;
  const pairs = raw
    .trim()
    .split(/\s+/)
    .map((pair) => pair.split('='));
  return pairs.map(([k, v]) => `${v} ${STAT_LABELS[k] ?? k}`).join(' · ');
}

const STATUS_ICON = {
  done: { icon: 'mdi:check-circle', color: 'var(--color-brand-500)' },
  running: { icon: 'mdi:loading', color: 'var(--color-brand-500)' },
  error: { icon: 'mdi:close-circle', color: '#dc2626' },
  pending: null,
};

// ─── Nested step row (shown once a phase is expanded) ────────────────────────
const NestedStep = ({ step }) => {
  const cfg = TYPE_CFG[step.type] ?? TYPE_CFG.observation;
  const isRunning = step.status === 'running';
  // Only label the type when it's the informative exception (thought/action).
  // Every phase in this trace is nearly all "observation" steps, so repeating
  // that word on every single line was pure noise — content alone says enough.
  const showTypeLabel = step.type === 'thought' || step.type === 'action';

  return (
    <div style={{ display: 'flex', gap: '8px', padding: '5px 0', alignItems: 'flex-start' }}>
      <div style={{ flexShrink: 0, paddingTop: '2px' }}>
        {isRunning ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
          >
            <Icon icon="mdi:loading" style={{ fontSize: '12px', color: cfg.color }} />
          </motion.div>
        ) : (
          <Icon icon={cfg.icon} style={{ fontSize: '12px', color: cfg.color, opacity: 0.7 }} />
        )}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {showTypeLabel && (
          <span
            style={{
              display: 'block',
              fontSize: '10px',
              fontWeight: 500,
              color: cfg.color,
              opacity: 0.75,
              marginBottom: '2px',
            }}
          >
            {cfg.label}
          </span>
        )}
        {step.type === 'action' ? (
          <code
            style={{
              fontFamily: '"Fira Code", "Courier New", monospace',
              fontSize: '11px',
              lineHeight: '1.5',
              display: 'block',
              wordBreak: 'break-word',
              color: 'var(--color-paper-dark)',
            }}
          >
            <span style={{ color: '#8040e8', fontWeight: 600 }}>{step.label}</span>
            <span style={{ color: 'var(--color-paper-mid)' }}>({step.args})</span>
          </code>
        ) : (
          <p
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: '12px',
              color: 'var(--color-paper-mid)',
              lineHeight: '1.5',
              margin: 0,
              fontStyle: step.type === 'thought' ? 'italic' : 'normal',
            }}
          >
            {step.content}
          </p>
        )}
      </div>
    </div>
  );
};

// ─── One phase row: summary + expandable detail ──────────────────────────────
const PhaseRow = ({ phase, isLast }) => {
  const [manualOpen, setManualOpen] = useState(null);
  const status = phaseStatus(phase);
  const statusIcon = STATUS_ICON[status];
  // Auto-expand whichever phase is actively running (so progress is visible
  // as it streams in) — but once the user clicks a phase, their choice wins.
  const open = manualOpen ?? status === 'running';
  const lastStep = phase.steps[phase.steps.length - 1];
  const summary = lastStep?.content ?? lastStep?.label ?? '';

  const badgeBg = status === 'pending' ? 'var(--color-paper-surface)' : 'var(--color-brand-500)';
  const badgeIconColor = status === 'pending' ? 'var(--color-paper-mid)' : 'var(--color-paper-bg)';

  return (
    <div style={{ position: 'relative', paddingLeft: '26px' }}>
      {!isLast && (
        <div
          style={{
            position: 'absolute',
            left: '9px',
            top: '22px',
            bottom: '-2px',
            width: '1px',
            background: 'var(--color-hairline-border)',
          }}
        />
      )}
      <button
        onClick={() => phase.steps.length > 0 && setManualOpen((v) => !(v ?? status === 'running'))}
        disabled={phase.steps.length === 0}
        style={{
          width: '100%',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '10px',
          padding: '7px 0',
          background: 'none',
          border: 'none',
          cursor: phase.steps.length > 0 ? 'pointer' : 'default',
          textAlign: 'left',
        }}
      >
        <div
          style={{
            position: 'absolute',
            left: 0,
            width: '20px',
            height: '20px',
            borderRadius: '50%',
            background: badgeBg,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}
        >
          {status === 'running' ? (
            <motion.div
              animate={{ rotate: 360 }}
              transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
            >
              <Icon icon={phase.icon} style={{ fontSize: '11px', color: badgeIconColor }} />
            </motion.div>
          ) : (
            <Icon icon={phase.icon} style={{ fontSize: '11px', color: badgeIconColor }} />
          )}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: '13px',
              fontWeight: 500,
              color: status === 'pending' ? 'var(--color-paper-mid)' : 'var(--color-paper-dark)',
            }}
          >
            {phase.label}
          </div>
          {summary && (
            <div
              style={{
                fontSize: '12px',
                color: 'var(--color-paper-mid)',
                marginTop: '1px',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: open ? 'normal' : 'nowrap',
              }}
            >
              {summary}
            </div>
          )}
        </div>

        {statusIcon && (
          <Icon
            icon={statusIcon.icon}
            style={{ fontSize: '15px', color: statusIcon.color, flexShrink: 0, marginTop: '2px' }}
          />
        )}
        {phase.steps.length > 1 && (
          <Icon
            icon={open ? 'mdi:chevron-up' : 'mdi:chevron-down'}
            style={{
              fontSize: '14px',
              color: 'var(--color-paper-mid)',
              flexShrink: 0,
              marginTop: '3px',
              opacity: 0.6,
            }}
          />
        )}
      </button>

      <AnimatePresence initial={false}>
        {open && phase.steps.length > 1 && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.18 }}
            style={{ overflow: 'hidden' }}
          >
            <div
              style={{
                paddingLeft: '10px',
                marginTop: '2px',
                marginBottom: '4px',
                borderLeft: '2px solid var(--color-hairline-border)',
              }}
            >
              {phase.steps.slice(0, -1).map((step) => (
                <NestedStep key={step.id} step={step} />
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────
const ReActTrace = ({ steps }) => {
  const isRunning = steps.some((s) => s.status === 'running');
  const hasError = steps.some((s) => s.status === 'error');
  const runningStep = steps.find((s) => s.status === 'running');
  const phases = groupIntoPhases(steps);
  const runningPhase = phases.find((p) => phaseStatus(p) === 'running');
  const tally = !isRunning ? finalTally(steps) : null;

  // Mở khi đang chạy, thu lại khi xong
  const [open, setOpen] = useState(isRunning);
  const [prevIsRunning, setPrevIsRunning] = useState(isRunning);
  if (isRunning !== prevIsRunning) {
    setPrevIsRunning(isRunning);
    if (isRunning) setOpen(true);
  }

  const summaryLabel = isRunning
    ? `${runningPhase?.label ?? 'Processing'} — ${runningStep?.content?.slice(0, 44) ?? '…'}`
    : hasError
      ? 'error'
      : 'done';

  const headerIcon = isRunning ? 'mdi:loading' : hasError ? 'mdi:close-circle' : 'mdi:check-circle';
  const headerIconColor = isRunning
    ? 'var(--color-brand-500)'
    : hasError
      ? '#dc2626'
      : 'var(--color-paper-mid)';

  return (
    <div
      style={{
        border: '1px solid var(--color-hairline-border)',
        borderRadius: '12px',
        marginBottom: '12px',
        overflow: 'hidden',
      }}
    >
      {/* ── Collapse header ── */}
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%',
          background: 'var(--color-paper-surface)',
          border: 'none',
          padding: '9px 14px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {isRunning ? (
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}
          >
            <Icon icon={headerIcon} style={{ fontSize: '15px', color: headerIconColor }} />
          </motion.div>
        ) : (
          <Icon icon={headerIcon} style={{ fontSize: '15px', color: headerIconColor }} />
        )}

        <span
          style={{
            fontFamily: "'Newsreader', serif",
            fontSize: '13px',
            color: 'var(--color-paper-dark)',
            fontStyle: 'italic',
            flex: 1,
            opacity: 0.85,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
          }}
        >
          Reasoning trace · {summaryLabel}
        </span>

        <Icon
          icon={open ? 'mdi:chevron-up' : 'mdi:chevron-down'}
          style={{ fontSize: '16px', color: 'var(--color-paper-mid)', flexShrink: 0 }}
        />
      </button>

      {/* ── Phase list ── */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '8px 14px 4px' }}>
              {phases.map((phase, i) => (
                <PhaseRow key={phase.key} phase={phase} isLast={i === phases.length - 1} />
              ))}
            </div>

            {tally && (
              <div
                style={{
                  padding: '8px 14px 10px',
                  borderTop: '1px solid var(--color-hairline-border)',
                  fontFamily: "'Newsreader', serif",
                  fontSize: '12px',
                  color: 'var(--color-paper-mid)',
                }}
              >
                {tally}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ReActTrace;
