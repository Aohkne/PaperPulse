import { useState, useRef, useCallback, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { Icon } from '@iconify/react';
import Sidebar from '@/features/chat/Sidebar';
import NotificationsButton from '@/features/chat/NotificationsButton';
import KnowledgeGraphDrawer from '@/features/graph/KnowledgeGraphDrawer';
import { useChatStore } from '@/shared/store/useChatStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useUIStore } from '@/shared/store/useUIStore';
import { useIsMobile } from '@/shared/hooks/useIsMobile';
import { ROUTES } from '@/shared/constant/routes';

const ChatLayout = ({ children }) => {
  const isMobile = useIsMobile(768);
  const [sidebarW, setSidebarW] = useState(20);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const graphOpen = useUIStore((s) => s.graphOpen);
  const setGraphOpen = useUIStore((s) => s.setGraphOpen);
  const containerRef = useRef(null);
  const dragging = useRef(null); // 'left' | null
  const location = useLocation();
  // Knowledge Graph + Notifications are tied to the active chat/research
  // session — only meaningful on the main chat route, not on Research Gap,
  // My Reviews, Review Detail, or PDF Agent (which share this same layout).
  const isChatHome = location.pathname === ROUTES.APP;

  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const activeThreadId = sessions.find((s) => s.id === activeSessionId)?.threadId ?? null;
  const ensureLoadedForUser = useChatStore((s) => s.ensureLoadedForUser);
  const userId = useAuthStore((s) => s.user?.id ?? null);

  // Each protected route (/app, /research, /app/reviews, /pdf-agent, ...)
  // mounts its own <ChatLayout>, so this effect re-runs on every navigation
  // between them, not just on login/logout. ensureLoadedForUser is keyed on
  // the signed-in user id internally, so it only resets+refetches when the
  // id actually changes (e.g. account switch), not on every route change.
  useEffect(() => {
    ensureLoadedForUser(userId);
  }, [userId, ensureLoadedForUser]);

  const onMouseDown = useCallback(
    (side) => (e) => {
      e.preventDefault();
      dragging.current = side;
      setIsDragging(true);

      const onMove = (e) => {
        if (!containerRef.current || !dragging.current) return;
        const { left, width } = containerRef.current.getBoundingClientRect();
        const pct = ((e.clientX - left) / width) * 100;
        setSidebarW(Math.max(12, Math.min(30, pct)));
      };

      const onUp = () => {
        dragging.current = null;
        setIsDragging(false);
        window.removeEventListener('mousemove', onMove);
        window.removeEventListener('mouseup', onUp);
      };

      window.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
    },
    []
  );

  // Transparent drag handle (was a solid 0.5px --color-paper-light line —
  // that olive tone read as a bold, blunt-looking rule running the full
  // sidebar height). The actual visual separation now comes from the soft
  // boxShadow on the sidebar panel below; this stays a wider *invisible*
  // hit-target (easier to grab than 0.5px) that only tints faintly on hover.
  const dividerStyle = {
    width: '4px',
    flexShrink: 0,
    cursor: 'col-resize',
    background: 'transparent',
    transition: 'background-color 0.15s',
  };

  if (isMobile) {
    // No explicit background — lets body's dot-grain texture (index.css)
    // show through instead of painting flat solid color over it.
    return (
      <div
        style={{ position: 'relative', height: '100vh', display: 'flex', flexDirection: 'column' }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '6px 8px',
            borderBottom: '1px solid var(--color-paper-light)',
            flexShrink: 0,
          }}
        >
          <button
            onClick={() => setMobileSidebarOpen(true)}
            title="Open menu"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--color-paper-mid)',
              padding: 0,
              width: 44,
              height: 44,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Icon icon="mdi:menu" style={{ fontSize: 22 }} />
          </button>
          {isChatHome && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <NotificationsButton size={44} iconSize={16} />
              <button
                onClick={() => setGraphOpen(true)}
                title="Open Knowledge Graph"
                style={{
                  background: 'none',
                  border: '1px solid var(--color-paper-light)',
                  borderRadius: '50%',
                  cursor: 'pointer',
                  color: 'var(--color-paper-mid)',
                  width: 44,
                  height: 44,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                <Icon icon="mdi:graph-outline" style={{ fontSize: '16px' }} />
              </button>
              <button
                onClick={() => window.Supademo?.open('cmr83e4fj02sgz70j2tn0w0c3')}
                title="How it works"
                style={{
                  background: 'none',
                  border: '1px solid var(--color-paper-light)',
                  borderRadius: '50%',
                  cursor: 'pointer',
                  color: 'var(--color-paper-mid)',
                  width: 44,
                  height: 44,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}
              >
                {/* Plain "?" glyph — mdi:help-circle-outline already draws
                    its own circle, which clashed with this button's own
                    rounded-square border into a nested double-ring look. */}
                <Icon icon="mdi:help" style={{ fontSize: '14px' }} />
              </button>
            </div>
          )}
        </div>

        <div
          className="themed-scroll"
          style={{ flex: 1, minWidth: 0, overflow: 'auto', position: 'relative' }}
        >
          {children}
        </div>

        {mobileSidebarOpen && (
          <>
            <div
              onClick={() => setMobileSidebarOpen(false)}
              style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200 }}
            />
            <div
              onClick={() => setMobileSidebarOpen(false)}
              style={{
                position: 'fixed',
                top: 0,
                left: 0,
                height: '100vh',
                width: 'min(82vw, 320px)',
                zIndex: 201,
                boxShadow: '2px 0 24px rgba(0,0,0,0.18)',
              }}
            >
              <Sidebar collapsed={false} onToggle={() => setMobileSidebarOpen(false)} />
            </div>
          </>
        )}

        {isChatHome && (
          <KnowledgeGraphDrawer
            open={graphOpen}
            onClose={() => setGraphOpen(false)}
            threadId={activeThreadId}
          />
        )}
      </div>
    );
  }

  // No explicit background — lets body's dot-grain texture (index.css) show
  // through instead of painting flat solid color over it.
  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        height: '100vh',
        userSelect: isDragging ? 'none' : 'auto',
      }}
    >
      <div
        style={{
          width: sidebarCollapsed ? '52px' : `${sidebarW}%`,
          flexShrink: 0,
          overflow: 'hidden',
          transition: 'width 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease',
          position: 'relative',
          zIndex: 1,
          // Gemini reference (both collapsed AND expanded): no drawn divider,
          // or one so faint it barely registers. A blurred boxShadow spreads
          // over ~3px and reads heavier than it measures on paper, so swap it
          // for an actual 1px hairline at the same low opacity already used
          // for card borders app-wide (rgba(41,17,0,0.08)) — a true thin line
          // instead of a soft glow. Collapsed still drops it entirely so the
          // 52px icon rail stays fully seamless.
          borderRight: sidebarCollapsed ? 'none' : '1px solid rgba(41, 17, 0, 0.08)',
        }}
      >
        <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed((v) => !v)} />
      </div>

      <div
        style={dividerStyle}
        onMouseDown={onMouseDown('left')}
        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(41, 17, 0, 0.10)')}
        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
      />

      <div
        style={{
          flex: 1,
          minWidth: 0,
          display: 'flex',
          flexDirection: 'column',
          overflow: 'visible',
          position: 'relative',
        }}
      >
        {isChatHome && (
          <div
            style={{
              position: 'absolute',
              top: '12px',
              right: '10px',
              zIndex: 10,
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
            }}
          >
            <NotificationsButton />
            <button
              onClick={() => setGraphOpen(true)}
              title="Open Knowledge Graph"
              style={{
                background: 'var(--color-paper-bg)',
                // Same border color, size (28px), and icon size (14px) as
                // the "?" help button on PDFAgentPage/ResearchPage — one
                // shared round-icon-button spec used everywhere in the app.
                border: '1px solid var(--color-paper-light)',
                borderRadius: '50%',
                cursor: 'pointer',
                width: '28px',
                height: '28px',
                padding: 0,
                color: 'var(--color-paper-mid)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Icon icon="mdi:graph-outline" style={{ width: 14, height: 14 }} />
            </button>
            <button
              onClick={() => window.Supademo?.open('cmr83e4fj02sgz70j2tn0w0c3')}
              title="How it works"
              style={{
                background: 'var(--color-paper-bg)',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '50%',
                cursor: 'pointer',
                width: '28px',
                height: '28px',
                padding: 0,
                color: 'var(--color-paper-mid)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              {/* Plain "?" glyph, same reasoning as the mobile button above. */}
              <Icon icon="mdi:help" style={{ width: 14, height: 14 }} />
            </button>
          </div>
        )}
        {children}
      </div>

      {isChatHome && (
        <KnowledgeGraphDrawer
          open={graphOpen}
          onClose={() => setGraphOpen(false)}
          threadId={activeThreadId}
        />
      )}
    </div>
  );
};

export default ChatLayout;
