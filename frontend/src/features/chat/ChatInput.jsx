import { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useChatStore } from '@/shared/store/useChatStore';
import UsageExhaustedBanner from '@/features/billing/UsageExhaustedBanner';
import { useQuotaExhausted } from '@/shared/hooks/useQuotaExhausted';

const ChatInput = () => {
  const [value, setValue] = useState('');
  const sendMessage = useChatStore((s) => s.sendMessage);
  const status = useChatStore((s) => s.sessions.find((sess) => sess.id === s.activeSessionId)?.status ?? 'idle');
  const textareaRef = useRef(null);
  const quotaExhausted = useQuotaExhausted('lr');
  const isLoading = status === 'loading';
  const isAwaitingPlan = status === 'awaiting_plan';
  const inputDisabled = isLoading || isAwaitingPlan || quotaExhausted;

  const handleChange = (e) => {
    setValue(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  };

  const handleSend = () => {
    if (!value.trim() || inputDisabled) return;
    sendMessage(value);
    setValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    // No explicit background — same color as body's default paper-bg, so
    // letting it show through keeps the dot-grain texture consistent.
    // No borderTop either (was a solid olive line) — the input pill's own
    // shadow already separates it from the messages above, same clean
    // look as Gemini's input bar, which has no divider line at all.
    <div
      style={{
        padding: '12px 28px 16px',
        flexShrink: 0,
      }}
    >
      <div style={{ maxWidth: '780px', margin: '0 auto' }}>
        <UsageExhaustedBanner />

        {/* Same raised-surface + soft shadow treatment as the login card /
            welcome-screen input — paper-surface on top of the page's deeper
            paper-bg tone, rounded pill shape instead of the old 4px box. */}
        <div
          style={{
            border: '1px solid rgba(41, 17, 0, 0.08)',
            borderRadius: '18px',
            padding: '10px 10px 10px 18px',
            display: 'flex',
            alignItems: 'flex-end',
            gap: '10px',
            backgroundColor: 'var(--color-paper-surface)',
            boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 8px 24px rgba(41, 17, 0, 0.12)',
          }}
        >
          <textarea
            ref={textareaRef}
            className="themed-scroll"
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={inputDisabled}
            rows={1}
            placeholder={quotaExhausted ? 'Quota used up for this period…' : 'Ask PaperPulse…'}
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              resize: 'none',
              fontFamily: "'Newsreader', serif",
              fontSize: '17px',
              color: 'var(--color-paper-dark)',
              lineHeight: '1.6',
              maxHeight: '120px',
              overflowY: 'auto',
              padding: '6px 0',
            }}
          />

          <button
            onClick={handleSend}
            disabled={inputDisabled || !value.trim()}
            title={isLoading ? 'Thinking…' : isAwaitingPlan ? 'Awaiting approval…' : 'Send'}
            style={{
              // Circular, arrow-up icon, brand green when ready — same shape
              // and color as the welcome-screen send button (ChatPage.jsx),
              // so both send buttons in the app read as the same control.
              backgroundColor: inputDisabled || !value.trim() ? 'var(--color-paper-bg)' : 'var(--color-paper-mid)',
              color: 'var(--color-paper-surface)',
              border: 'none',
              borderRadius: '50%',
              width: 38,
              height: 38,
              cursor: inputDisabled || !value.trim() ? 'not-allowed' : 'pointer',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <AnimatePresence mode="wait" initial={false}>
              {isLoading ? (
                <motion.span
                  key="loading"
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.6 }}
                  transition={{ duration: 0.15 }}
                  style={{ display: 'flex' }}
                >
                  <span
                    style={{ display: 'block', width: 15, height: 15, border: '2px solid var(--color-paper-surface)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.9s linear infinite' }}
                  />
                </motion.span>
              ) : isAwaitingPlan ? (
                <motion.span
                  key="awaiting-plan"
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.6 }}
                  transition={{ duration: 0.15 }}
                  style={{ display: 'flex' }}
                >
                  <Icon icon="mdi:clock-outline" style={{ fontSize: '17px' }} />
                </motion.span>
              ) : (
                <motion.span
                  key="send"
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.6 }}
                  transition={{ duration: 0.15 }}
                  style={{ display: 'flex' }}
                >
                  <Icon icon="mdi:arrow-up" style={{ fontSize: '19px' }} />
                </motion.span>
              )}
            </AnimatePresence>
          </button>
        </div>

        {/* Disclaimer */}
        <p
          style={{
            textAlign: 'center',
            fontSize: '12px',
            color: 'var(--color-paper-mid)',
            marginTop: '6px',
            fontFamily: "'Newsreader', serif",
          }}
        >
          PaperPulse is AI and may make mistakes.
        </p>
      </div>
    </div>
  );
};

export default ChatInput;
