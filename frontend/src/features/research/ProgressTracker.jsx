import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';

const STATUS_ICON = {
  loading: { icon: 'mdi:loading', color: 'var(--color-brand-500)', spin: true },
  done: { icon: 'mdi:check-circle', color: 'var(--color-paper-mid)' },
  error: { icon: 'mdi:close-circle', color: '#dc2626' },
  interrupt: { icon: 'mdi:pause-circle', color: '#f59e0b' },
};

const ProgressTracker = ({ steps, stepLabels, stepTokens = {} }) => {
  // Only show steps that have been reached — idle steps stay hidden
  const activeEntries = Object.entries(stepLabels)
    .map(([n, label]) => ({ n, label, status: steps[Number(n)] ?? 'idle' }))
    .filter(({ status }) => status !== 'idle');

  if (activeEntries.length === 0) return null;

  return (
    <div style={{ padding: '12px 0' }}>
      <ol style={{ listStyle: 'none', margin: 0, padding: 0 }}>
        <AnimatePresence initial={false}>
          {activeEntries.map(({ n, label, status }, idx) => {
            const { icon, color, spin } = STATUS_ICON[status] ?? STATUS_ICON.done;
            const isLast = idx === activeEntries.length - 1;
            const streamedText = stepTokens[n] || '';
            const showStreamed = status === 'loading' && streamedText;

            return (
              <motion.li
                key={n}
                initial={{ opacity: 0, height: 0, x: -8 }}
                animate={{ opacity: 1, height: 'auto', x: 0 }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.25, ease: 'easeOut' }}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '10px',
                  overflow: 'hidden',
                }}
              >
                {/* Icon + connector line */}
                <div
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    flexShrink: 0,
                  }}
                >
                  <AnimatePresence mode="wait">
                    <motion.span
                      key={status}
                      initial={status === 'done' ? { scale: 0.4, opacity: 0 } : { opacity: 0 }}
                      animate={
                        status === 'done'
                          ? { scale: [0.4, 1.3, 1], opacity: 1 }
                          : { opacity: 1, scale: 1 }
                      }
                      transition={{ duration: 0.3, ease: 'easeOut' }}
                      style={{ display: 'flex' }}
                    >
                      <Icon
                        icon={icon}
                        className={spin ? 'animate-spin' : ''}
                        style={{ fontSize: '16px', color, flexShrink: 0 }}
                      />
                    </motion.span>
                  </AnimatePresence>
                  {!isLast && (
                    <motion.div
                      animate={{
                        background:
                          status === 'done'
                            ? 'var(--color-paper-mid)'
                            : 'var(--color-paper-surface)',
                      }}
                      transition={{ duration: 0.4 }}
                      style={{ width: '1px', flex: 1, minHeight: '14px', margin: '2px 0' }}
                    />
                  )}
                </div>

                {/* Label / streamed narrator text */}
                <div style={{ paddingBottom: isLast ? 0 : '14px', minWidth: 0, flex: 1 }}>
                  <AnimatePresence mode="wait">
                    {showStreamed ? (
                      <motion.span
                        key="stream"
                        initial={{ opacity: 0, y: 3 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        style={{
                          fontSize: '12px',
                          lineHeight: '16px',
                          color: 'var(--color-brand-600)',
                          fontStyle: 'italic',
                          display: 'block',
                        }}
                      >
                        {streamedText}
                        <span
                          style={{
                            display: 'inline-block',
                            width: '1px',
                            height: '11px',
                            background: 'var(--color-brand-500)',
                            marginLeft: '2px',
                            verticalAlign: 'text-bottom',
                            animation: 'blink 0.9s step-end infinite',
                          }}
                        />
                      </motion.span>
                    ) : (
                      <motion.span
                        key="label"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.15 }}
                        style={{
                          fontSize: '12px',
                          lineHeight: '16px',
                          color:
                            status === 'error'
                              ? '#dc2626'
                              : status === 'interrupt'
                                ? '#f59e0b'
                                : status === 'done'
                                  ? 'var(--color-paper-mid)'
                                  : 'var(--color-paper-dark)',
                          fontWeight: status === 'interrupt' ? 600 : 400,
                          display: 'block',
                        }}
                      >
                        {label}
                        {status === 'interrupt' && (
                          <span style={{ marginLeft: '4px', fontSize: '10px', color: '#f59e0b' }}>
                            ⏸ waiting
                          </span>
                        )}
                      </motion.span>
                    )}
                  </AnimatePresence>
                </div>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ol>
      <style>{`@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
};

export default ProgressTracker;
