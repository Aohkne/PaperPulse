import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';

const STEP_COLOR = {
  '0':  '#94a3b8',
  '1':  '#4f86c6',
  '2':  '#8040e8',
  '3':  '#9b5de5',
  '4':  '#059669',
  '5':  '#d97706',
  '6':  '#7c3aed',
  '7':  '#be185d',
  '8':  '#dc2626',
  '9':  '#b45309',
  '10': '#0d9488',
  '11': '#5A6B33',
};

const TYPE_CFG = {
  thought: {
    icon: 'mdi:brain',
    label: 'Thought',
    color: '#B5A23F',
  },
  action: {
    icon: 'mdi:code-tags',
    label: 'Action',
    color: '#8040e8',
  },
  observation: {
    icon: 'mdi:eye-check-outline',
    label: 'Observation',
    color: '#5A6B33',
  },
};

const ReActStep = ({ step, index }) => {
  const cfg = TYPE_CFG[step.type] ?? TYPE_CFG.thought;
  const stepColor = STEP_COLOR[step.stepNum] ?? 'var(--color-paper-light)';
  const isRunning = step.status === 'running';

  return (
    <motion.div
      initial={{ opacity: 0, x: -6 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.2, delay: index * 0.015, ease: [0.22, 1, 0.36, 1] }}
      style={{
        display: 'flex',
        gap: '8px',
        padding: '6px 0',
        borderBottom: '1px solid var(--color-paper-surface)',
        alignItems: 'flex-start',
      }}
    >
      {/* Step badge ①②... */}
      <span style={{
        flexShrink: 0,
        fontSize: '11px',
        fontWeight: 700,
        color: stepColor,
        fontFamily: 'monospace',
        minWidth: '30px',
        paddingTop: '2px',
        textAlign: 'center',
        letterSpacing: '-0.02em',
      }}>
        {step.stepNum}
      </span>

      {/* Type icon */}
      <div style={{ flexShrink: 0, paddingTop: '3px' }}>
        {isRunning ? (
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}>
            <Icon icon="mdi:loading" style={{ fontSize: '13px', color: cfg.color }} />
          </motion.div>
        ) : (
          <Icon icon={cfg.icon} style={{ fontSize: '13px', color: cfg.color, opacity: 0.75 }} />
        )}
      </div>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <span style={{
          display: 'block',
          fontSize: '10px',
          fontWeight: 700,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: cfg.color,
          opacity: 0.65,
          marginBottom: '2px',
        }}>
          {cfg.label}
        </span>

        {step.type === 'action' ? (
          <code style={{
            fontFamily: '"Fira Code", "Courier New", monospace',
            fontSize: '12px',
            lineHeight: '1.55',
            display: 'block',
            wordBreak: 'break-word',
            color: 'var(--color-paper-dark)',
          }}>
            <span style={{ color: '#8040e8', fontWeight: 600 }}>{step.label}</span>
            <span style={{ color: 'var(--color-paper-light)', fontWeight: 400 }}>(</span>
            <span style={{ color: 'var(--color-paper-mid)', fontStyle: 'italic' }}>{step.args}</span>
            <span style={{ color: 'var(--color-paper-light)', fontWeight: 400 }}>)</span>
          </code>
        ) : (
          <p style={{
            fontFamily: "'Noto Serif', serif",
            fontSize: '13px',
            color: 'var(--color-paper-dark)',
            lineHeight: '1.55',
            margin: 0,
            fontStyle: step.type === 'thought' ? 'italic' : 'normal',
            opacity: step.type === 'observation' ? 0.85 : 1,
          }}>
            {step.content}
          </p>
        )}
      </div>

      {/* Status indicator */}
      <div style={{ flexShrink: 0, paddingTop: '4px' }}>
        {step.status === 'done' && (
          <Icon icon="mdi:check" style={{ fontSize: '11px', color: '#5A6B33', opacity: 0.6 }} />
        )}
        {step.status === 'error' && (
          <Icon icon="mdi:close" style={{ fontSize: '11px', color: '#dc2626' }} />
        )}
      </div>
    </motion.div>
  );
};

// ─── Stats bar: coverage numbers hiển thị sau khi xong ───────────────────────
const TraceStats = ({ steps }) => {
  const obs = steps.filter(s => s.type === 'observation' && s.stat);
  if (!obs.length) return null;
  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      gap: '6px',
      padding: '6px 12px 8px',
      borderTop: '1px solid var(--color-paper-surface)',
    }}>
      {obs.map((s) => (
        <span key={s.id} style={{
          fontSize: '11px',
          fontFamily: "'Noto Serif', serif",
          color: 'var(--color-paper-mid)',
          background: 'var(--color-paper-surface)',
          borderRadius: '3px',
          padding: '2px 7px',
        }}>
          {s.stat}
        </span>
      ))}
    </div>
  );
};

// ─── Main component ───────────────────────────────────────────────────────────
const ReActTrace = ({ steps }) => {
  const isRunning = steps.some(s => s.status === 'running');
  const doneCount = steps.filter(s => s.status === 'done').length;
  const hasError  = steps.some(s => s.status === 'error');
  const runningStep = steps.find(s => s.status === 'running');

  // Mở khi đang chạy, thu lại khi xong
  const [open, setOpen] = useState(isRunning);
  const [prevIsRunning, setPrevIsRunning] = useState(isRunning);
  if (isRunning !== prevIsRunning) {
    setPrevIsRunning(isRunning);
    if (isRunning) setOpen(true);
  }

  const summaryLabel = isRunning
    ? `${runningStep?.stepNum ?? '…'} — ${runningStep?.label ?? runningStep?.content?.slice(0, 40) ?? 'processing'}…`
    : hasError
      ? `${doneCount}/${steps.length} steps · Error`
      : `${steps.length} steps · Complete`;

  const headerIcon = isRunning
    ? 'mdi:loading'
    : hasError
      ? 'mdi:close-circle'
      : 'mdi:check-circle';

  const headerIconColor = isRunning
    ? 'var(--color-brand-500)'
    : hasError
      ? '#dc2626'
      : 'var(--color-paper-mid)';

  return (
    <div style={{
      border: '1px solid var(--color-paper-surface)',
      borderRadius: '4px',
      marginBottom: '12px',
      overflow: 'hidden',
    }}>
      {/* ── Collapse header ── */}
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%',
          background: 'var(--color-paper-surface)',
          border: 'none',
          padding: '7px 12px',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          cursor: 'pointer',
          textAlign: 'left',
        }}
      >
        {isRunning ? (
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 1.1, repeat: Infinity, ease: 'linear' }}>
            <Icon icon={headerIcon} style={{ fontSize: '14px', color: headerIconColor }} />
          </motion.div>
        ) : (
          <Icon icon={headerIcon} style={{ fontSize: '14px', color: headerIconColor }} />
        )}

        <span style={{
          fontFamily: "'Noto Serif', serif",
          fontSize: '12px',
          color: 'var(--color-paper-dark)',
          fontStyle: 'italic',
          flex: 1,
          opacity: 0.8,
        }}>
          Reasoning trace — {summaryLabel}
        </span>

        <Icon
          icon={open ? 'mdi:chevron-up' : 'mdi:chevron-down'}
          style={{ fontSize: '15px', color: 'var(--color-paper-light)', flexShrink: 0 }}
        />
      </button>

      {/* ── Steps list ── */}
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            style={{ overflow: 'hidden' }}
          >
            <div style={{ padding: '2px 12px 4px' }}>
              {steps.map((step, i) => (
                <ReActStep key={step.id} step={step} index={i} />
              ))}
            </div>
            <TraceStats steps={steps} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ReActTrace;
