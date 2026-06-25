import { useRef, useState } from 'react';
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

const PILLARS = [
  { key: 'literature-review', icon: 'mdi:text-search', title: 'Literature Review', description: 'Search, screen, and summarise papers on any topic.' },
  { key: 'research-gaps', icon: 'mdi:lightbulb-on-outline', title: 'Research Gaps', description: 'Surface contradictions and understudied angles.' },
  { key: 'knowledge-graph', icon: 'mdi:graph-outline', title: 'Knowledge Graph', description: 'Visualise connections between papers and topics.' },
  { key: 'pdf-agent', icon: 'mdi:file-search-outline', title: 'PDF Agent', description: 'Upload a PDF to critique and verify its citations.' },
];

function getGreeting() {
  const h = new Date().getHours();
  if (h >= 5  && h < 12) return 'Good morning';
  if (h >= 12 && h < 18) return 'Good afternoon';
  if (h >= 18 && h < 22) return 'Good evening';
  return 'Good night';
}

const WelcomeInput = () => {
  const [text, setText] = useState('');
  const sendMessage = useChatStore((s) => s.sendMessage);
  const setGraphOpen = useUIStore((s) => s.setGraphOpen);
  const navigate = useNavigate();
  const textareaRef = useRef(null);

  const handleSend = () => {
    if (!text.trim()) return;
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
          placeholder="Describe the topic, research question, and requirements..."
          style={{
            width: '100%',
            border: 'none',
            outline: 'none',
            background: 'transparent',
            fontFamily: 'Georgia, serif',
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
            disabled={!text.trim()}
            style={{
              background: 'var(--color-paper-dark)',
              border: 'none',
              borderRadius: '4px',
              padding: '6px 14px',
              color: 'var(--color-paper-bg)',
              fontFamily: 'Georgia, serif',
              fontSize: '13px',
              cursor: text.trim() ? 'pointer' : 'not-allowed',
            }}
          >
            →
          </button>
        </div>
      </div>

      {!text.trim() && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '10px', marginTop: '14px' }}>
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
              <span style={{ fontFamily: 'Georgia, serif', fontSize: '13px', fontWeight: 600, color: 'var(--color-paper-dark)' }}>
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
  const user = useAuthStore((s) => s.user);
  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const activeMessages = activeSession?.messages ?? [];
  const isLoading = activeSession?.status === 'loading';

  if (activeMessages.length === 0) {
    const displayName = user?.name || user?.email?.split('@')[0] || '';

    return (
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '0 24px', gap: '32px' }}
      >
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
            style={{ fontFamily: 'Georgia, serif', fontSize: '15px', color: 'var(--color-paper-mid)', margin: 0 }}
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
      <MessageList messages={activeMessages} isLoading={isLoading} />
      <ChatInput />
    </div>
  );
};

export default ChatPage;
