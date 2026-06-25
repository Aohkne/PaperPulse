import { useState } from 'react';
import { Icon } from '@iconify/react';

/**
 * ClarifyCard — shown when intent_router returns intent="clarify".
 *
 * Props:
 *   questions       string[]   — clarifying questions from the LLM
 *   onSubmit        (answer: string) => void
 *   onNewTopic      () => void  — discard and start over
 */
const ClarifyCard = ({ questions = [], onSubmit, onNewTopic }) => {
  const [answer, setAnswer] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (answer.trim()) onSubmit(answer.trim());
  };

  return (
    <div style={{
      maxWidth: '600px',
      margin: '0 auto',
      padding: '24px',
      background: 'var(--color-paper-bg)',
      border: '1px solid var(--color-paper-surface)',
      borderRadius: '12px',
      boxShadow: '0 4px 24px rgba(0,0,0,0.06)',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '16px' }}>
        <div style={{
          width: '32px', height: '32px', borderRadius: '50%',
          background: 'rgba(245,158,11,0.12)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
        }}>
          <Icon icon="mdi:help-circle-outline" style={{ fontSize: '18px', color: '#d97706' }} />
        </div>
        <div>
          <p style={{ fontSize: '13px', fontWeight: 700, color: 'var(--color-paper-dark)', margin: 0 }}>
            Need a bit more context
          </p>
          <p style={{ fontSize: '11px', color: 'var(--color-paper-light)', margin: 0 }}>
            Please answer one or more of the questions below so I can build the right research plan.
          </p>
        </div>
      </div>

      {/* Questions */}
      <div style={{
        background: 'rgba(245,158,11,0.05)',
        border: '1px solid rgba(245,158,11,0.2)',
        borderRadius: '8px',
        padding: '12px 16px',
        marginBottom: '16px',
      }}>
        {questions.map((q, i) => (
          <div key={i} style={{
            display: 'flex',
            gap: '10px',
            fontSize: '13px',
            color: 'var(--color-paper-dark)',
            lineHeight: '1.6',
            paddingBottom: i < questions.length - 1 ? '8px' : 0,
            marginBottom: i < questions.length - 1 ? '8px' : 0,
            borderBottom: i < questions.length - 1 ? '1px solid rgba(245,158,11,0.15)' : 'none',
          }}>
            <span style={{
              fontSize: '11px',
              fontWeight: 700,
              color: '#d97706',
              minWidth: '18px',
              paddingTop: '2px',
            }}>
              {i + 1}.
            </span>
            {q}
          </div>
        ))}
      </div>

      {/* Answer input */}
      <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
        <textarea
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="Type your answer here…"
          rows={3}
          style={{
            width: '100%',
            padding: '10px 12px',
            fontSize: '13px',
            lineHeight: '1.6',
            border: '1px solid var(--color-paper-light)',
            borderRadius: '8px',
            background: 'var(--color-paper-bg)',
            color: 'var(--color-paper-dark)',
            outline: 'none',
            resize: 'vertical',
            boxSizing: 'border-box',
            fontFamily: 'inherit',
          }}
          onFocus={(e) => { e.target.style.borderColor = 'var(--color-brand-600)'; }}
          onBlur={(e) => { e.target.style.borderColor = 'var(--color-paper-light)'; }}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSubmit(e);
          }}
        />
        <div style={{ display: 'flex', gap: '8px', justifyContent: 'flex-end' }}>
          {onNewTopic && (
            <button
              type="button"
              onClick={onNewTopic}
              style={{
                padding: '7px 14px',
                fontSize: '12px',
                background: 'transparent',
                color: 'var(--color-paper-light)',
                border: '1px solid var(--color-paper-surface)',
                borderRadius: '6px',
                cursor: 'pointer',
              }}
            >
              Start over
            </button>
          )}
          <button
            type="submit"
            disabled={!answer.trim()}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '7px 16px',
              fontSize: '13px',
              fontWeight: 700,
              background: answer.trim() ? 'var(--color-brand-600)' : 'var(--color-paper-surface)',
              color: answer.trim() ? '#fff' : 'var(--color-paper-light)',
              border: 'none',
              borderRadius: '6px',
              cursor: answer.trim() ? 'pointer' : 'default',
              transition: 'background 0.15s',
            }}
          >
            <Icon icon="mdi:send-outline" style={{ fontSize: '14px' }} />
            Send  <span style={{ fontSize: '10px', opacity: 0.75, fontWeight: 400 }}>⌘↵</span>
          </button>
        </div>
      </form>
    </div>
  );
};

export default ClarifyCard;
