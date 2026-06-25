import { useEffect, useRef } from 'react';
import { AnimatePresence } from 'framer-motion';
import ChatMessage from './ChatMessage';

const MessageList = ({ messages, isLoading }) => {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length, isLoading]);

  if (!messages.length && !isLoading) {
    return (
      <div style={{
        flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center',
        color: 'var(--color-paper-light)', fontFamily: 'Georgia, serif', fontSize: '16px',
      }}>
        Start a new research session
      </div>
    );
  }

  return (
    <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }}>
      <div style={{ maxWidth: '680px', margin: '0 auto' }}>
        <AnimatePresence initial={false}>
          {messages.map((msg, i) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              animate={i === messages.length - 1 && msg.role === 'assistant'}
            />
          ))}
        </AnimatePresence>
        <div ref={bottomRef} />
      </div>
    </div>
  );
};

export default MessageList;
