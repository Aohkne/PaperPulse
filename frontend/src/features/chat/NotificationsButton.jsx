import { useEffect, useMemo, useState } from 'react';
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

const stateLabel = (state) => {
  if (state === 'auto_watching') return 'Watching';
  if (state === 'muted') return 'Muted';
  return 'Candidate';
};

const TopicDeleteConfirmModal = ({ isOpen, topicLabel, deleting, onCancel, onConfirm }) => {
  if (!isOpen) return null;

  return (
    <div
      onClick={deleting ? undefined : onCancel}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(46, 39, 31, 0.22)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '20px',
        zIndex: 210,
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
          Remove tracked topic?
        </div>
        <div style={{ fontSize: '13px', color: 'var(--color-paper-mid)', lineHeight: 1.5 }}>
          This topic will be removed from your tracked interests.
        </div>
        {topicLabel && (
          <div
            style={{
              marginTop: '10px',
              fontSize: '12px',
              color: 'var(--color-paper-light)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
            title={topicLabel}
          >
            {topicLabel}
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
            {deleting ? 'Deleting...' : 'Remove'}
          </button>
        </div>
      </div>
    </div>
  );
};

const NotificationPanel = ({
  notifications,
  unreadCount,
  notificationsError,
  pauseAllInApp,
  topicInterests,
  topicInterestsError,
  topicInterestsLoading,
  onTogglePause,
  onMarkOneRead,
  onMarkAllRead,
  onToggleTopicState,
  onDeleteTopic,
  topicInterestPendingById,
}) => {
  const [topicControlsExpanded, setTopicControlsExpanded] = useState(false);

  const topicSummary = useMemo(() => {
    if (topicInterestsLoading) return 'Loading tracked topics...';
    if (topicInterests.length === 0) return 'No tracked topics yet';

    const counts = topicInterests.reduce((acc, topic) => {
      acc.total += 1;
      if (topic.state === 'auto_watching') acc.watching += 1;
      else if (topic.state === 'muted') acc.muted += 1;
      else acc.candidate += 1;
      return acc;
    }, { total: 0, watching: 0, muted: 0, candidate: 0 });

    const parts = [];
    if (counts.watching) parts.push(`${counts.watching} watching`);
    if (counts.candidate) parts.push(`${counts.candidate} candidate`);
    if (counts.muted) parts.push(`${counts.muted} muted`);
    return parts.length > 0 ? parts.join(', ') : `${counts.total} tracked topics`;
  }, [topicInterests, topicInterestsLoading]);

  return (
    <div
      style={{
        position: 'absolute',
        top: 'calc(100% + 8px)',
        right: 0,
        width: '340px',
        maxWidth: 'calc(100vw - 32px)',
        maxHeight: '75vh',
        overflowY: 'auto',
        border: '1px solid var(--color-paper-light)',
        borderRadius: '8px',
        background: 'var(--color-paper-bg)',
        boxShadow: '0 18px 40px rgba(46, 39, 31, 0.12)',
        zIndex: 30,
      }}
    >
      <div style={{ padding: '12px 14px 10px', borderBottom: '1px solid var(--color-paper-surface)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
          <div>
            <div style={{ fontFamily: 'Georgia, serif', fontSize: '15px', color: 'var(--color-paper-dark)' }}>
              Notifications
            </div>
            <div style={{ fontSize: '11px', color: 'var(--color-paper-light)' }}>
              {pauseAllInApp ? 'Paused globally' : unreadCount > 0 ? `${unreadCount} unread` : 'All caught up'}
            </div>
          </div>
          <button
            onClick={onMarkAllRead}
            disabled={unreadCount === 0}
            style={{
              border: '1px solid var(--color-paper-light)',
              borderRadius: '999px',
              background: 'transparent',
              padding: '4px 9px',
              fontSize: '11px',
              color: unreadCount === 0 ? 'var(--color-paper-light)' : 'var(--color-paper-mid)',
              cursor: unreadCount === 0 ? 'not-allowed' : 'pointer',
            }}
          >
            Mark all read
          </button>
        </div>
      </div>

      <div style={{ padding: '12px 14px 14px', borderBottom: '1px solid var(--color-paper-surface)' }}>
        <div
          style={{
            border: '1px solid var(--color-paper-surface)',
            borderRadius: '8px',
            background: 'rgba(196, 166, 122, 0.08)',
            padding: '12px',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
          }}
        >
          <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-paper-light)' }}>
            Controls
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ fontFamily: 'Georgia, serif', fontSize: '14px', color: 'var(--color-paper-dark)' }}>
                Pause in-app alerts
              </div>
              <div style={{ fontSize: '11px', color: 'var(--color-paper-light)', marginTop: '2px', lineHeight: 1.45 }}>
                Keep topic scoring running, but stop materializing alerts for now.
              </div>
            </div>
            <button
              onClick={() => onTogglePause(!pauseAllInApp)}
              style={{
                border: '1px solid var(--color-paper-light)',
                borderRadius: '999px',
                background: pauseAllInApp ? 'var(--color-paper-dark)' : 'transparent',
                color: pauseAllInApp ? 'var(--color-paper-bg)' : 'var(--color-paper-mid)',
                padding: '4px 10px',
                fontSize: '11px',
                cursor: 'pointer',
                flexShrink: 0,
              }}
            >
              {pauseAllInApp ? 'Paused' : 'Active'}
            </button>
          </div>

          <div style={{ borderTop: '1px solid var(--color-paper-surface)', paddingTop: '12px' }}>
            <button
              onClick={() => setTopicControlsExpanded((value) => !value)}
              style={{
                width: '100%',
                border: 'none',
                background: 'transparent',
                padding: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                gap: '10px',
                cursor: 'pointer',
                textAlign: 'left',
              }}
            >
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{ fontFamily: 'Georgia, serif', fontSize: '14px', color: 'var(--color-paper-dark)' }}>
                  Topic controls
                </div>
                <div style={{ fontSize: '11px', color: 'var(--color-paper-light)', marginTop: '2px', lineHeight: 1.45 }}>
                  {topicSummary}
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                <span style={{ fontSize: '11px', color: 'var(--color-paper-mid)' }}>
                  {topicControlsExpanded ? 'Hide' : 'Show'}
                </span>
                <Icon icon={topicControlsExpanded ? 'mdi:chevron-up' : 'mdi:chevron-down'} style={{ width: 16, height: 16, color: 'var(--color-paper-mid)' }} />
              </div>
            </button>

            {topicControlsExpanded && (
              <div style={{ marginTop: '12px' }}>
                <div style={{ fontSize: '11px', color: 'var(--color-paper-light)', marginBottom: '10px', lineHeight: 1.45 }}>
                  Mute, restore, or remove tracked topics without leaving the chat shell.
                </div>

                {topicInterestsError && (
                  <div style={{ marginBottom: '10px', padding: '8px 10px', border: '1px solid #d8b4b4', borderRadius: '4px', color: '#8c3b3b', fontSize: '12px', lineHeight: 1.4 }}>
                    {friendlyError(topicInterestsError, "Couldn't load your tracked topics.")}
                  </div>
                )}

                {topicInterestsLoading ? (
                  <div style={{ fontSize: '12px', color: 'var(--color-paper-light)' }}>Loading topics...</div>
                ) : topicInterests.length === 0 ? (
                  <div style={{ fontSize: '12px', color: 'var(--color-paper-light)' }}>No tracked topics yet.</div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    {topicInterests.map((topic) => {
                      const topicPending = Boolean(topicInterestPendingById[topic.topic_id]);
                      return (
                      <div key={topic.topic_id} style={{ border: '1px solid var(--color-paper-surface)', borderRadius: '6px', padding: '10px', background: 'var(--color-paper-bg)', opacity: topicPending ? 0.72 : 1 }}>
                        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div style={{ fontFamily: 'Georgia, serif', fontSize: '14px', color: 'var(--color-paper-dark)', lineHeight: 1.35 }}>
                              {topic.label}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '5px', flexWrap: 'wrap' }}>
                              <span style={{ fontSize: '10px', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-light)', borderRadius: '999px', padding: '2px 7px' }}>
                                {stateLabel(topic.state)}
                              </span>
                              {topic.auto_watch_reason && (
                                <span style={{ fontSize: '10px', color: 'var(--color-paper-light)' }}>
                                  {topic.auto_watch_reason}
                                </span>
                              )}
                            </div>
                          </div>
                          <button
                            onClick={() => onDeleteTopic(topic.topic_id)}
                            disabled={topicPending}
                            style={{ border: 'none', background: 'transparent', padding: 0, color: 'var(--color-paper-light)', cursor: topicPending ? 'not-allowed' : 'pointer', opacity: topicPending ? 0.6 : 1 }}
                            title="Delete topic interest"
                          >
                            <Icon icon="mdi:trash-can-outline" style={{ width: 14, height: 14 }} />
                          </button>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px', marginTop: '8px' }}>
                          <div style={{ fontSize: '11px', color: 'var(--color-paper-light)' }}>
                            Score {Number(topic.interest_score ?? 0).toFixed(1)}
                          </div>
                          <button
                            onClick={() => onToggleTopicState(topic.topic_id, topic.state === 'muted' ? 'candidate' : 'muted')}
                            disabled={topicPending}
                            style={{
                              border: '1px solid var(--color-paper-light)',
                              borderRadius: '999px',
                              background: topicPending ? 'var(--color-paper-surface)' : 'transparent',
                              padding: '4px 9px',
                              fontSize: '11px',
                              color: 'var(--color-paper-mid)',
                              cursor: topicPending ? 'not-allowed' : 'pointer',
                              flexShrink: 0,
                              opacity: topicPending ? 0.7 : 1,
                            }}
                          >
                            {topicPending ? 'Updating...' : topic.state === 'muted' ? 'Unmute' : 'Mute'}
                          </button>
                        </div>
                      </div>
                    );})}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      <div style={{ padding: '12px 14px 8px', borderBottom: notifications.length > 0 ? '1px solid var(--color-paper-surface)' : 'none' }}>
        <div style={{ fontSize: '10px', fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-paper-light)' }}>
          Alert feed
        </div>
        <div style={{ fontSize: '11px', color: 'var(--color-paper-light)', marginTop: '3px' }}>
          Recent paper matches for your watched topics.
        </div>
      </div>

      {notificationsError && (
        <div style={{ margin: '10px 12px 0', padding: '8px 10px', border: '1px solid #d8b4b4', borderRadius: '4px', color: '#8c3b3b', fontSize: '12px', lineHeight: 1.4 }}>
          {friendlyError(notificationsError, "Couldn't load your notifications.")}
        </div>
      )}

      {notifications.length === 0 ? (
        <div style={{ padding: '16px 14px 18px', fontSize: '12px', color: 'var(--color-paper-light)', lineHeight: 1.5 }}>
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
                borderTop: '1px solid var(--color-paper-surface)',
                background: item.is_read ? 'transparent' : 'rgba(196, 166, 122, 0.08)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '10px' }}>
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontSize: '11px', color: 'var(--color-paper-light)', marginBottom: '3px' }}>
                    {topicLine}
                  </div>
                  <div style={{ fontFamily: 'Georgia, serif', fontSize: '14px', color: 'var(--color-paper-dark)', lineHeight: 1.35 }}>
                    {title}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--color-paper-mid)', lineHeight: 1.45, marginTop: '5px' }}>
                    {item.reason || 'Matched your watched topic.'}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginTop: '7px', fontSize: '11px', color: 'var(--color-paper-light)', flexWrap: 'wrap' }}>
                    <span>{formatTime(item.created_at)}</span>
                    {item.score != null && <span>Score {Number(item.score).toFixed(2)}</span>}
                  </div>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px', flexShrink: 0 }}>
                  {!item.is_read && (
                    <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--color-brand-600)' }} />
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
                      style={{ fontSize: '11px', color: 'var(--color-brand-600)', textDecoration: 'none' }}
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
};

/**
 * Bell notification trigger + dropdown panel — lives next to the "Open
 * Knowledge Graph" button in ChatLayout (both desktop and mobile) so the two
 * top-level chat actions are grouped together instead of the bell being
 * anchored inside the sidebar header, far from the graph button.
 */
const NotificationsButton = () => {
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
  const topicInterests = useChatStore((s) => s.topicInterests);
  const topicInterestsLoaded = useChatStore((s) => s.topicInterestsLoaded);
  const topicInterestsError = useChatStore((s) => s.topicInterestsError);
  const topicInterestsLoading = useChatStore((s) => s.topicInterestsLoading);
  const pauseAllInApp = useChatStore((s) => s.pauseAllInApp);
  const loadTopicInterests = useChatStore((s) => s.loadTopicInterests);
  const setPauseAllInApp = useChatStore((s) => s.setPauseAllInApp);
  const updateTopicInterestState = useChatStore((s) => s.updateTopicInterestState);
  const deleteTopicInterest = useChatStore((s) => s.deleteTopicInterest);
  const topicInterestPendingById = useChatStore((s) => s.topicInterestPendingById);

  const [topicDeleteTarget, setTopicDeleteTarget] = useState(null);
  const [topicDeletePending, setTopicDeletePending] = useState(false);

  useEffect(() => {
    if (!notificationsLoaded && !notificationsLoading) {
      loadNotifications();
    }
  }, [notificationsLoaded, notificationsLoading, loadNotifications]);

  useEffect(() => {
    if (!topicInterestsLoaded && !topicInterestsLoading) {
      loadTopicInterests();
    }
  }, [topicInterestsLoaded, topicInterestsLoading, loadTopicInterests]);

  const handleToggleNotifications = () => {
    const nextOpen = !notificationsPanelOpen;
    setNotificationsPanelOpen(nextOpen);
    if (nextOpen) {
      void loadNotifications();
      void loadTopicInterests();
    }
  };

  const handleDeleteTopic = (topicId, label) => {
    setTopicDeleteTarget({ id: topicId, label });
  };

  const handleCancelDeleteTopic = () => {
    if (topicDeletePending) return;
    setTopicDeleteTarget(null);
  };

  const handleConfirmDeleteTopic = async () => {
    if (!topicDeleteTarget?.id || topicDeletePending) return;
    setTopicDeletePending(true);
    const deleted = await deleteTopicInterest(topicDeleteTarget.id);
    setTopicDeletePending(false);
    if (deleted) {
      setTopicDeleteTarget(null);
    }
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
          borderRadius: '4px',
          cursor: 'pointer',
          padding: '4px 6px',
          color: 'var(--color-paper-mid)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <Icon icon="mdi:bell-outline" style={{ fontSize: '15px' }} />
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
          topicInterests={topicInterests}
          topicInterestsError={topicInterestsError}
          topicInterestsLoading={topicInterestsLoading}
          onTogglePause={setPauseAllInApp}
          onMarkOneRead={markNotificationRead}
          onMarkAllRead={markAllNotificationsRead}
          onToggleTopicState={updateTopicInterestState}
          topicInterestPendingById={topicInterestPendingById}
          onDeleteTopic={(topicId) => {
            const topic = topicInterests.find((item) => item.topic_id === topicId);
            handleDeleteTopic(topicId, topic?.label || 'this topic');
          }}
        />
      )}

      <TopicDeleteConfirmModal
        isOpen={Boolean(topicDeleteTarget)}
        topicLabel={topicDeleteTarget?.label || ''}
        deleting={topicDeletePending}
        onCancel={handleCancelDeleteTopic}
        onConfirm={handleConfirmDeleteTopic}
      />
    </div>
  );
};

export default NotificationsButton;
