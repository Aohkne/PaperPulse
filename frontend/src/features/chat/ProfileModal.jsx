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

const cardStyle = {
  background: 'var(--color-paper-bg)',
  border: '1px solid var(--color-paper-surface)',
  borderRadius: '4px',
  boxShadow: '0 8px 32px rgba(41,17,0,0.12)',
  width: '640px',
  maxWidth: '92vw',
  maxHeight: '82vh',
  display: 'flex',
  flexDirection: 'column',
  overflow: 'hidden',
};

const TABS = [
  { key: 'general', label: 'General' },
  { key: 'billing', label: 'Billing' },
  { key: 'usage', label: 'Usage' },
];

/* Square avatar tile — paper aesthetic, no circle */
const AvatarTile = ({ user, initials, size = 44, fontSize = 16 }) => (
  <div style={{
    width: size, height: size, borderRadius: 4, flexShrink: 0,
    background: 'var(--color-paper-surface)',
    border: '1px solid var(--color-paper-light)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    overflow: 'hidden',
  }}>
    {user?.avatar_url
      ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
      : <span style={{
          fontFamily: "'Inknut Antiqua', Georgia, serif",
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
              padding: '20px 24px', borderBottom: '1px solid var(--color-paper-surface)', flexShrink: 0,
            }}>
              <AvatarTile user={user} initials={initials} size={44} fontSize={16} />
              <div style={{ minWidth: 0, flex: 1 }}>
                <div style={{
                  fontSize: 15, fontFamily: "'Inknut Antiqua', Georgia, serif",
                  color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                  display: 'flex', alignItems: 'center', gap: 8,
                }}>
                  {user?.name || 'Account'}
                  {isAdmin && (
                    <span style={{
                      padding: '1px 7px',
                      border: '1px solid var(--color-paper-light)',
                      borderRadius: 2,
                      background: 'transparent',
                      color: 'var(--color-paper-light)',
                      fontSize: 9, fontFamily: 'Georgia, serif',
                      fontWeight: 600, letterSpacing: '0.08em',
                      textTransform: 'uppercase', verticalAlign: 'middle',
                    }}>
                      Admin
                    </span>
                  )}
                </div>
                <div style={{ fontSize: 13, color: 'var(--color-paper-mid)', fontFamily: 'Georgia, serif', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user?.email || ''}
                </div>
              </div>
              <button
                onClick={onClose}
                style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--color-paper-light)', padding: 4, display: 'flex' }}
                onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-paper-dark)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-paper-light)'; }}
              >
                <Icon icon="mdi:close" style={{ width: 20, height: 20 }} />
              </button>
            </div>

            {/* Tab bar */}
            <div style={{ display: 'flex', gap: 4, padding: '10px 24px 0', borderBottom: '1px solid var(--color-paper-surface)', flexShrink: 0 }}>
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  style={{
                    padding: '8px 14px', border: 'none', background: 'none', cursor: 'pointer',
                    fontFamily: 'Georgia, serif', fontSize: 14,
                    color: activeTab === tab.key ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
                    fontWeight: activeTab === tab.key ? 600 : 400,
                    borderBottom: activeTab === tab.key ? '2px solid var(--color-paper-dark)' : '2px solid transparent',
                    marginBottom: '-1px',
                    transition: 'color 0.12s',
                  }}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
              {activeTab === 'general' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-paper-light)', textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: 'Georgia, serif', marginBottom: 10 }}>
                      Profile
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <AvatarTile user={user} initials={initials} size={36} fontSize={13} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: 14, color: 'var(--color-paper-dark)', fontFamily: 'Georgia, serif' }}>
                          {user?.name || 'Account'}
                        </div>
                        <div style={{ fontSize: 13, color: 'var(--color-paper-mid)', fontFamily: 'Georgia, serif' }}>
                          {user?.email}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--color-paper-light)', textTransform: 'uppercase', letterSpacing: '0.08em', fontFamily: 'Georgia, serif', marginBottom: 10 }}>
                      Appearance
                    </div>
                    <div style={{ display: 'flex', gap: 6 }}>
                      {['light', 'dark', 'system'].map((t) => (
                        <button
                          key={t}
                          onClick={() => setTheme(t)}
                          title={t}
                          style={{
                            padding: '10px 14px',
                            border: '1px solid',
                            borderColor: theme === t ? 'var(--color-paper-dark)' : 'var(--color-paper-surface)',
                            borderRadius: 4,
                            background: theme === t ? 'var(--color-paper-surface)' : 'transparent',
                            cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                            transition: 'all 0.12s',
                          }}
                        >
                          <Icon
                            icon={THEME_ICONS[t]}
                            style={{ fontSize: 18, color: theme === t ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)' }}
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

            {/* Footer — persistent sign out */}
            <div style={{ padding: '12px 24px', borderTop: '1px solid var(--color-paper-surface)', flexShrink: 0 }}>
              <button
                onClick={onLogout}
                style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 12px', border: 'none', borderRadius: 4,
                  background: 'transparent', cursor: 'pointer',
                  color: 'var(--color-brand-600)',
                  fontFamily: 'Georgia, serif', fontSize: 14,
                  transition: 'background 0.12s',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = 'var(--color-brand-50)')}
                onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
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
