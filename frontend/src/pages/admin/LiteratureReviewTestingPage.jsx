import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';
import useAdminTestStore from '@/shared/store/useAdminTestStore';

// Matches backend _NODE_STEP_NUM (api/research.py): 0 intent/plan · 1 search+dedup
// +relevance · 2 embed · 3 cluster · 4 write · 5 extract+verify · 6 route+KG · 7 export.
const STEP_LABELS = {
  0: 'Intent / Plan',
  1: 'Search + Filter',
  2: 'Embed',
  3: 'Cluster',
  4: 'Write',
  5: 'Verify',
  6: 'Route + KG',
  7: 'Export',
};

// â”€â”€ Step progress strip â€” derived from "step" events seen so far â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const StepStrip = ({ timeline }) => {
  const reached = useMemo(() => {
    const set = new Set();
    for (const e of timeline) {
      if (e.kind === 'step' && e.data?.stepNum !== undefined) set.add(Number(e.data.stepNum));
    }
    return set;
  }, [timeline]);

  const lastReached = reached.size ? Math.max(...reached) : -1;

  return (
    <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
      {Object.entries(STEP_LABELS).map(([n, label]) => {
        const num = Number(n);
        const isReached = reached.has(num);
        const isCurrent = num === lastReached;
        return (
          <div
            key={n}
            title={`Step ${n} â€” ${label}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 5,
              padding: '4px 9px',
              borderRadius: 20,
              fontSize: 11,
              fontWeight: 600,
              border: `1px solid ${isReached ? 'var(--color-admin-accent)' : 'var(--color-admin-border)'}`,
              background: isCurrent
                ? 'var(--color-admin-accent-bg)'
                : isReached
                  ? 'transparent'
                  : 'transparent',
              color: isReached ? 'var(--color-admin-accent-text)' : 'var(--color-admin-mid)',
              opacity: isReached ? 1 : 0.55,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: '50%',
                background: isReached ? 'var(--color-admin-accent)' : 'var(--color-admin-border)',
              }}
            />
            {n}. {label}
          </div>
        );
      })}
    </div>
  );
};

const Blink = () => (
  <span
    style={{
      display: 'inline-block',
      width: 2,
      height: 12,
      marginLeft: 2,
      background: 'currentColor',
      verticalAlign: 'text-bottom',
      animation: 'admin-kg-blink 0.9s step-end infinite',
    }}
  />
);

const RawDetails = ({ data }) => (
  <details style={{ marginTop: 6 }}>
    <summary style={{ fontSize: 11, color: 'var(--color-admin-mid)', cursor: 'pointer' }}>
      Raw event
    </summary>
    <pre
      style={{
        margin: '6px 0 0',
        fontSize: 11,
        lineHeight: 1.5,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
        background: 'var(--color-admin-bg)',
        border: '1px solid var(--color-admin-border)',
        borderRadius: 6,
        padding: 8,
        color: 'var(--color-admin-muted)',
      }}
    >
      {JSON.stringify(data, null, 2)}
    </pre>
  </details>
);

// â”€â”€ One timeline block, rendered differently per `kind` â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const TimelineEntry = ({ entry, isLastStreaming }) => {
  const time = new Date(entry.ts).toLocaleTimeString([], { hour12: false });

  const shell = (label, icon, color, bg, children) => (
    <div
      style={{
        display: 'flex',
        gap: 10,
        padding: '10px 12px',
        borderRadius: 8,
        background: bg,
        border: `1px solid ${color}33`,
      }}
    >
      <Icon icon={icon} style={{ fontSize: 15, color, flexShrink: 0, marginTop: 2 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          <span
            style={{
              fontSize: 11,
              fontWeight: 700,
              color,
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
            }}
          >
            {label}
          </span>
          <span style={{ fontSize: 10, color: 'var(--color-admin-mid)' }}>{time}</span>
        </div>
        {children}
      </div>
    </div>
  );

  switch (entry.kind) {
    case 'user_turn':
      return (
        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <div
            style={{
              maxWidth: '70%',
              padding: '8px 12px',
              borderRadius: 8,
              background: 'var(--color-admin-surface)',
              border: '1px solid var(--color-admin-border)',
              fontSize: 13,
              color: 'var(--color-admin-text)',
            }}
          >
            {entry.text}
          </div>
        </div>
      );

    case 'thinking_token':
      return shell(
        'Thinking â€” intent_router',
        'mdi:brain',
        'var(--color-admin-accent)',
        'var(--color-admin-accent-bg)',
        <p
          style={{
            margin: 0,
            fontSize: 13,
            fontStyle: 'italic',
            color: 'var(--color-admin-text)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {entry.text}
          {isLastStreaming && <Blink />}
        </p>
      );

    case 'reply_token':
      return shell(
        'Reply â€” reply_generator',
        'mdi:message-text-outline',
        '#4f86c6',
        'rgba(79,134,198,0.1)',
        <p
          style={{
            margin: 0,
            fontSize: 13,
            color: 'var(--color-admin-text)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {entry.text}
          {isLastStreaming && <Blink />}
        </p>
      );

    case 'step_token':
      return shell(
        `Step ${entry.stepNum} narrator`,
        'mdi:cog-outline',
        'var(--color-admin-mid)',
        'transparent',
        <p
          style={{
            margin: 0,
            fontSize: 12,
            fontStyle: 'italic',
            color: 'var(--color-admin-mid)',
            whiteSpace: 'pre-wrap',
          }}
        >
          {entry.text}
          {isLastStreaming && <Blink />}
        </p>
      );

    case 'step': {
      const d = entry.data;
      return shell(
        `Step ${d.stepNum} complete`,
        'mdi:check-circle-outline',
        '#16a34a',
        'rgba(22,163,74,0.08)',
        <>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--color-admin-text)' }}>{d.content}</p>
          {d.stat && (
            <p
              style={{
                margin: '2px 0 0',
                fontSize: 11,
                color: 'var(--color-admin-mid)',
                fontFamily: 'monospace',
              }}
            >
              {d.stat}
            </p>
          )}
          {d.refined_query && (
            <p style={{ margin: '4px 0 0', fontSize: 12, color: 'var(--color-admin-text)' }}>
              <strong>Refined query:</strong> {d.refined_query}
            </p>
          )}
          {d.plan_description && (
            <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--color-admin-muted)' }}>
              {d.plan_description}
            </p>
          )}
          <RawDetails data={d} />
        </>
      );
    }

    case 'greeting':
      return shell(
        'Greeting (intent=greeting)',
        'mdi:hand-wave-outline',
        'var(--color-admin-mid)',
        'transparent',
        <p style={{ margin: 0, fontSize: 13, color: 'var(--color-admin-text)' }}>
          {entry.data.content}
        </p>
      );

    case 'clarify':
      return shell(
        'Clarify (intent=clarify)',
        'mdi:help-circle-outline',
        '#d97706',
        'rgba(217,119,6,0.08)',
        <ul style={{ margin: 0, paddingLeft: 18, fontSize: 13, color: 'var(--color-admin-text)' }}>
          {(entry.data.questions || []).map((q, i) => (
            <li key={i}>{q}</li>
          ))}
        </ul>
      );

    case 'interrupt':
      return shell(
        'Interrupt â€” pipeline paused',
        'mdi:pause-circle-outline',
        '#d97706',
        'rgba(217,119,6,0.1)',
        <RawDetails data={entry.data} />
      );

    case 'done':
      return shell(
        'Pipeline complete',
        'mdi:flag-checkered',
        '#16a34a',
        'rgba(22,163,74,0.12)',
        <>
          <p
            style={{
              margin: 0,
              fontSize: 12,
              color: 'var(--color-admin-mid)',
              fontFamily: 'monospace',
            }}
          >
            literature_review.tex: {entry.data.content?.length ?? 0} chars Â· references.bib:{' '}
            {entry.data.bib?.length ?? 0} chars
          </p>
          <RawDetails data={entry.data} />
        </>
      );

    case 'error':
      return shell(
        'Error',
        'mdi:alert-circle-outline',
        '#dc2626',
        'rgba(220,38,38,0.08)',
        <p style={{ margin: 0, fontSize: 13, color: '#dc2626' }}>{entry.data.message}</p>
      );

    case 'resume_action':
      return shell(
        'Resumed',
        'mdi:play-circle-outline',
        'var(--color-admin-accent)',
        'var(--color-admin-accent-bg)',
        <p
          style={{
            margin: 0,
            fontSize: 12,
            color: 'var(--color-admin-text)',
            fontFamily: 'monospace',
          }}
        >
          resume_value = {JSON.stringify(entry.data.resumeValue)}
        </p>
      );

    default:
      return shell(
        entry.kind,
        'mdi:code-json',
        'var(--color-admin-mid)',
        'transparent',
        <RawDetails data={entry.data} />
      );
  }
};

// â”€â”€ Pending interrupt â€” approve or send a custom resume value â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const InterruptPanel = ({ data, onResume }) => {
  const [customJson, setCustomJson] = useState('true');
  const [customError, setCustomError] = useState(null);

  const submitCustom = () => {
    try {
      const parsed = JSON.parse(customJson);
      setCustomError(null);
      onResume(parsed);
    } catch {
      setCustomError('Invalid JSON');
    }
  };

  return (
    <div
      style={{
        padding: '12px 14px',
        borderRadius: 8,
        marginBottom: 12,
        background: 'rgba(217,119,6,0.1)',
        border: '1px solid rgba(217,119,6,0.35)',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Icon icon="mdi:pause-circle" style={{ fontSize: 16, color: '#d97706' }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: '#d97706' }}>
          Graph paused â€” waiting for resume
        </span>
      </div>
      <pre
        style={{
          margin: '0 0 10px',
          fontSize: 11,
          maxHeight: 160,
          overflowY: 'auto',
          background: 'var(--color-admin-bg)',
          border: '1px solid var(--color-admin-border)',
          borderRadius: 6,
          padding: 8,
          color: 'var(--color-admin-muted)',
          whiteSpace: 'pre-wrap',
        }}
      >
        {JSON.stringify(data, null, 2)}
      </pre>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
        <button
          onClick={() => onResume(true)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '7px 14px',
            fontSize: 13,
            fontWeight: 700,
            background: '#d97706',
            color: '#fff',
            border: 'none',
            borderRadius: 6,
            cursor: 'pointer',
          }}
        >
          <Icon icon="mdi:play" style={{ fontSize: 14 }} />
          Resume (approve)
        </button>
        <input
          value={customJson}
          onChange={(e) => setCustomJson(e.target.value)}
          placeholder='custom resume_value JSON, e.g. {"approved_outline":[...]}'
          style={{
            flex: 1,
            minWidth: 220,
            padding: '7px 10px',
            fontSize: 12,
            fontFamily: 'monospace',
            border: '1px solid var(--color-admin-border)',
            borderRadius: 6,
            background: 'var(--color-admin-input-bg)',
            color: 'var(--color-admin-text)',
          }}
        />
        <button
          onClick={submitCustom}
          style={{
            padding: '7px 12px',
            fontSize: 12,
            fontWeight: 600,
            border: '1px solid var(--color-admin-border)',
            borderRadius: 6,
            background: 'transparent',
            color: 'var(--color-admin-text)',
            cursor: 'pointer',
          }}
        >
          Resume with custom value
        </button>
      </div>
      {customError && (
        <p style={{ margin: '6px 0 0', fontSize: 11, color: '#dc2626' }}>{customError}</p>
      )}
    </div>
  );
};

const LiteratureReviewTestingPage = () => {
  const {
    running,
    threadId,
    timeline,
    error,
    pendingInterrupt,
    conversationHistory,
    submit,
    resume,
    reset,
  } = useAdminTestStore();

  const [input, setInput] = useState('');
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [timeline.length]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim() || running) return;
    submit(input.trim());
    setInput('');
  };

  const isFollowUp = conversationHistory.length > 0 && !running;
  const lastEntry = timeline[timeline.length - 1];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16, height: '100%' }}>
      {/* Header */}
      <div>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700, color: 'var(--color-admin-text)' }}>
          Literature Review â€” Pipeline Testing
        </h1>
        <p style={{ margin: '4px 0 0', fontSize: 13, color: 'var(--color-admin-mid)' }}>
          Runs the real <code>/api/research/stream</code> pipeline (research-agent_SPEC_2.0.md Step
          0â†’â‘©) and shows every SSE event â€” thinking tokens, reply tokens, step narration, and
          step completions â€” live.
        </p>
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8 }}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            isFollowUp
              ? 'Follow-up answer (continues the same thread)â€¦'
              : 'Type a query â€” e.g. "hello", "RAG", "RAG optimization techniques"'
          }
          disabled={running}
          style={{
            flex: 1,
            padding: '10px 14px',
            fontSize: 14,
            border: '1px solid var(--color-admin-border)',
            borderRadius: 8,
            background: 'var(--color-admin-input-bg)',
            color: 'var(--color-admin-text)',
          }}
        />
        <button
          type="submit"
          disabled={running || !input.trim()}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '10px 18px',
            fontSize: 13,
            fontWeight: 700,
            borderRadius: 8,
            border: 'none',
            background: running ? 'var(--color-admin-border)' : 'var(--color-admin-accent)',
            color: running ? 'var(--color-admin-mid)' : '#fff',
            cursor: running ? 'default' : 'pointer',
          }}
        >
          {running ? (
            <Icon icon="mdi:loading" className="animate-spin" style={{ fontSize: 15 }} />
          ) : (
            <Icon icon="mdi:play" style={{ fontSize: 15 }} />
          )}
          {isFollowUp ? 'Continue' : 'Run'}
        </button>
        <button
          type="button"
          onClick={reset}
          disabled={running}
          title="Clear and start a fresh test"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 6,
            padding: '10px 14px',
            fontSize: 13,
            fontWeight: 600,
            borderRadius: 8,
            border: '1px solid var(--color-admin-border)',
            background: 'transparent',
            color: 'var(--color-admin-text)',
            cursor: running ? 'default' : 'pointer',
          }}
        >
          <Icon icon="mdi:refresh" style={{ fontSize: 14 }} />
          Reset
        </button>
      </form>

      {/* Status row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
        <StepStrip timeline={timeline} />
        {threadId && (
          <span
            style={{
              fontSize: 11,
              fontFamily: 'monospace',
              color: 'var(--color-admin-mid)',
              padding: '3px 8px',
              borderRadius: 20,
              border: '1px solid var(--color-admin-border)',
            }}
          >
            thread: {threadId.slice(0, 12)}â€¦
          </span>
        )}
      </div>

      {error && (
        <div
          style={{
            padding: '10px 14px',
            fontSize: 13,
            color: '#dc2626',
            background: 'rgba(220,38,38,0.08)',
            border: '1px solid rgba(220,38,38,0.3)',
            borderRadius: 8,
          }}
        >
          {error}
        </div>
      )}

      {pendingInterrupt && <InterruptPanel data={pendingInterrupt.data} onResume={resume} />}

      {/* Timeline */}
      <div
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 8,
          padding: 4,
        }}
      >
        {timeline.length === 0 && !running && (
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              flex: 1,
              color: 'var(--color-admin-mid)',
              gap: 8,
            }}
          >
            <Icon icon="mdi:flask-empty-outline" style={{ fontSize: 28 }} />
            <p style={{ fontSize: 13, margin: 0 }}>
              No events yet â€” run a query to see the pipeline stream.
            </p>
          </div>
        )}
        <AnimatePresence initial={false}>
          {timeline.map((entry) => (
            <motion.div
              key={entry.id}
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.15 }}
            >
              <TimelineEntry
                entry={entry}
                isLastStreaming={running && entry.id === lastEntry?.id}
              />
            </motion.div>
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>

      <style>{`@keyframes admin-kg-blink { 0%,100%{opacity:1} 50%{opacity:0} }`}</style>
    </div>
  );
};

export default LiteratureReviewTestingPage;
