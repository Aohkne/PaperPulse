import { useState, useRef, useCallback } from 'react';
import { Icon } from '@iconify/react';
import Sidebar from '@/features/chat/Sidebar';
import KnowledgeGraphDrawer from '@/features/graph/KnowledgeGraphDrawer';
import { useChatStore } from '@/shared/store/useChatStore';
import { useUIStore } from '@/shared/store/useUIStore';

const ChatLayout = ({ children }) => {
  const [sidebarW, setSidebarW] = useState(20);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const graphOpen = useUIStore((s) => s.graphOpen);
  const setGraphOpen = useUIStore((s) => s.setGraphOpen);
  const containerRef = useRef(null);
  const dragging = useRef(null); // 'left' | null

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
        <button
          onClick={() => setGraphOpen(true)}
          title="Open Knowledge Graph"
          style={{
            position: 'absolute',
            top: '12px',
            right: '10px',
            zIndex: 10,
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
        {children}
      </div>

      <KnowledgeGraphDrawer
        open={graphOpen}
        onClose={() => setGraphOpen(false)}
        threadId={activeThreadId}
      />
    </div>
  );
};

export default ChatLayout;
