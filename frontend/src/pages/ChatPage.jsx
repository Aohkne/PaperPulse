import { useEffect, useRef, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useChatStore } from '@/shared/store/useChatStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useUIStore } from '@/shared/store/useUIStore';
import { ROUTES } from '@/shared/constant/routes';
import MessageList from '@/features/chat/MessageList';
import ChatInput from '@/features/chat/ChatInput';
import DotOrbitBackground from '@/shared/components/DotOrbitBackground';
import UsageExhaustedBanner from '@/features/billing/UsageExhaustedBanner';
import { useQuotaExhausted } from '@/shared/hooks/useQuotaExhausted';
import { friendlyError } from '@/shared/utils/errorMessage';

const PILLARS = [
  { key: 'literature-review', icon: 'mdi:text-search', title: 'Literature Review', description: 'Search, screen, and summarise papers on any topic.' },
  { key: 'research-gaps', icon: 'mdi:lightbulb-on-outline', title: 'Research Gaps', description: 'Surface contradictions and understudied angles.' },
  { key: 'knowledge-graph', icon: 'mdi:graph-outline', title: 'Knowledge Graph', description: 'Visualise connections between papers and topics.' },
  { key: 'pdf-agent', icon: 'mdi:file-search-outline', title: 'PDF Agent', description: 'Upload a PDF to critique and verify its citations.' },
];

// "Literature Review" is where the user already is (this is the chat UI) —
// clicking it can't sensibly navigate anywhere, so instead it collapses the
// pillar grid down into 1-2 example prompts they can start from directly.
const LITERATURE_REVIEW_EXAMPLES = [
  'Summarize recent approaches to few-shot learning in computer vision (2022–2025).',
  'Compare evaluation methodologies across graph neural network papers on molecular property prediction.',
];

function getGreeting() {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return 'Good morning';
  if (h >= 12 && h < 18) return 'Good afternoon';
  if (h >= 18 && h < 22) return 'Good evening';
  return 'Good night';
}

// Mirrors MessageList's own container (padding/maxWidth) so the skeleton sits
// exactly where real messages will render — no extra card/heading "frame"
// around it, just the message-bubble placeholders fading in in place.
const SessionLoadingPanel = () => {
  const placeholderWidths = ['72%', '56%', '68%'];

  return (
    <div className="themed-scroll" style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
      <div style={{ maxWidth: '780px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '14px' }}>
        {placeholderWidths.map((width, index) => {
          const alignSelf = index === 1 ? 'flex-end' : 'flex-start';
          const bubbleTint = index === 1 ? 'var(--color-brand-100)' : 'var(--color-paper-surface)';
          return (
            <motion.div
              key={width}
              animate={{ opacity: [0.45, 0.8, 0.45] }}
              transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut', delay: index * 0.12 }}
              style={{ alignSelf, width, maxWidth: '100%' }}
            >
              <div
                style={{
                  height: index === 1 ? '78px' : index === 2 ? '64px' : '52px',
                  borderRadius: '18px',
                  border: '1px solid var(--color-paper-light)',
                  background: `linear-gradient(90deg, ${bubbleTint} 0%, var(--color-paper-bg) 48%, ${bubbleTint} 100%)`,
                  backgroundSize: '200% 100%',
                  boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.45)',
                }}
              />
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};

const WelcomeInput = () => {
  const location = useLocation();
  const [text, setText] = useState(location.state?.prefillText ?? '');
  const [showLRExamples, setShowLRExamples] = useState(false);
  const sendMessage = useChatStore((s) => s.sendMessage);
  const setGraphOpen = useUIStore((s) => s.setGraphOpen);
  const navigate = useNavigate();
  const textareaRef = useRef(null);
  const quotaExhausted = useQuotaExhausted('lr');

  // Consume the one-shot prefill (e.g. from the Applications launcher) so it
  // doesn't reappear if the user navigates back to this route later.
  useEffect(() => {
    if (location.state?.prefillText) {
      navigate(location.pathname, { replace: true, state: {} });
      textareaRef.current?.focus();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSend = () => {
    if (!text.trim() || quotaExhausted) return;
    sendMessage(text);
    setText('');
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handlePillarClick = (key) => {
    if (key === 'pdf-agent') { navigate(ROUTES.PDF_AGENT); return; }
    if (key === 'knowledge-graph') { setGraphOpen(true); return; }
    // Research Gaps is a real, separate page — take the user there directly
    // instead of dropping placeholder text into this chat's input.
    if (key === 'research-gaps') { navigate(ROUTES.RESEARCH); return; }
    // Literature Review *is* this chat UI, so "navigating" here would be a
    // no-op from the user's point of view. Collapse to example prompts
    // instead of prefilling a meaningless "Literature Review: " tag.
    if (key === 'literature-review') { setShowLRExamples(true); return; }
  };

  const handleExampleClick = (example) => {
    setText(example);
    setShowLRExamples(false);
    textareaRef.current?.focus();
  };

  return (
    <div>
      <UsageExhaustedBanner />

      {/* Same "raised surface on the page" treatment as the login card:
          paper-surface fill + soft 2-layer shadow, sitting on the page's
          slightly-deeper paper-bg tone. Rounder + bigger than the old 4px
          box — matches the reference Claude.ai input (big pill, soft shadow). */}
      <div style={{
        border: '1px solid rgba(41, 17, 0, 0.08)',
        borderRadius: '20px',
        background: 'var(--color-paper-surface)',
        boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 8px 24px rgba(41, 17, 0, 0.12)',
        padding: '18px 20px',
        display: 'flex',
        flexDirection: 'column',
        gap: '14px',
      }}>
        <textarea
          ref={textareaRef}
          rows={3}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={quotaExhausted}
          placeholder={quotaExhausted ? 'Quota used up for this period…' : 'Describe the topic, research question, and requirements...'}
          style={{
            width: '100%',
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontFamily: "'Newsreader', serif",
            fontSize: '17px',
            color: 'var(--color-paper-dark)',
            resize: 'none',
            lineHeight: '1.6',
            boxSizing: 'border-box',
          }}
        />

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={handleSend}
            disabled={!text.trim() || quotaExhausted}
            title="Send"
            style={{
              // Same green (paper-mid, which is brand-500) + same circular
              // shape as ChatInput's send button — one consistent "send"
              // control across the whole app instead of two different colors.
              background: text.trim() && !quotaExhausted ? 'var(--color-paper-mid)' : 'var(--color-paper-bg)',
              border: 'none',
              borderRadius: '50%',
              width: 38,
              height: 38,
              color: 'var(--color-paper-surface)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: text.trim() && !quotaExhausted ? 'pointer' : 'not-allowed',
            }}
          >
            <Icon icon="mdi:arrow-up" style={{ fontSize: '19px' }} />
          </button>
        </div>
      </div>

      {!text.trim() && (
        showLRExamples ? (
          <motion.div
            initial={{ opacity: 0, y: -6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.2, ease: [0.22, 1, 0.36, 1] }}
            style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}
          >
            <button
              onClick={() => setShowLRExamples(false)}
              style={{
                alignSelf: 'flex-start',
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                border: 'none',
                background: 'transparent',
                padding: '4px 2px',
                cursor: 'pointer',
                fontSize: '12.5px',
                color: 'var(--color-paper-mid)',
              }}
            >
              <Icon icon="mdi:chevron-left" style={{ fontSize: 16 }} />
              Back
            </button>
            {LITERATURE_REVIEW_EXAMPLES.map((example) => (
              <button
                key={example}
                onClick={() => handleExampleClick(example)}
                style={{
                  textAlign: 'left',
                  border: '1px solid rgba(41, 17, 0, 0.08)',
                  borderRadius: '14px',
                  background: 'var(--color-paper-surface)',
                  padding: '14px 16px',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  transition: 'box-shadow 0.15s ease, transform 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = '0 8px 20px rgba(41, 17, 0, 0.10)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.transform = 'none';
                }}
              >
                <Icon icon="mdi:text-search" style={{ fontSize: 18, color: 'var(--color-brand-500)', flexShrink: 0 }} />
                <span style={{ fontFamily: "'Newsreader', serif", fontSize: '14px', lineHeight: 1.5, color: 'var(--color-paper-dark)' }}>
                  {example}
                </span>
              </button>
            ))}
          </motion.div>
        ) : (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '12px', marginTop: '16px' }}>
            {PILLARS.map(({ key, icon, title, description }) => (
              <button
                key={key}
                onClick={() => handlePillarClick(key)}
                style={{
                  textAlign: 'left',
                  border: '1px solid rgba(41, 17, 0, 0.08)',
                  borderRadius: '14px',
                  background: 'var(--color-paper-surface)',
                  padding: '16px',
                  cursor: 'pointer',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                  transition: 'box-shadow 0.15s ease, transform 0.15s ease',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.boxShadow = '0 8px 20px rgba(41, 17, 0, 0.10)';
                  e.currentTarget.style.transform = 'translateY(-2px)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.boxShadow = 'none';
                  e.currentTarget.style.transform = 'none';
                }}
              >
                <Icon icon={icon} style={{ fontSize: 20, color: 'var(--color-brand-500)' }} />
                <span style={{ fontFamily: "'Newsreader', serif", fontSize: '14px', fontWeight: 600, color: 'var(--color-paper-dark)' }}>
                  {title}
                </span>
                <span style={{ fontSize: '12.5px', lineHeight: 1.5, color: 'var(--color-paper-mid)' }}>
                  {description}
                </span>
              </button>
            ))}
          </div>
        )
      )}
    </div>
  );
};

const ChatPage = () => {
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const loadChats = useChatStore((s) => s.loadChats);
  const chatsLoaded = useChatStore((s) => s.chatsLoaded);
  const chatsLoading = useChatStore((s) => s.chatsLoading);
  const chatsError = useChatStore((s) => s.chatsError);
  const user = useAuthStore((s) => s.user);
  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const activeMessages = activeSession?.messages ?? [];
  const isLoading = activeSession?.status === 'loading';
  const isHydratingPersistedSession =
    activeSession?.persisted &&
    activeSession?.status === 'loading' &&
    activeMessages.length === 0;
  const showWelcome = activeMessages.length === 0 && !isHydratingPersistedSession;

  useEffect(() => {
    if (!chatsLoaded && !chatsLoading) {
      loadChats();
    }
  }, [chatsLoaded, chatsLoading, loadChats]);

  if (showWelcome) {
    const displayName = user?.name || user?.email?.split('@')[0] || '';

    return (
      <div style={{ position: 'relative', flex: 1, overflow: 'hidden' }}>
        {/* Same brand-colored animated dot layer as the landing hero — only
            on the empty/welcome state, not once real messages are on screen
            (would be too noisy behind dense chat content). */}
        <div style={{ position: 'absolute', inset: 0, zIndex: 0 }}>
          <DotOrbitBackground
            mode="orbit"
            tracking="global"
            interaction="repel"
            density={0.8}
            speed={0.4}
            dotSize={1.6}
            linkDistance={120}
            opacity={0.5}
            alpha={1}
            interactionRadius={140}
            interactionStrength={12}
            cursorEase={35}
            background="rgba(0, 0, 0, 0)"
            dotColor="--color-brand-500"
            lineColor="--color-brand-100"
          />
        </div>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
          style={{
            position: 'relative', zIndex: 1,
            flex: 1, height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', padding: '0 24px', gap: '24px',
          }}
        >
          {chatsError && (
            <div style={{ width: '100%', maxWidth: '780px', padding: '10px 12px', border: '1px solid #d8b4b4', borderRadius: '4px', color: '#8c3b3b', fontSize: '13px', lineHeight: 1.4 }}>
              {friendlyError(chatsError, "Couldn't load your chats.")}
            </div>
          )}

          <div style={{ textAlign: 'center' }}>
            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
              style={{ fontFamily: 'var(--font-inknut)', fontSize: '34px', fontWeight: '600', color: 'var(--color-paper-dark)', margin: '0 0 10px' }}
            >
              {getGreeting()}{displayName ? `, ${displayName}` : ''}.
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4, delay: 0.16, ease: [0.22, 1, 0.36, 1] }}
              style={{ fontFamily: "'Newsreader', serif", fontSize: '17px', color: 'var(--color-paper-mid)', margin: 0 }}
            >
              What would you like to research today?
            </motion.p>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
            style={{ width: '100%', maxWidth: '780px' }}
          >
            <WelcomeInput />
          </motion.div>
        </motion.div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {isHydratingPersistedSession ? (
        <SessionLoadingPanel />
      ) : (
        <MessageList messages={activeMessages} isLoading={isLoading} />
      )}
      <ChatInput />
    </div>
  );
};

export default ChatPage;

