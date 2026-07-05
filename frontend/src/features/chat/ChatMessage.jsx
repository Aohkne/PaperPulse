import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';
import ReActTrace from './ReActTrace';
import TypingIndicator from './TypingIndicator';
import ResearchPlanCard from '@/features/research/ResearchPlanCard';
import LatexPreview from '@/shared/components/LatexPreview';
import SaveReviewModal from '@/features/reviews/SaveReviewModal';
import { useChatStore } from '@/shared/store/useChatStore';

const formatTime = (ts) => {
  const d = ts instanceof Date ? ts : new Date(ts);
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

// Typewriter that progressively reveals LaTeX source then re-parses each frame
const CHUNK = 28; // chars revealed per tick
const TICK = 18; // ms between ticks (~55 fps)

const TypewriterLatex = ({ content }) => {
  const [displayed, setDisplayed] = useState('');
  const posRef = useRef(0);
  const timerRef = useRef(null);

  useEffect(() => {
    posRef.current = 0;
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDisplayed('');

    timerRef.current = setInterval(() => {
      posRef.current = Math.min(posRef.current + CHUNK, content.length);
      setDisplayed(content.slice(0, posRef.current));
      if (posRef.current >= content.length) {
        clearInterval(timerRef.current);
      }
    }, TICK);

    return () => clearInterval(timerRef.current);
  }, [content]);

  return <LatexPreview content={displayed} />;
};

const msgVariants = {
  initial: { opacity: 0, y: 10 },
  animate: { opacity: 1, y: 0, transition: { duration: 0.25, ease: [0.22, 1, 0.36, 1] } },
};

const ChatMessage = ({ message, animate = true }) => {
  const [saveOpen, setSaveOpen] = useState(false);

  // Get session title (original query) for the default review name
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const approvePlan = useChatStore((s) => s.approvePlan);
  const activeSession = sessions.find((s) => s.id === activeSessionId);
  const sessionTitle = activeSession?.title ?? '';
  const shouldRenderPendingPlan = Boolean(message.pendingPlan);
  const shouldRenderContent = Boolean(message.content) && !shouldRenderPendingPlan;

  if (message.role === 'user') {
    return (
      <motion.div
        variants={msgVariants}
        initial="initial"
        animate="animate"
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          marginBottom: '16px',
        }}
      >
        {/* Borderless, like Gemini's user bubble — fill only, no outline.
            Radius bumped from the old sharp 4px to 16px to match the
            rounded-card convention used on LoginPage and elsewhere. */}
        <div
          style={{
            backgroundColor: 'var(--color-paper-surface)',
            borderRadius: '16px',
            padding: '10px 14px',
            maxWidth: '480px',
            color: 'var(--color-paper-dark)',
            fontFamily: "'Newsreader', serif",
            fontSize: '16px',
            lineHeight: '1.6',
          }}
        >
          {message.content}
        </div>
        <span style={{ fontSize: '12px', color: 'var(--color-paper-mid)', marginTop: '4px' }}>
          {formatTime(message.timestamp)}
        </span>
      </motion.div>
    );
  }

  // Only show save button for actual LaTeX literature reviews, not conversational replies
  const canSave = !!(message.content && message.content.includes('\\documentclass'));

  return (
    <>
      <motion.div
        variants={msgVariants}
        initial="initial"
        animate="animate"
        style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', marginBottom: '20px' }}
      >
        <div
          style={{
            width: '28px',
            height: '28px',
            backgroundColor: 'var(--color-paper-mid)',
            borderRadius: '10px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            marginTop: '2px',
          }}
        >
          <span
            style={{
              fontFamily: 'var(--font-inknut)',
              color: 'var(--color-paper-bg)',
              fontSize: '14px',
              fontWeight: 600,
              lineHeight: 1,
            }}
          >
            P
          </span>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* ReAct reasoning trace (nếu có) */}
          {message.steps?.length > 0 && <ReActTrace steps={message.steps} />}

          {/* Step 0c — research plan awaiting user approval before any search calls */}
          {shouldRenderPendingPlan && (
            <ResearchPlanCard
              planDescription={message.pendingPlan.plan_description}
              subQueries={message.pendingPlan.sub_queries || []}
              sources={message.pendingPlan.sources || []}
              onApprove={(plan) => approvePlan(activeSessionId, plan)}
            />
          )}

          {/* Final answer — only render preview when content exists */}
          {shouldRenderContent ? (
            animate ? (
              <TypewriterLatex content={message.content} />
            ) : (
              <LatexPreview content={message.content} />
            )
          ) : (
            !message.steps?.length && !shouldRenderPendingPlan && <TypingIndicator inline />
          )}
          {/* Timestamp + Save sit in the same row, anchored to the END of the
              message content instead of floating absolute over its top edge.
              The old version pinned "Save" to the top-right corner of the
              whole message, which worked while a plain paragraph sat there —
              but collides with whatever now renders at the top (ReActTrace's
              own card header, ResearchPlanCard, etc.) since that top-right
              corner is contested space. Anchoring to the timestamp row is a
              landmark that's always the last thing in the message, so it
              can't collide with content above it no matter what that is. */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginTop: '4px',
            }}
          >
            <span style={{ fontSize: '12px', color: 'var(--color-paper-mid)' }}>
              {formatTime(message.timestamp)}
            </span>
            {canSave && (
              <button
                onClick={() => setSaveOpen(true)}
                title="Save to My Reviews"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '4px',
                  background: 'none',
                  border: 'none',
                  padding: '2px 0',
                  cursor: 'pointer',
                  color: 'var(--color-paper-mid)',
                  fontFamily: "'Newsreader', serif",
                  fontSize: '12px',
                  transition: 'color 0.15s',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--color-paper-dark)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--color-paper-mid)';
                }}
              >
                <Icon icon="mdi:bookmark-plus-outline" style={{ width: 13, height: 13 }} />
                Save
              </button>
            )}
          </div>
        </div>
      </motion.div>

      <SaveReviewModal
        isOpen={saveOpen}
        onClose={() => setSaveOpen(false)}
        markdownContent={message.content}
        defaultTitle={sessionTitle}
      />
    </>
  );
};

export default ChatMessage;
