import { useState } from 'react';
import { Icon } from '@iconify/react';

import useGapStore from './useGapStore';
import UsageExhaustedBanner from '@/features/billing/UsageExhaustedBanner';
import { useQuotaExhausted } from '@/shared/hooks/useQuotaExhausted';

/**
 * ColdStartInput - Topic input + submit button for cold-start gap detection.
 *
 * Renders a textarea + "Find Gaps" button.
 * Button disabled when topic is empty or pipeline is loading.
 * Calls useGapStore.findGapsFromTopic(topic) on submit.
 */
const ColdStartInput = ({ onSubmit }) => {
  const [topic, setTopic] = useState('');
  const { findGapsFromTopic, gapLoading, gapRejected } = useGapStore();
  const handleSubmitAction = onSubmit || findGapsFromTopic;
  const quotaExhausted = useQuotaExhausted('gap');

  const trimmed = topic.trim();
  const disabled = !trimmed || trimmed.length < 3 || gapLoading || quotaExhausted;

  const handleSubmit = () => {
    if (!disabled) handleSubmitAction(trimmed);
  };

  const handleKeyDown = (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') handleSubmit();
  };

  return (
    <section style={{
      border: '1px solid var(--color-paper-surface)',
      borderRadius: '14px',
      background: 'var(--color-paper-bg)',
      boxShadow: '0 10px 28px rgba(41, 17, 0, 0.05)',
      overflow: 'hidden',
    }}>
      <div style={{ padding: '18px 20px 14px', borderBottom: '1px solid var(--color-paper-surface)' }}>
        <UsageExhaustedBanner feature="gap" />
        <div style={{ fontFamily: 'var(--font-inknut)', fontSize: '12px', fontWeight: 700, letterSpacing: '0.04em', textTransform: 'uppercase', color: 'var(--color-paper-light)', marginBottom: '6px' }}>
          Topic
        </div>
        <div style={{ fontFamily: "'Noto Serif', serif", fontSize: '14px', color: 'var(--color-paper-dark)', marginBottom: '10px' }}>
          Describe the research area you want to analyze.
        </div>

        <textarea
          id="gap-topic-input"
          value={topic}
          onChange={(e) => { setTopic(e.target.value); if (gapRejected) useGapStore.setState({ gapRejected: null }); }}
          onKeyDown={handleKeyDown}
          disabled={gapLoading || quotaExhausted}
          placeholder={quotaExhausted ? 'Quota used up for this period…' : 'Enter research topic... (e.g. transformer long-context NLP)'}
          rows={4}
          style={{
            width: '100%',
            minHeight: '110px',
            padding: '12px 14px',
            fontSize: '14px',
            lineHeight: '1.65',
            border: '1px solid var(--color-paper-surface)',
            borderRadius: '10px',
            resize: 'vertical',
            fontFamily: "'Noto Serif', serif",
            color: 'var(--color-paper-dark)',
            background: gapLoading || quotaExhausted ? 'var(--color-paper-surface)' : 'var(--color-paper-bg)',
            outline: 'none',
            boxSizing: 'border-box',
            transition: 'border-color 0.15s, box-shadow 0.15s',
          }}
          onFocus={(e) => { e.target.style.borderColor = 'var(--color-paper-light)'; e.target.style.boxShadow = '0 0 0 3px rgba(181, 162, 63, 0.16)'; }}
          onBlur={(e) => { e.target.style.borderColor = 'var(--color-paper-surface)'; e.target.style.boxShadow = 'none'; }}
        />

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '12px', marginTop: '12px', flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
            <p style={{ margin: 0, fontFamily: "'Noto Serif', serif", fontSize: '12px', color: 'var(--color-paper-light)' }}>
            Ctrl+Enter to submit
            </p>
          </div>

          <button
            id="gap-find-btn"
            onClick={handleSubmit}
            disabled={disabled}
            title={quotaExhausted ? 'Quota used up for this period' : trimmed.length < 3 ? 'Enter at least 3 characters' : 'Find research gaps'}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '6px',
              padding: '9px 16px',
              fontFamily: "'Noto Serif', serif",
              fontSize: '13px',
              fontWeight: 600,
              background: disabled ? 'var(--color-paper-surface)' : 'var(--color-paper-mid)',
              color: disabled ? 'var(--color-paper-light)' : 'var(--color-paper-bg)',
              border: disabled ? '1px solid var(--color-paper-surface)' : '1px solid var(--color-paper-mid)',
              borderRadius: '10px',
              cursor: disabled ? 'default' : 'pointer',
              transition: 'background 0.15s, border-color 0.15s, transform 0.15s, box-shadow 0.15s',
              boxShadow: disabled ? 'none' : '0 8px 18px rgba(90, 107, 51, 0.18)',
            }}
            onMouseEnter={(e) => {
              if (!disabled) {
                e.currentTarget.style.background = 'var(--color-paper-dark)';
                e.currentTarget.style.borderColor = 'var(--color-paper-dark)';
              }
            }}
            onMouseLeave={(e) => {
              if (!disabled) {
                e.currentTarget.style.background = 'var(--color-paper-mid)';
                e.currentTarget.style.borderColor = 'var(--color-paper-mid)';
              }
            }}
          >
            {gapLoading
              ? <><Icon icon="mdi:loading" style={{ fontSize: '13px', color: 'var(--color-paper-bg)', animation: 'spin 1s linear infinite' }} /> Analyzing...</>
              : <><Icon icon="mdi:lightbulb-search-outline" style={{ fontSize: '13px' }} /> Find Gaps</>
            }
          </button>
        </div>

        {gapRejected && (
          <div style={{
            marginTop: '12px',
            padding: '10px 14px',
            borderRadius: '8px',
            background: gapRejected.reason === 'injection'
              ? 'rgba(139, 74, 47, 0.08)'
              : 'rgba(181, 162, 63, 0.10)',
            border: `1px solid ${gapRejected.reason === 'injection' ? 'rgba(139, 74, 47, 0.25)' : 'rgba(181, 162, 63, 0.30)'}`,
            display: 'flex',
            alignItems: 'flex-start',
            gap: '8px',
          }}>
            <Icon
              icon={gapRejected.reason === 'injection' ? 'mdi:shield-alert-outline' : 'mdi:information-outline'}
              style={{ fontSize: '16px', color: gapRejected.reason === 'injection' ? '#8B4A2F' : 'var(--color-paper-mid)', flexShrink: 0, marginTop: '1px' }}
            />
            <p style={{ margin: 0, fontFamily: "'Noto Serif', serif", fontSize: '13px', lineHeight: '1.6', color: 'var(--color-paper-dark)' }}>
              {gapRejected.message}
            </p>
          </div>
        )}
      </div>
    </section>
  );
};

export default ColdStartInput;