import { useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useThemeStore } from '@/shared/store/useThemeStore';
import BillingPanel from '@/features/billing/BillingPanel';
import UsagePanel from '@/features/billing/UsagePanel';

const THEME_ICONS = { light: 'mdi:weather-sunny', dark: 'mdi:weather-night', system: 'mdi:monitor' };

const getInitials = (user) =>
  user?.name
    ? user.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : (user?.email?.[0]?.toUpperCase() ?? '?');

const overlayStyle = {
  position: 'fixed', inset: 0,
  background: 'rgba(41,17,0,0.35)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  zIndex: 10000,
};

// Matches LoginPage.jsx's card treatment: paper-surface bg, barely-there
// rgba border, 16px radius, two-layer soft shadow — instead of the old flat
// paper-bg + 4px radius + single hard shadow, which read as a different,
// older UI style than the rest of the app now uses.
const cardStyle = {
  background: 'var(--color-paper-surface)',
  border: '1px solid rgba(41, 17, 0, 0.08)',
  borderRadius: '16px',
  boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 8px 24px rgba(41, 17, 0, 0.12)',
  width: '640px',
  maxWidth: '92vw',
  maxHeight: '82vh',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};

// Same small-caps label treatment as LoginPage.jsx's labelStyle.
const sectionLabelStyle = {
  fontSize: 11, fontWeight: 600, color: 'var(--color-paper-mid)',
  textTransform: 'uppercase', letterSpacing: '0.08em',
  fontFamily: "'Lora', 'Newsreader', serif", marginBottom: 10,
};

const TABS = [
  { key: 'general', label: 'General' },
  { key: 'billing', label: 'Billing' },
  { key: 'usage', label: 'Usage' },
];

// Circular now (was a square 4px-radius tile) to match the avatar used
// everywhere else in the app — Sidebar.jsx's bottom profile row, the app
// launcher, etc. all switched to circular earlier; this was the one place
// still showing the old square shape for the same user.
const AvatarTile = ({ user, initials, size = 44, fontSize = 16 }) => (
  <div style={{
    width: size, height: size, borderRadius: '50%', flexShrink: 0,
    background: 'var(--color-paper-bg)',
    border: '1px solid rgba(41, 17, 0, 0.12)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden',
  }}>
    {user?.avatar_url
      ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      : <span style={{
          fontFamily: "'Fraunces', 'Newsreader', serif",
          fontSize, fontWeight: 600,
          color: 'var(--color-paper-dark)',
          lineHeight: 1,
        }}>{initials}</span>
    }
  </div>
);

const ProfileModal = ({ isOpen, onClose, user, onLogout }) => {
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const [activeTab, setActiveTab] = useState('general');
  const isAdmin = user?.role === 'admin';
  const initials = getInitials(user);

  // Reset to the General tab whenever the modal re-opens — adjusted during
  // render (no effect needed for derived state), same pattern as
  // SaveReviewModal.jsx / AppLauncherModal.jsx.
  const [prevIsOpen, setPrevIsOpen] = useState(isOpen);
  if (isOpen !== prevIsOpen) {
    setPrevIsOpen(isOpen);
    if (isOpen) setActiveTab('general');
  }

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          style={overlayStyle}
          onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 8 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 8 }}
            transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
            style={cardStyle}
          >
            {/* Header */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 12,
              padding: '20px 24px', borderBottom: '1px solid rgba(41, 17, 0, 0.08)', flexShrink: 0,
            }}>
              <AvatarTile user={user} initials={initials} size={44} fontSize={16} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{
                  fontSize: 15, fontFamily: "'Fraunces', 'Newsreader', serif",
                  color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  {user?.name || 'Account'}
                  {isAdmin && (
                    <span style={{
                      padding: '1px 7px',
                      border: '1px solid var(--color-brand-100)',
                      borderRadius: 4,
                      background: 'var(--color-brand-50)',
                      color: 'var(--color-brand-600)',
                      fontSize: 9, fontFamily: "'Lora', 'Newsreader', serif",
                      fontWeight: 600, letterSpacing: '0.08em',
                      textTransform: 'uppercase', verticalAlign: 'middle',
                    }}>
                      Admin
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: 'var(--color-paper-mid)', fontFamily: "'Newsreader', serif", whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.email || ''}
                </div>
              </div>
              <button
                onClick={onClose}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-mid)', padding: 4, display: 'flex' }}
                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-paper-dark)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-paper-mid)'; }}
              >
                <Icon icon="mdi:close" style={{ width: 20, height: 20 }} />
              </button>
            </div>

            {/* Tab bar — active underline now uses the brand accent color
                (same as links/focus states on the login card) instead of
                paper-dark, so "selected" reads consistently with the rest
                of the app's accent language. */}
            <div style={{ display: 'flex', gap: 4, padding: '10px 24px 0', borderBottom: '1px solid rgba(41, 17, 0, 0.08)', flexShrink: 0 }}>
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: '8px 14px', border: 'none', background: 'none', cursor: 'pointer',
                    fontFamily: "'Newsreader', serif", fontSize: 14,
                    color: activeTab === tab.key ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
                    fontWeight: activeTab === tab.key ? 600 : 400,
                    borderBottom: activeTab === tab.key ? '2px solid var(--color-brand-500)' : '2px solid transparent',
                    marginBottom: '-1px',
                    transition: 'color 0.12s',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="themed-scroll" style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
              {activeTab === 'general' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  <div>
                    <div style={sectionLabelStyle}>
                      Profile
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <AvatarTile user={user} initials={initials} size={36} fontSize={13} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 14, color: 'var(--color-paper-dark)', fontFamily: "'Newsreader', serif" }}>
                          {user?.name || 'Account'}
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--color-paper-mid)', fontFamily: "'Newsreader', serif" }}>
                          {user?.email}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <div style={sectionLabelStyle}>
                      Appearance
                    </div>
                    {/* Border/fill now brand-500 + brand-50 for the selected
                        option (was paper-dark + paper-surface) — same accent
                        color as the tab underline above, so "this one is
                        picked" reads the same way everywhere in the modal. */}
                    <div style={{ display: 'flex', gap: 6 }}>
                      {['light', 'dark', 'system'].map((t) => (
                        <button
                          key={t}
                          onClick={() => setTheme(t)}
                          title={t}
                          style={{
                            padding: '10px 14px',
                            border: '1px solid',
                            borderColor: theme === t ? 'var(--color-brand-500)' : 'rgba(41, 17, 0, 0.12)',
                            borderRadius: 8,
                            background: theme === t ? 'var(--color-brand-50)' : 'transparent',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            transition: 'all 0.12s',
                          }}
                        >
                          <Icon
                            icon={THEME_ICONS[t]}
                            style={{ fontSize: 18, color: theme === t ? 'var(--color-brand-600)' : 'var(--color-paper-mid)' }}
                          />
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'billing' && <BillingPanel />}
              {activeTab === 'usage' && <UsagePanel />}
            </div>

            {/* Footer — sign out restyled as a bordered secondary button
                (same rgba(41,17,0,0.12) border + 10px radius as the "Sign in
                with Google" button on LoginPage.jsx) instead of a plain
                borderless text link, so it reads as a deliberate action
                rather than incidental footer text. */}
            <div style={{ padding: '12px 24px', borderTop: '1px solid rgba(41, 17, 0, 0.08)', flexShrink: 0 }}>
              <button
                onClick={onLogout}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '9px 14px', border: '1px solid rgba(41, 17, 0, 0.12)', borderRadius: 10,
                  background: 'var(--color-paper-bg)', cursor: 'pointer',
                  // Red (same #c0392b used for Delete elsewhere, e.g.
                  // ReviewDetailPage.jsx) — signals this ends the session,
                  // distinct from the brand-green used for regular actions.
                  color: '#c0392b',
                  fontFamily: "'Lora', 'Newsreader', serif", fontSize: 14, fontWeight: 600,
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(192, 57, 43, 0.08)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'var(--color-paper-bg)')}
              >
                <Icon icon="mdi:logout" style={{ fontSize: 17 }} />
                <span>Sign out</span>
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body
  );
};

export default ProfileModal;
