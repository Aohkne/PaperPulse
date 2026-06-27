import { useState, useRef, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { Icon } from '@iconify/react';
import Sidebar from '@/features/chat/Sidebar';
import NotificationsButton from '@/features/chat/NotificationsButton';
import KnowledgeGraphDrawer from '@/features/graph/KnowledgeGraphDrawer';
import { useChatStore } from '@/shared/store/useChatStore';
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

  const onMouseDown = useCallback((side) => (e) => {
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
  }, []);

  const dividerStyle = {
    width: '0.5px',
    flexShrink: 0,
    cursor: 'col-resize',
    background: 'var(--color-paper-light)',
    transition: 'background 0.15s',
  };

  if (isMobile) {
    return (
      <div style={{ position: 'relative', height: '100vh', display: 'flex', flexDirection: 'column', background: 'var(--color-paper-bg)' }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '6px 8px', borderBottom: '1px solid var(--color-paper-light)', flexShrink: 0,
        }}>
          <button
            onClick={() => setMobileSidebarOpen(true)}
            title="Open menu"
            style={{
              background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-mid)',
              padding: 0, width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <Icon icon="mdi:menu" style={{ fontSize: 22 }} />
          </button>
          {isChatHome && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <NotificationsButton />
              <button
                onClick={() => setGraphOpen(true)}
                title="Open Knowledge Graph"
                style={{
                  background: 'none', border: '1px solid var(--color-paper-light)', borderRadius: '4px',
                  cursor: 'pointer', color: 'var(--color-paper-mid)',
                  width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                <Icon icon="mdi:graph-outline" style={{ fontSize: '16px' }} />
              </button>
            </div>
          )}
        </div>

        <div style={{ flex: 1, minWidth: 0, overflow: 'auto', position: 'relative' }}>
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
                position: 'fixed', top: 0, left: 0, height: '100vh',
                width: 'min(82vw, 320px)', zIndex: 201,
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

  return (
    <div
      ref={containerRef}
      style={{
        display: 'flex',
        height: '100vh',
        background: 'var(--color-paper-bg)',
        userSelect: isDragging ? 'none' : 'auto',
      }}
    >
      <div style={{ width: sidebarCollapsed ? '52px' : `${sidebarW}%`, flexShrink: 0, overflow: 'hidden', transition: 'width 0.2s ease' }}>
        <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(v => !v)} />
      </div>

      <div
        style={dividerStyle}
        onMouseDown={onMouseDown('left')}
        onMouseEnter={e => e.currentTarget.style.background = 'var(--color-paper-mid)'}
        onMouseLeave={e => e.currentTarget.style.background = 'var(--color-paper-light)'}
      />

      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'visible', position: 'relative' }}>
        {isChatHome && (
          <div style={{ position: 'absolute', top: '12px', right: '10px', zIndex: 10, display: 'flex', alignItems: 'center', gap: '8px' }}>
            <NotificationsButton />
            <button
              onClick={() => setGraphOpen(true)}
              title="Open Knowledge Graph"
              style={{
                background: 'var(--color-paper-bg)',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '4px',
                cursor: 'pointer',
                padding: '4px 6px',
                color: 'var(--color-paper-mid)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Icon icon="mdi:graph-outline" style={{ fontSize: '15px' }} />
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
