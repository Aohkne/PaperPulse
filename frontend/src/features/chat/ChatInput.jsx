import { useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useChatStore } from '@/shared/store/useChatStore';
import UsageExhaustedBanner from '@/features/billing/UsageExhaustedBanner';

const ChatInput = () => {
  const [value, setValue] = useState('');
  const sendMessage = useChatStore((s) => s.sendMessage);
  const status = useChatStore((s) => s.sessions.find((sess) => sess.id === s.activeSessionId)?.status ?? 'idle');
  const textareaRef = useRef(null);
  const isLoading = status === 'loading' || status === 'awaiting_plan';

  const handleChange = (e) => {
    setValue(e.target.value);
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = 'auto';
      ta.style.height = Math.min(ta.scrollHeight, 120) + 'px';
    }
  };

  const handleSend = () => {
    if (!value.trim() || isLoading) return;
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
    <div
      style={{
        borderTop: '1px solid var(--color-paper-light)',
        padding: '12px 28px 16px',
        backgroundColor: 'var(--color-paper-bg)',
        flexShrink: 0,
      }}
    >
      <div style={{ maxWidth: '680px', margin: '0 auto' }}>
        <UsageExhaustedBanner />

        {/* Input row */}
        <div
          style={{
            border: '1px solid var(--color-paper-light)',
            borderRadius: '4px',
            padding: '8px 12px',
            display: 'flex',
            alignItems: 'flex-end',
            gap: '8px',
            backgroundColor: 'var(--color-paper-bg)',
          }}
        >
          <Icon
            icon="mdi:paperclip"
            style={{ color: 'var(--color-paper-light)', width: 18, height: 18, flexShrink: 0, marginBottom: '2px' }}
          />

          <textarea
            ref={textareaRef}
            value={value}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            disabled={isLoading}
            rows={1}
            placeholder="Ask PaperPulse, attach PDFs, or paste a DOI…"
            style={{
              flex: 1,
              background: 'transparent',
              border: 'none',
              outline: 'none',
              resize: 'none',
              fontFamily: 'Georgia, serif',
              fontSize: '15px',
              color: 'var(--color-paper-dark)',
              lineHeight: '1.6',
              maxHeight: '120px',
              overflowY: 'auto',
            }}
          />

          <button
            onClick={handleSend}
            disabled={isLoading || !value.trim()}
            style={{
              backgroundColor: isLoading || !value.trim() ? 'var(--color-paper-surface)' : 'var(--color-paper-mid)',
              color: 'var(--color-paper-bg)',
              border: 'none',
              borderRadius: '2px',
              padding: '5px 14px',
              fontFamily: 'Georgia, serif',
              fontSize: '15px',
              cursor: isLoading || !value.trim() ? 'not-allowed' : 'pointer',
              flexShrink: 0,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
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
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <span
                    style={{ display: 'block', width: 13, height: 13, border: '2px solid var(--color-paper-bg)', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.9s linear infinite' }}
                  />
                  Thinking…
                </motion.span>
              ) : (
                <motion.span
                  key="send"
                  initial={{ opacity: 0, scale: 0.6 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.6 }}
                  transition={{ duration: 0.15 }}
                >
                  Send
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
            color: 'var(--color-paper-light)',
            marginTop: '6px',
            fontFamily: 'Georgia, serif',
          }}
        >
          PaperPulse only cites real papers — never fabricated sources.
        </p>
      </div>
    </div>
  );
};

export default ChatInput;
