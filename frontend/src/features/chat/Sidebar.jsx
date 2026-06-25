import { useState } from 'react';
import { Icon } from '@iconify/react';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '@/shared/store/useChatStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { ROUTES } from '@/shared/constant/routes';
import AppLauncherModal from '@/features/chat/AppLauncherModal';
import ProfileModal from '@/features/chat/ProfileModal';

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

const Sidebar = ({ collapsed, onToggle }) => {
  const sidebarOpen = !collapsed;
  const navigate = useNavigate();
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const newSession = useChatStore((s) => s.newSession);
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const theme = useThemeStore((s) => s.theme);
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  const logoSrc = isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png';

  const [profileOpen, setProfileOpen] = useState(false);
  const [launcherOpen, setLauncherOpen] = useState(false);

  const handleNewSession = () => {
    newSession();
    navigate(ROUTES.APP);
  };

  const handleLogout = async () => {
    setProfileOpen(false);
    await logout();
    navigate('/');
  };

  const initials = getInitials(user);

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
      }}
    >
      {/* Header */}
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
              fontFamily: 'Georgia, serif', fontSize: '9px', fontWeight: 700, letterSpacing: '0.04em',
              color: 'var(--color-brand-600)', background: 'var(--color-brand-50)',
              border: '1px solid var(--color-brand-100)', borderRadius: '4px', padding: '2px 5px',
            }}>
              BETA
            </span>
          </button>
        )}
        <button
          onClick={onToggle}
          title={sidebarOpen ? 'Collapse sidebar' : 'Expand sidebar'}
          style={{
            background: 'none', border: 'none', cursor: 'pointer',
            color: 'var(--color-paper-mid)', padding: '2px',
            display: 'flex', alignItems: 'center',
          }}
        >
          <Icon icon={sidebarOpen ? 'mdi:chevron-left' : 'mdi:chevron-right'} style={{ width: 18, height: 18 }} />
        </button>
      </div>

      {sidebarOpen ? (
        <>
          {/* Sessions label */}
          <div style={{ padding: '10px 12px 4px', fontSize: '12px', fontWeight: 600, color: 'var(--color-paper-light)', textTransform: 'uppercase', letterSpacing: '0.06em', flexShrink: 0 }}>
            Sessions
          </div>

          {/* Session list */}
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {sessions.map((session) => {
              const isActive = session.id === activeSessionId;
              return (
                <button
                  key={session.id}
                  onClick={() => setActiveSession(session.id)}
                  style={{
                    width: '100%', textAlign: 'left', padding: '8px 12px 8px 10px',
                    background: 'none', border: 'none',
                    borderLeft: isActive ? '2px solid var(--color-paper-mid)' : '2px solid transparent',
                    backgroundColor: isActive ? 'var(--color-paper-surface)' : 'transparent',
                    cursor: 'pointer', display: 'block',
                  }}
                >
                  <div style={{
                    fontSize: '15px', fontFamily: 'Georgia, serif',
                    color: isActive ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
                    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  }}>
                    {session.title}
                  </div>
                  <div
                    title="Saving sessions is still under development"
                    style={{
                      display: 'inline-flex', alignItems: 'center', marginTop: '4px',
                      fontSize: '10px', color: 'var(--color-paper-light)',
                      background: 'var(--color-paper-surface)', border: '1px solid var(--color-paper-light)',
                      borderRadius: '10px', padding: '1px 7px', cursor: 'help',
                    }}
                  >
                    Updated {formatTime(session.createdAt)}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Library section */}
          <div style={{
            padding: '8px 12px 4px', fontSize: '12px', fontWeight: 600,
            color: 'var(--color-paper-light)', textTransform: 'uppercase', letterSpacing: '0.06em',
            borderTop: '1px solid var(--color-paper-surface)', flexShrink: 0,
          }}>
            Library
          </div>

          {/* My Reviews link */}
          <button
            onClick={() => navigate(ROUTES.MY_REVIEWS)}
            style={{
              width: '100%', textAlign: 'left', padding: '6px 12px',
              background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px',
            }}
          >
            <Icon icon="mdi:bookshelf" style={{ width: 14, height: 14, color: 'var(--color-paper-light)', flexShrink: 0 }} />
            <span style={{ fontSize: '14px', color: 'var(--color-paper-mid)', fontFamily: 'Georgia, serif' }}>
              My Reviews
            </span>
          </button>

          {/* Applications launcher */}
          <button
            onClick={() => setLauncherOpen(true)}
            style={{
              width: '100%', textAlign: 'left', padding: '6px 12px',
              background: 'none', border: 'none', cursor: 'pointer',
              display: 'flex', alignItems: 'center', gap: '8px',
            }}
          >
            <Icon icon="mdi:apps" style={{ width: 14, height: 14, color: 'var(--color-paper-light)', flexShrink: 0 }} />
            <span style={{ fontSize: '14px', color: 'var(--color-paper-mid)', fontFamily: 'Georgia, serif' }}>
              Applications
            </span>
          </button>

          {/* New Session */}
          <div style={{ padding: '10px 12px 8px', borderTop: '1px solid var(--color-paper-surface)', flexShrink: 0 }}>
            <button
              onClick={handleNewSession}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '6px',
                padding: '6px 10px', border: '1px solid var(--color-paper-light)',
                borderRadius: '4px', background: 'none', cursor: 'pointer',
              }}
            >
              <Icon icon="mdi:plus" style={{ width: 14, height: 14, color: 'var(--color-paper-mid)' }} />
              <span style={{ fontSize: '14px', color: 'var(--color-paper-mid)', fontFamily: 'Georgia, serif' }}>
                New Session
              </span>
            </button>
          </div>

          {/* Profile trigger */}
          <div style={{ padding: '0 12px 12px', flexShrink: 0 }}>
            <button
              onClick={() => setProfileOpen(true)}
              style={{
                width: '100%', display: 'flex', alignItems: 'center', gap: '8px',
                padding: '7px 10px',
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
                fontSize: '11px', fontFamily: 'Georgia, serif',
                color: 'var(--color-paper-mid)', flexShrink: 0, overflow: 'hidden',
              }}>
                {user?.avatar_url
                  ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                  : initials}
              </div>
              <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                <div style={{ fontSize: '13px', fontFamily: 'Georgia, serif', color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.name || 'Account'}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--color-paper-light)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.email || ''}
                </div>
              </div>
              <Icon icon="mdi:dots-horizontal" style={{ width: 14, height: 14, color: 'var(--color-paper-light)', flexShrink: 0 }} />
            </button>
          </div>
        </>
      ) : (
        /* Collapsed — icon bar */
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

          {/* Profile icon — collapsed */}
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
