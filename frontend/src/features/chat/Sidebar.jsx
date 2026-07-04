import { useEffect, useMemo, useRef, useState } from 'react';
import { Icon } from '@iconify/react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useChatStore } from '@/shared/store/useChatStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { ROUTES } from '@/shared/constant/routes';
import AppLauncherModal from '@/features/chat/AppLauncherModal';
import ProfileModal from '@/features/chat/ProfileModal';
import { friendlyError } from '@/shared/utils/errorMessage';

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
              color: 'var(--color-paper-mid)',
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

// One row in the Sessions list. Hover-to-reveal kebab menu (matches the
// Gemini reference the user asked to follow) instead of a permanently
// visible trash icon — keeps the row focused on the title until the user
// actually wants to act on it. Only "Delete" is wired up for real: there's
// no rename/pin/share endpoint on the backend yet (chats only support
// POST create + DELETE, see useChatStore), so those Gemini-menu items are
// left out rather than added as dead buttons.
const SessionRow = ({ title, isActive, isPersisted, onSelect, onDelete }) => {
  const [hovered, setHovered] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e) => { if (!menuRef.current?.contains(e.target)) setMenuOpen(false); };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const showKebab = isPersisted && (hovered || menuOpen);

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ position: 'relative' }}
    >
      <button
        onClick={onSelect}
        style={{
          width: '100%', textAlign: 'left', padding: '6px 12px',
          background: 'none', border: 'none',
          borderLeft: isActive ? '2px solid var(--color-paper-mid)' : '2px solid transparent',
          backgroundColor: isActive ? 'var(--color-paper-surface)' : 'transparent',
          cursor: 'pointer', display: 'block',
        }}
      >
        <div style={{
          fontSize: '15px', fontFamily: "'Newsreader', serif",
          fontWeight: 400,
          color: 'var(--color-paper-dark)',
          whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
          paddingRight: isPersisted ? '26px' : 0,
        }}>
          {title}
        </div>
      </button>

      {showKebab && (
        <button
          onClick={(event) => { event.stopPropagation(); setMenuOpen((v) => !v); }}
          title="Chat options"
          style={{
            position: 'absolute', top: '6px', right: '6px',
            width: 26, height: 26, display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: menuOpen ? 'var(--color-paper-bg)' : 'none', border: 'none', borderRadius: '6px',
            cursor: 'pointer', color: 'var(--color-paper-mid)',
          }}
        >
          <Icon icon="mdi:dots-horizontal" style={{ width: 16, height: 16 }} />
        </button>
      )}

      <AnimatePresence>
        {menuOpen && (
          <motion.div
            ref={menuRef}
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.12 }}
            style={{
              position: 'absolute', top: '34px', right: '6px', zIndex: 50,
              background: 'var(--color-paper-surface)', border: '1px solid rgba(41, 17, 0, 0.08)',
              borderRadius: '10px', boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 8px 24px rgba(41, 17, 0, 0.14)',
              minWidth: '140px', overflow: 'hidden', padding: '4px',
            }}
          >
            <button
              onClick={(event) => { event.stopPropagation(); setMenuOpen(false); onDelete(event); }}
              style={{
                width: '100%', textAlign: 'left', padding: '8px 10px', background: 'none', border: 'none',
                borderRadius: '6px', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '8px',
                fontFamily: "'Newsreader', serif", fontSize: '13px', color: '#c0392b',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-paper-bg)')}
              onMouseLeave={(e) => (e.currentTarget.style.background = 'none')}
            >
              <Icon icon="mdi:trash-can-outline" style={{ width: 14, height: 14 }} />
              Delete
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// One nav row (New Session / My Reviews / Applications). Same button in both
// sidebar states — only the label fades in/out — instead of two separate
// icon-only vs icon+label implementations. That's what makes the Gemini
// reference collapse read as "smooth": the icon never jumps or swaps, only
// the text beside it fades, and every icon gets the same rounded hover
// highlight whether the sidebar is open or collapsed.
const NavItem = ({ icon, label, collapsed, onClick, badge, labelWeight = 400 }) => (
  <button
    onClick={onClick}
    title={collapsed ? label : undefined}
    style={{
      width: '100%', display: 'flex', alignItems: 'center',
      justifyContent: collapsed ? 'center' : 'flex-start',
      gap: '10px', padding: collapsed ? '9px 0' : '9px 10px', minHeight: 38,
      background: 'none', border: 'none', borderRadius: '8px', cursor: 'pointer',
      transition: 'background-color 0.15s',
    }}
    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = 'var(--color-paper-surface)'; }}
    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent'; }}
  >
    {/* Both branches use the same 24px-wide slot (badge circle vs a plain
        icon centered in an equal-size invisible box) so New Session's icon
        and My Reviews/Applications' icons all sit at the same x-position —
        previously the plain icons (18px, no wrapper) started further left
        than the badge circle (24px), so the three labels beside them didn't
        line up in a straight column. */}
    {badge ? (
      // Filled with the same green (--color-paper-mid) as the My
      // Reviews/Applications icons below, so all three read as one matching
      // set instead of this one being an off-tone gray circle. The "+" uses
      // --color-paper-bg (the page/sidebar background color itself) instead
      // of a fixed dark tone — that token already flips light↔dark with the
      // theme, so the glyph automatically stays dark-on-green in light mode
      // and light-on-green in dark mode, matching either background.
      <div style={{
        width: 24, height: 24, borderRadius: '50%', flexShrink: 0,
        background: 'var(--color-paper-mid)', border: 'none',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon icon={icon} style={{ width: 14, height: 14, color: 'var(--color-paper-bg)' }} />
      </div>
    ) : (
      <div style={{ width: 24, height: 24, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon icon={icon} style={{ width: 18, height: 18, color: 'var(--color-paper-mid)' }} />
      </div>
    )}
    <AnimatePresence initial={false}>
      {!collapsed && (
        <motion.span
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
          style={{
            fontSize: '14px', fontWeight: labelWeight, color: 'var(--color-paper-mid)',
            fontFamily: "'Newsreader', serif", whiteSpace: 'nowrap', overflow: 'hidden',
          }}
        >
          {label}
        </motion.span>
      )}
    </AnimatePresence>
  </button>
);

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

  // Local-only draft session — no server call here on purpose. Calling
  // createServerChat() immediately (the old behavior) persisted an empty
  // "New chat" row to history the instant this button was clicked, even if
  // the user never typed anything (e.g. clicking it just to get back to the
  // chat screen from Gap/PDF Agent). newSession() only touches local state;
  // the existing sendMessage()/_sendMessageImpl() flow already persists the
  // session to the server (with a real title) the moment the user actually
  // sends their first message — so chats now only show up in history once
  // there's something in them, matching the Gemini reference. No backend
  // change needed: this only changes which existing frontend function runs.
  const handleNewSession = () => {
    newSession();
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
  // Local draft sessions only join the visible list once they actually have
  // a message in them — a brand-new session from newSession() has
  // messages: [] until sendMessage() runs, so an empty draft (e.g. from
  // clicking "New Session" and then navigating away without typing) never
  // shows up as a phantom "New chat" row. It becomes a real serverChats
  // entry automatically once the first message is sent (see
  // _sendMessageImpl in useChatStore.js), so no separate cleanup is needed.
  const sessionList = useMemo(
    () => [...serverChats, ...sessions.filter((session) => !session.persisted && session.messages.length > 0)].sort((a, b) => {
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
        // No border here — ChatLayout's wrapper around this component now
        // provides the sidebar/content separation via a soft boxShadow
        // instead of a solid olive border-right (was reading as a bold,
        // blunt line running the full sidebar height).
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
          // Same reasoning as ChatLayout's boxShadow: drop the line entirely
          // when collapsed so the icon rail has no visible seams at all
          // (Gemini reference), keep it when expanded to separate the
          // logo/toggle row from the nav below.
          borderBottom: sidebarOpen ? '1px solid rgba(41, 17, 0, 0.08)' : 'none',
          flexShrink: 0,
        }}
      >
        <AnimatePresence initial={false}>
          {sidebarOpen && (
            <motion.button
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.12 }}
              onClick={() => navigate('/')}
              title="PaperPulse Home"
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <img src={logoSrc} alt="PaperPulse" style={{ height: '28px', width: 'auto', objectFit: 'contain' }} />
              <span style={{
                fontFamily: "'Newsreader', serif", fontSize: '9px', fontWeight: 700, letterSpacing: '0.04em',
                color: 'var(--color-brand-600)', background: 'var(--color-brand-50)',
                border: '1px solid var(--color-brand-100)', borderRadius: '4px', padding: '2px 5px',
              }}>
                BETA
              </span>
            </motion.button>
          )}
        </AnimatePresence>
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

      {/* Single flex skeleton for both states — the sub-blocks toggle their
          *contents* (via NavItem's label fade / conditionally showing the
          Sessions list), but the skeleton itself never unmounts/remounts.
          That's what keeps the collapse feeling like one continuous motion
          instead of a hard cut between two different layouts. */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Primary nav — reordered to match the Claude.ai sidebar reference:
            primary action (New Session) and product-level nav (My Reviews,
            Applications) live above the scrollable Recents/Sessions list. */}
        <div style={{ padding: sidebarOpen ? '10px 8px 4px' : '10px 4px 4px', flexShrink: 0 }}>
          <NavItem icon="mdi:plus" label="New Session" collapsed={!sidebarOpen} onClick={handleNewSession} badge labelWeight={600} />
          <NavItem icon="mdi:bookshelf" label="My Reviews" collapsed={!sidebarOpen} onClick={() => navigate(ROUTES.MY_REVIEWS)} labelWeight={600} />
          <NavItem icon="mdi:apps" label="Applications" collapsed={!sidebarOpen} onClick={() => setLauncherOpen(true)} labelWeight={600} />
        </div>

        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {sidebarOpen && (
            <>
              <div style={{ padding: '14px 12px 4px', fontSize: '12px', fontWeight: 600, color: 'var(--color-paper-mid)', textTransform: 'uppercase', letterSpacing: '0.06em', flexShrink: 0, borderTop: '1px solid rgba(41, 17, 0, 0.08)' }}>
                Sessions
              </div>

              {(chatsError || chatMutationError) && (
                <div style={{ margin: '0 12px 8px', padding: '8px 10px', border: '1px solid #d8b4b4', borderRadius: '4px', color: '#8c3b3b', fontSize: '12px', lineHeight: 1.4 }}>
                  {friendlyError(chatsError || chatMutationError, "Couldn't load your chats.")}
                </div>
              )}

              <div className="sidebar-scroll" style={{ flex: 1, overflowY: 'auto' }}>
                {chatsLoading && sessionList.length === 0 && (
                  <div style={{ padding: '8px 12px', fontSize: '12px', color: 'var(--color-paper-mid)' }}>
                    Loading chats...
                  </div>
                )}

                {sessionList.map((session) => {
                  const isActive = session.id === activeSessionId;
                  const isPersisted = session.persisted ?? serverChats.some((item) => item.id === session.id);
                  return (
                    <SessionRow
                      key={session.id}
                      title={session.title}
                      isActive={isActive}
                      isPersisted={isPersisted}
                      onSelect={() => handleSelectSession(session)}
                      onDelete={(event) => handleDeleteChat(event, session.id, session.title)}
                    />
                  );
                })}
              </div>
            </>
          )}
        </div>

        {/* Flat, borderless row (Gemini reference) instead of the previous
            bordered "card" button — just a top divider to separate it
            from the session list above. Pinned to the bottom of the flex
            column in both states, so it never jumps position on collapse. */}
        <div style={{ padding: '8px', borderTop: sidebarOpen ? '1px solid rgba(41, 17, 0, 0.08)' : 'none', flexShrink: 0 }}>
          <button
            onClick={() => setProfileOpen(true)}
            title={sidebarOpen ? undefined : 'Profile'}
            style={{
              width: '100%', display: 'flex', alignItems: 'center', gap: '10px',
              justifyContent: sidebarOpen ? 'flex-start' : 'center',
              padding: sidebarOpen ? '8px 6px' : '8px 0', minHeight: 44,
              background: profileOpen ? 'var(--color-paper-surface)' : 'none',
              border: 'none', borderRadius: '8px', cursor: 'pointer',
              transition: 'background-color 0.15s',
            }}
            onMouseEnter={(e) => { if (!profileOpen) e.currentTarget.style.backgroundColor = 'var(--color-paper-surface)'; }}
            onMouseLeave={(e) => { if (!profileOpen) e.currentTarget.style.backgroundColor = 'transparent'; }}
          >
            <div style={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
              background: 'var(--color-paper-surface)',
              border: '1px solid var(--color-paper-light)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: '12px', fontFamily: "'Newsreader', serif",
              color: 'var(--color-paper-mid)', overflow: 'hidden',
            }}>
              {user?.avatar_url
                ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : initials}
            </div>
            <AnimatePresence initial={false}>
              {sidebarOpen && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.12 }}
                  style={{ flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', gap: '10px' }}
                >
                  <div style={{ flex: 1, minWidth: 0, textAlign: 'left' }}>
                    <div style={{ fontSize: '14px', fontWeight: 600, fontFamily: "'Newsreader', serif", color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {user?.name || 'Account'}
                    </div>
                    <div style={{ fontSize: '12px', color: 'var(--color-paper-mid)', fontFamily: "'Newsreader', serif", whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {user?.email || ''}
                    </div>
                  </div>
                  <Icon icon="mdi:cog-outline" style={{ width: 16, height: 16, color: 'var(--color-paper-mid)', flexShrink: 0 }} />
                </motion.div>
              )}
            </AnimatePresence>
          </button>
        </div>
      </div>

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
