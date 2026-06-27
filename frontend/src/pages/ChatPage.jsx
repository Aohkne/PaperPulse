import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useChatStore } from '@/shared/store/useChatStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useUIStore } from '@/shared/store/useUIStore';
import { ROUTES } from '@/shared/constant/routes';
import MessageList from '@/features/chat/MessageList';
import ChatInput from '@/features/chat/ChatInput';
import UsageExhaustedBanner from '@/features/billing/UsageExhaustedBanner';
import { useQuotaExhausted } from '@/shared/hooks/useQuotaExhausted';

const PILLARS = [
  { key: 'literature-review', icon: 'mdi:text-search', title: 'Literature Review', description: 'Search, screen, and summarise papers on any topic.' },
  { key: 'research-gaps', icon: 'mdi:lightbulb-on-outline', title: 'Research Gaps', description: 'Surface contradictions and understudied angles.' },
  { key: 'knowledge-graph', icon: 'mdi:graph-outline', title: 'Knowledge Graph', description: 'Visualise connections between papers and topics.' },
  { key: 'pdf-agent', icon: 'mdi:file-search-outline', title: 'PDF Agent', description: 'Upload a PDF to critique and verify its citations.' },
];

function getGreeting() {
  const h = new Date().getHours();
  if (h >= 5 && h < 12) return 'Good morning';
  if (h >= 12 && h < 18) return 'Good afternoon';
  if (h >= 18 && h < 22) return 'Good evening';
  return 'Good night';
}

const SessionLoadingPanel = () => {
  const placeholderWidths = ['72%', '56%', '68%'];

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
      style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        padding: '32px 24px 20px',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '760px',
          margin: '0 auto',
          border: '1px solid var(--color-paper-light)',
          borderRadius: '8px',
          background: 'linear-gradient(180deg, rgba(255,255,255,0.72) 0%, rgba(244, 238, 228, 0.88) 100%)',
          boxShadow: '0 18px 40px rgba(46, 39, 31, 0.08)',
          padding: '20px 20px 18px',
        }}
      >
        <div style={{ marginBottom: '18px' }}>
          <div
            style={{
              fontFamily: 'var(--font-inknut)',
              fontSize: '24px',
              fontWeight: 600,
              color: 'var(--color-paper-dark)',
              marginBottom: '6px',
            }}
          >
            Opening session...
          </div>
          <div style={{ fontFamily: 'Georgia, serif', fontSize: '14px', color: 'var(--color-paper-mid)', marginBottom: '4px' }}>
            Loading previous messages and session details.
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-paper-light)' }}>
            This should only take a moment.
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          {placeholderWidths.map((width, index) => {
            const alignSelf = index === 1 ? 'flex-end' : 'flex-start';
            const bubbleTint = index === 1 ? 'rgba(196, 166, 122, 0.16)' : 'rgba(92, 76, 54, 0.08)';
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
                    border: '1px solid rgba(92, 76, 54, 0.08)',
                    background: `linear-gradient(90deg, ${bubbleTint} 0%, rgba(255,255,255,0.76) 48%, ${bubbleTint} 100%)`,
                    backgroundSize: '200% 100%',
                    boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.45)',
                  }}
                />
              </motion.div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
};

const WelcomeInput = () => {
  const [text, setText] = useState('');
  const sendMessage = useChatStore((s) => s.sendMessage);
  const setGraphOpen = useUIStore((s) => s.setGraphOpen);
  const navigate = useNavigate();
  const textareaRef = useRef(null);
  const quotaExhausted = useQuotaExhausted('lr');

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
    const pillar = PILLARS.find((p) => p.key === key);
    setText(`${pillar.title}: `);
    textareaRef.current?.focus();
  };

  return (
    <div>
      <UsageExhaustedBanner />

      <div style={{
        border: '1px solid var(--color-paper-light)',
        borderRadius: '4px',
        background: 'var(--color-paper-bg)',
        padding: '12px 14px',
        display: 'flex',
        flexDirection: 'column',
        gap: '12px',
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
            fontFamily: "'Noto Serif', serif",
            fontSize: '14px',
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
            style={{
              background: 'var(--color-paper-dark)',
              border: 'none',
              borderRadius: '4px',
              padding: '8px 16px',
              minHeight: 36,
              color: 'var(--color-paper-bg)',
              fontFamily: "'Noto Serif', serif",
              fontSize: '13px',
              cursor: text.trim() && !quotaExhausted ? 'pointer' : 'not-allowed',
            }}
          >
            {'->'}
          </button>
        </div>
      </div>

      {!text.trim() && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '10px', marginTop: '14px' }}>
          {PILLARS.map(({ key, icon, title, description }) => (
            <button
              key={key}
              onClick={() => handlePillarClick(key)}
              style={{
                textAlign: 'left',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '6px',
                background: 'var(--color-paper-bg)',
                padding: '12px',
                cursor: 'pointer',
                display: 'flex',
                flexDirection: 'column',
                gap: '6px',
              }}
            >
              <Icon icon={icon} style={{ fontSize: 18, color: 'var(--color-paper-mid)' }} />
              <span style={{ fontFamily: "'Noto Serif', serif", fontSize: '13px', fontWeight: 600, color: 'var(--color-paper-dark)' }}>
                {title}
              </span>
              <span style={{ fontSize: '11px', lineHeight: 1.4, color: 'var(--color-paper-light)' }}>
                {description}
              </span>
            </button>
          ))}
        </div>
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
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 24px', gap: '20px' }}
      >
        {chatsError && (
          <div style={{ width: '100%', maxWidth: '640px', padding: '10px 12px', border: '1px solid #d8b4b4', borderRadius: '4px', color: '#8c3b3b', fontSize: '13px', lineHeight: 1.4 }}>
            {chatsError}
          </div>
        )}

        <div style={{ textAlign: 'center' }}>
          <motion.h1
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
            style={{ fontFamily: 'var(--font-inknut)', fontSize: '28px', fontWeight: '600', color: 'var(--color-paper-dark)', margin: '0 0 8px' }}
          >
            {getGreeting()}{displayName ? `, ${displayName}` : ''}.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: 0.16, ease: [0.22, 1, 0.36, 1] }}
            style={{ fontFamily: "'Noto Serif', serif", fontSize: '15px', color: 'var(--color-paper-mid)', margin: 0 }}
          >
            What would you like to research today?
          </motion.p>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
          style={{ width: '100%', maxWidth: '640px' }}
        >
          <WelcomeInput />
        </motion.div>
      </motion.div>
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

