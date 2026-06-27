import { useEffect, useMemo, useState } from 'react';
import { Icon } from '@iconify/react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '@/shared/store/useChatStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { ROUTES } from '@/shared/constant/routes';
import AppLauncherModal from '@/features/chat/AppLauncherModal';
import ProfileModal from '@/features/chat/ProfileModal';
import { friendlyError } from '@/shared/utils/errorMessage';

const formatTime = (date) => {
  const d = date instanceof Date ? date : new Date(date);
  const diff = Date.now() - d.getTime();
  if (diff < 60_000) return 'just now';
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`;
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`;
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)}d ago`;
  return d.toLocaleDateString();
};

const getInitials = (user) =>
  user?.name
    ? user.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : (user?.email?.[0]?.toUpperCase() ?? '?');

const getSessionActivityAt = (session) => (
  session?.last_message_at ??
  session?.lastMessageAt ??
  session?.created_at ??
  session?.createdAt ??
  ''
);

const ChatDeleteConfirmModal = ({ isOpen, chatTitle, deleting, onCancel, onConfirm }) => {
  if (!isOpen) return null;

  return (
    <div
      onClick={onCancel}
      style={{
        position: 'absolute',
        inset: 0,
        background: 'rgba(46, 39, 31, 0.22)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        zIndex: 40,
      }}
    >
      <div
        onClick={(event) => event.stopPropagation()}
        style={{
          width: '100%',
          maxWidth: '320px',
          border: '1px solid var(--color-paper-light)',
          borderRadius: '10px',
          background: 'var(--color-paper-bg)',
          boxShadow: '0 22px 40px rgba(46, 39, 31, 0.16)',
          padding: '18px 18px 16px',
        }}
      >
        <div style={{ fontFamily: 'Georgia, serif', fontSize: '18px', color: 'var(--color-paper-dark)', marginBottom: '8px' }}>
          Delete chat history?
        </div>
        <div style={{ fontSize: '13px', color: 'var(--color-paper-mid)', lineHeight: 1.5 }}>
          This chat will be removed from your session list.
        </div>
        {chatTitle && (
          <div
            style={{
              marginTop: '10px',
              fontSize: '12px',
              color: 'var(--color-paper-light)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={chatTitle}
          >
            {chatTitle}
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '18px' }}>
          <button
            onClick={onCancel}
            disabled={deleting}
            style={{
              border: '1px solid var(--color-paper-light)',
              borderRadius: '999px',
              background: 'transparent',
              padding: '6px 12px',
              fontSize: '12px',
              color: 'var(--color-paper-mid)',
              cursor: deleting ? 'not-allowed' : 'pointer',
            }}
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={deleting}
            style={{
              border: '1px solid #b65a52',
              borderRadius: '999px',
              background: '#b65a52',
              padding: '6px 12px',
              fontSize: '12px',
              color: 'white',
              cursor: deleting ? 'not-allowed' : 'pointer',
              opacity: deleting ? 0.72 : 1,
            }}
          >
            {deleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
};

const Sidebar = ({ collapsed, onToggle }) => {
  const sidebarOpen = !collapsed;
  const navigate = useNavigate();
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const newSession = useChatStore((s) => s.newSession);
  const serverChats = useChatStore((s) => s.serverChats);
  const loadChats = useChatStore((s) => s.loadChats);
  const openServerChat = useChatStore((s) => s.openServerChat);
  const createServerChat = useChatStore((s) => s.createServerChat);
  const deleteServerChat = useChatStore((s) => s.deleteServerChat);
  const chatsLoaded = useChatStore((s) => s.chatsLoaded);
  const chatsLoading = useChatStore((s) => s.chatsLoading);
  const chatsError = useChatStore((s) => s.chatsError);
  const chatMutationError = useChatStore((s) => s.chatMutationError);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const theme = useThemeStore((s) => s.theme);
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  const logoSrc = isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png';

  const [profileOpen, setProfileOpen] = useState(false);
  const [launcherOpen, setLauncherOpen] = useState(false);
  const [chatDeleteTarget, setChatDeleteTarget] = useState(null);
  const [chatDeletePending, setChatDeletePending] = useState(false);

  useEffect(() => {
    if (!chatsLoaded && !chatsLoading) {
      loadChats();
    }
  }, [chatsLoaded, chatsLoading, loadChats]);

  const handleNewSession = async () => {
    try {
      await createServerChat();
    } catch {
      newSession();
    }
    navigate(ROUTES.APP);
  };

  const handleSelectSession = (session) => {
    if (serverChats.some((item) => item.id === session.id)) {
      openServerChat(session.id);
    } else {
      setActiveSession(session.id);
    }
    navigate(ROUTES.APP);
  };

  const handleDeleteChat = (event, sessionId, title) => {
    event.stopPropagation();
    setChatDeleteTarget({ id: sessionId, title });
  };

  const handleCancelDeleteChat = () => {
    if (chatDeletePending) return;
    setChatDeleteTarget(null);
  };

  const handleConfirmDeleteChat = async () => {
    if (!chatDeleteTarget?.id || chatDeletePending) return;
    setChatDeletePending(true);
    const deleted = await deleteServerChat(chatDeleteTarget.id);
    setChatDeletePending(false);
    if (deleted) {
      setChatDeleteTarget(null);
    }
  };

  const handleLogout = async () => {
    setProfileOpen(false);
    await logout();
    navigate('/');
  };

  const initials = getInitials(user);
  const sessionList = useMemo(
    () => [...serverChats, ...sessions.filter((session) => !session.persisted)].sort((a, b) => {
      const activityCompare = getSessionActivityAt(b).localeCompare(getSessionActivityAt(a));
      if (activityCompare !== 0) return activityCompare;
      const createdCompare = (b?.created_at ?? b?.createdAt ?? '').localeCompare(a?.created_at ?? a?.createdAt ?? '');
      if (createdCompare !== 0) return createdCompare;
      return String(b?.id ?? '').localeCompare(String(a?.id ?? ''));
    }),
    [serverChats, sessions]
  );

  return (
    <div
      style={{
        width: sidebarOpen ? '100%' : '52px',
        height: '100%',
        transition: 'width 0.2s ease',
        overflow: 'hidden',
        flexShrink: sidebarOpen ? undefined : 0,
        borderRight: '1px solid var(--color-paper-light)',
        backgroundColor: 'var(--color-paper-bg)',
        display: 'flex',
        flexDirection: 'column',
        position: 'relative',
      }}
    >
      <div
        style={{
          padding: sidebarOpen ? '12px 12px 10px' : '12px 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: sidebarOpen ? 'space-between' : 'center',
          borderBottom: '1px solid var(--color-paper-surface)',
          flexShrink: 0,
        }}
      >
        {sidebarOpen && (
          <button
            onClick={() => navigate('/')}
            title="PaperPulse Home"
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: '6px' }}
          >
            <img src={logoSrc} alt="PaperPulse" style={{ height: '28px', width: 'auto', objectFit: 'contain' }} />
            <span style={{
              fontFamily: "'Noto Serif', serif", fontSize: '9px', fontWeight: 700, letterSpacing: '0.04em',
              color: 'var(--color-brand-600)', background: 'var(--color-brand-50)',
              border: '1px solid var(--color-brand-100)', borderRadius: '4px', padding: '2px 5px',
            }}>
              BETA
            </span>
          </button>
        )}
<div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={onToggle}
            title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'var(--color-paper-mid)', padding: 0,
              width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
              flexShrink: 0,
            }}
          >
            <Icon icon={sidebarOpen ? 'mdi:chevron-left' : 'mdi:chevron-right'} style={{ width: 18, height: 18 }} />
          </button>
        </div>
      </div>

      {sidebarOpen ? (
        <>
          <div style={{ padding: '10px 12px 4px', fontSize: '12px', fontWeight: 600, color: 'var(--color-paper-light)', textTransform: 'uppercase', letterSpacing: '0.06em', flexShrink: 0 }}>
            Sessions
          </div>

          {(chatsError || chatMutationError) && (
            <div style={{ margin: '0 12px 8px', padding: '8px 10px', border: '1px solid #d8b4b4', borderRadius: '4px', color: '#8c3b3b', fontSize: '12px', lineHeight: 1.4 }}>
              {friendlyError(chatsError || chatMutationError, "Couldn't load your chats.")}
            </div>
          )}

          <div className="sidebar-scroll" style={{ flex: 1, overflowY: 'auto' }}>
            {chatsLoading && sessionList.length === 0 && (
              <div style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--color-paper-light)' }}>
                Loading chats...
              </div>
            )}

            {sessionList.map((session) => {
              const isActive = session.id === activeSessionId;
              const updatedAt = session.last_message_at ?? session.lastMessageAt ?? session.created_at ?? session.createdAt;
              const isPersisted = session.persisted ?? serverChats.some((item) => item.id === session.id);
              return (
                <button
                  key={session.id}
                  onClick={() => handleSelectSession(session)}
                  style={{
                    width: '100%', textAlign: 'left', padding: '8px 12px 8px 10px',
                    background: 'none', border: 'none',
                    borderLeft: isActive ? '2px solid var(--color-paper-mid)' : '2px solid transparent',
                    backgroundColor: isActive ? 'var(--color-paper-surface)' : 'transparent',
                    cursor: 'pointer', display: 'block', position: 'relative',
                  }}
                >
                  <div style={{
                    fontSize: '15px', fontFamily: "'Noto Serif', serif",
                    color: isActive ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: isPersisted ? '24px' : 0,
                  }}>
                    {session.title}
                  </div>
                  <div
                    style={{
                      display: 'inline-flex', alignItems: 'center', marginTop: '4px',
                      fontSize: '10px', color: 'var(--color-paper-light)',
                      background: 'var(--color-paper-surface)', border: '1px solid var(--color-paper-light)',
                      borderRadius: '10px', padding: '1px 7px',
                    }}
                  >
                    Updated {formatTime(updatedAt)}
                  </div>
                  {isPersisted && (
                    <span
                      onClick={(event) => handleDeleteChat(event, session.id, session.title)}
                      title="Delete chat"
                      style={{ position: 'absolute', top: '10px', right: '10px', color: 'var(--color-paper-light)' }}
                    >
                      <Icon icon="mdi:trash-can-outline" style={{ width: 14, height: 14 }} />
                    </span>
                  )}
                </button>
              );
            })}
          </div>

          <div style={{
            padding: '8px 12px 4px', fontSize: '12px', fontWeight: 600,
            color: 'var(--color-paper-light)', textTransform: 'uppercase', letterSpacing: '0.06em',
            borderTop: '1px solid var(--color-paper-surface)', flexShrink: 0,
          }}>
            Library
          </div>

          <button
            onClick={() => navigate(ROUTES.MY_REVIEWS)}
            style={{
              width: '100%', textAlign: 'left', padding: '10px 12px', minHeight: 40,
              background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px',
            }}
          >
            <Icon icon="mdi:bookshelf" style={{ width: 14, height: 14, color: 'var(--color-paper-light)', flexShrink: 0 }} />
            <span style={{ fontSize: '14px', color: 'var(--color-paper-mid)', fontFamily: "'Noto Serif', serif" }}>
              My Reviews
            </span>
          </button>

          <button
            onClick={() => setLauncherOpen(true)}
            style={{
              width: '100%', textAlign: 'left', padding: '10px 12px', minHeight: 40,
              background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px',
            }}
          >
            <Icon icon="mdi:apps" style={{ width: 14, height: 14, color: 'var(--color-paper-light)', flexShrink: 0 }} />
            <span style={{ fontSize: '14px', color: 'var(--color-paper-mid)', fontFamily: "'Noto Serif', serif" }}>
              Applications
            </span>
          </button>

          <div style={{ padding: '10px 12px 8px', borderTop: '1px solid var(--color-paper-surface)', flexShrink: 0 }}>
            <button
              onClick={handleNewSession}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '6px',
                padding: '10px 10px', minHeight: 40, border: '1px solid var(--color-paper-light)',
                borderRadius: '4px', background: 'none', cursor: 'pointer',
              }}
            >
              <Icon icon="mdi:plus" style={{ width: 14, height: 14, color: 'var(--color-paper-mid)' }} />
              <span style={{ fontSize: '14px', color: 'var(--color-paper-mid)', fontFamily: "'Noto Serif', serif" }}>
                New Session
              </span>
            </button>
          </div>

          <div style={{ padding: '0 12px 12px', flexShrink: 0 }}>
            <button
              onClick={() => setProfileOpen(true)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                padding: '10px 10px', minHeight: 44,
                background: profileOpen ? 'var(--color-paper-surface)' : 'none',
                border: '1px solid var(--color-paper-light)',
                borderRadius: '4px', cursor: 'pointer',
              }}
            >
              <div style={{
                width: 24, height: 24, borderRadius: '50%',
                background: 'var(--color-paper-surface)',
                border: '1px solid var(--color-paper-light)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: '11px', fontFamily: "'Noto Serif', serif",
                color: 'var(--color-paper-mid)', flexShrink: 0, overflow: 'hidden',
              }}>
                {user?.avatar_url
                  ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  : initials}
              </div>
              <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                <div style={{ fontSize: '13px', fontFamily: "'Noto Serif', serif", color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.name || 'Account'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--color-paper-light)', fontFamily: "'Noto Serif', serif", whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.email || ''}
                </div>
              </div>
              <Icon icon="mdi:dots-horizontal" style={{ width: 14, height: 14, color: 'var(--color-paper-light)', flexShrink: 0 }} />
            </button>
          </div>
        </>
      ) : (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', paddingTop: '16px', gap: '16px' }}>
          <div title="Sessions" style={{ cursor: 'pointer', color: 'var(--color-paper-mid)' }}>
            <Icon icon="mdi:chat-outline" style={{ width: 20, height: 20 }} />
          </div>
          <div title="My Reviews" onClick={() => navigate(ROUTES.MY_REVIEWS)} style={{ cursor: 'pointer', color: 'var(--color-paper-mid)' }}>
            <Icon icon="mdi:bookshelf" style={{ width: 20, height: 20 }} />
          </div>
          <div title="Applications" onClick={() => setLauncherOpen(true)} style={{ cursor: 'pointer', color: 'var(--color-paper-mid)' }}>
            <Icon icon="mdi:apps" style={{ width: 20, height: 20 }} />
          </div>
          <div title="New Session" onClick={handleNewSession} style={{ cursor: 'pointer', color: 'var(--color-paper-mid)' }}>
            <Icon icon="mdi:plus" style={{ width: 20, height: 20 }} />
          </div>

          <div style={{ marginTop: 'auto', marginBottom: '12px' }}>
            <button
              onClick={() => setProfileOpen(true)}
              title="Profile"
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-mid)', padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
            >
              {user?.avatar_url
                ? <img src={user.avatar_url} alt="" style={{ width: 22, height: 22, borderRadius: '50%', objectFit: 'cover' }} />
                : <Icon icon="mdi:account-circle-outline" style={{ width: 22, height: 22 }} />}
            </button>
          </div>
        </div>
      )}

      <ChatDeleteConfirmModal
        isOpen={Boolean(chatDeleteTarget)}
        chatTitle={chatDeleteTarget?.title || ''}
        deleting={chatDeletePending}
        onCancel={handleCancelDeleteChat}
        onConfirm={handleConfirmDeleteChat}
      />

      <ProfileModal
        isOpen={profileOpen}
        onClose={() => setProfileOpen(false)}
        user={user}
        onLogout={handleLogout}
      />

      <AppLauncherModal isOpen={launcherOpen} onClose={() => setLauncherOpen(false)} />
    </div>
  );
};

export default Sidebar;
