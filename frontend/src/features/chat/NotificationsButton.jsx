import { useEffect } from 'react';
import { Icon } from '@iconify/react';
import { useChatStore } from '@/shared/store/useChatStore';
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

// Slim on/off switch for in-app alerts. pauseAllInApp === true means OFF.
const AlertsToggle = ({ pauseAllInApp, onToggle }) => {
  const on = !pauseAllInApp;
  return (
    <button
      onClick={() => onToggle(!pauseAllInApp)}
      title={on ? 'Notifications on' : 'Notifications off'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 6,
        border: '1px solid rgba(41, 17, 0, 0.12)',
        borderRadius: 999,
        background: on ? 'var(--color-brand-50)' : 'transparent',
        padding: '4px 10px',
        fontSize: 11,
        color: on ? 'var(--color-brand-600)' : 'var(--color-paper-mid)',
        cursor: 'pointer',
        flexShrink: 0,
      }}
    >
      <Icon
        icon={on ? 'mdi:bell-outline' : 'mdi:bell-off-outline'}
        style={{ width: 14, height: 14 }}
      />
      {on ? 'On' : 'Off'}
    </button>
  );
};

const NotificationPanel = ({
  notifications,
  unreadCount,
  notificationsError,
  pauseAllInApp,
  onTogglePause,
  onMarkOneRead,
  onMarkAllRead,
}) => (
  <div
    className="themed-scroll"
    style={{
      position: 'absolute',
      top: 'calc(100% + 8px)',
      right: 0,
      width: '340px',
      maxWidth: 'calc(100vw - 32px)',
      maxHeight: '75vh',
      overflowY: 'auto',
      border: '1px solid rgba(41, 17, 0, 0.08)',
      borderRadius: '16px',
      background: 'var(--color-paper-surface)',
      boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 8px 24px rgba(41, 17, 0, 0.12)',
      zIndex: 30,
    }}
  >
    {/* Header: title + on/off toggle, then status + mark-all-read */}
    <div style={{ padding: '12px 14px', borderBottom: '1px solid rgba(41, 17, 0, 0.08)' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '10px',
        }}
      >
        <div
          style={{
            fontFamily: 'Georgia, serif',
            fontSize: '15px',
            color: 'var(--color-paper-dark)',
          }}
        >
          Notifications
        </div>
        <AlertsToggle pauseAllInApp={pauseAllInApp} onToggle={onTogglePause} />
      </div>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '10px',
          marginTop: '4px',
        }}
      >
        <div style={{ fontSize: '11px', color: 'var(--color-paper-mid)' }}>
          {pauseAllInApp
            ? 'Notifications are off'
            : unreadCount > 0
              ? `${unreadCount} unread`
              : 'All caught up'}
        </div>
        {unreadCount > 0 && (
          <button
            onClick={onMarkAllRead}
            style={{
              border: 'none',
              background: 'transparent',
              padding: 0,
              fontSize: '11px',
              color: 'var(--color-paper-mid)',
              cursor: 'pointer',
            }}
          >
            Mark all read
          </button>
        )}
      </div>
    </div>

    {notificationsError && (
      <div
        style={{
          margin: '10px 12px 0',
          padding: '8px 10px',
          border: '1px solid #d8b4b4',
          borderRadius: '4px',
          color: '#8c3b3b',
          fontSize: '12px',
          lineHeight: 1.4,
        }}
      >
        {friendlyError(notificationsError, "Couldn't load your notifications.")}
      </div>
    )}

    {notifications.length === 0 ? (
      <div
        style={{
          padding: '18px 14px',
          fontSize: '12px',
          color: 'var(--color-paper-mid)',
          lineHeight: 1.5,
        }}
      >
        No paper alerts yet.
      </div>
    ) : (
      notifications.map((item) => {
        const title = item.paper_ref?.title || 'Untitled paper';
        const topicLine = item.content || 'New paper alert';
        return (
          <div
            key={item.id}
            style={{
              padding: '12px 14px',
              borderTop: '1px solid rgba(41, 17, 0, 0.08)',
              background: item.is_read ? 'transparent' : 'rgba(196, 166, 122, 0.08)',
            }}
          >
            <div
              style={{
                display: 'flex',
                alignItems: 'flex-start',
                justifyContent: 'space-between',
                gap: '10px',
              }}
            >
              <div style={{ minWidth: 0, flex: 1 }}>
                <div
                  style={{ fontSize: '11px', color: 'var(--color-paper-mid)', marginBottom: '3px' }}
                >
                  {topicLine}
                </div>
                <div
                  style={{
                    fontFamily: 'Georgia, serif',
                    fontSize: '14px',
                    color: 'var(--color-paper-dark)',
                    lineHeight: 1.35,
                  }}
                >
                  {title}
                </div>
                <div
                  style={{ marginTop: '7px', fontSize: '11px', color: 'var(--color-paper-mid)' }}
                >
                  {formatTime(item.created_at)}
                </div>
              </div>
              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'flex-end',
                  gap: '8px',
                  flexShrink: 0,
                }}
              >
                {!item.is_read && (
                  <span
                    style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      background: 'var(--color-brand-600)',
                    }}
                  />
                )}
                {!item.is_read && (
                  <button
                    onClick={() => onMarkOneRead(item.id)}
                    style={{
                      border: 'none',
                      background: 'transparent',
                      padding: 0,
                      fontSize: '11px',
                      color: 'var(--color-paper-mid)',
                      cursor: 'pointer',
                    }}
                  >
                    Mark read
                  </button>
                )}
                {item.paper_ref?.url && (
                  <a
                    href={item.paper_ref.url}
                    target="_blank"
                    rel="noreferrer"
                    style={{
                      fontSize: '11px',
                      color: 'var(--color-brand-600)',
                      textDecoration: 'none',
                    }}
                  >
                    Open paper
                  </a>
                )}
              </div>
            </div>
          </div>
        );
      })
    )}
  </div>
);

/**
 * Bell notification trigger + dropdown panel — lives next to the "Open
 * Knowledge Graph" button in ChatLayout. Slimmed to just an on/off toggle and
 * the alert feed (topic-management controls were removed as redundant).
 */
const NotificationsButton = ({ size = 28, iconSize = 14 }) => {
  const notifications = useChatStore((s) => s.notifications);
  const notificationsLoaded = useChatStore((s) => s.notificationsLoaded);
  const notificationsLoading = useChatStore((s) => s.notificationsLoading);
  const notificationsError = useChatStore((s) => s.notificationsError);
  const notificationsPanelOpen = useChatStore((s) => s.notificationsPanelOpen);
  const unreadNotificationCount = useChatStore((s) => s.unreadNotificationCount);
  const loadNotifications = useChatStore((s) => s.loadNotifications);
  const markNotificationRead = useChatStore((s) => s.markNotificationRead);
  const markAllNotificationsRead = useChatStore((s) => s.markAllNotificationsRead);
  const setNotificationsPanelOpen = useChatStore((s) => s.setNotificationsPanelOpen);
  const pauseAllInApp = useChatStore((s) => s.pauseAllInApp);
  const setPauseAllInApp = useChatStore((s) => s.setPauseAllInApp);

  useEffect(() => {
    if (!notificationsLoaded && !notificationsLoading) {
      loadNotifications();
    }
  }, [notificationsLoaded, notificationsLoading, loadNotifications]);

  const handleToggleNotifications = () => {
    const nextOpen = !notificationsPanelOpen;
    setNotificationsPanelOpen(nextOpen);
    if (nextOpen) void loadNotifications();
  };

  return (
    <div style={{ position: 'relative' }}>
      <button
        onClick={handleToggleNotifications}
        title="Notifications"
        style={{
          position: 'relative',
          background: 'var(--color-paper-bg)',
          border: '1px solid var(--color-paper-light)',
          borderRadius: '50%',
          cursor: 'pointer',
          width: `${size}px`,
          height: `${size}px`,
          padding: 0,
          color: 'var(--color-paper-mid)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <Icon icon="mdi:bell-outline" style={{ width: iconSize, height: iconSize }} />
        {unreadNotificationCount > 0 && (
          <span
            style={{
              position: 'absolute',
              top: '-4px',
              right: '-4px',
              minWidth: '16px',
              height: '16px',
              borderRadius: '999px',
              background: 'var(--color-brand-600)',
              color: 'white',
              fontSize: '10px',
              lineHeight: '16px',
              textAlign: 'center',
              padding: '0 4px',
            }}
          >
            {unreadNotificationCount > 9 ? '9+' : unreadNotificationCount}
          </span>
        )}
      </button>

      {notificationsPanelOpen && (
        <NotificationPanel
          notifications={notifications}
          unreadCount={unreadNotificationCount}
          notificationsError={notificationsError}
          pauseAllInApp={pauseAllInApp}
          onTogglePause={setPauseAllInApp}
          onMarkOneRead={markNotificationRead}
          onMarkAllRead={markAllNotificationsRead}
        />
      )}
    </div>
  );
};

export default NotificationsButton;
