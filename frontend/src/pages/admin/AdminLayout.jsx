import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { NavLink, useNavigate, useLocation, Outlet } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { ROUTES } from '@/shared/constant/routes';

const NAV = [
  { to: ROUTES.ADMIN_DASHBOARD,  label: 'Dashboard',  icon: 'mdi:view-dashboard-outline' },
  { to: ROUTES.ADMIN_USERS,      label: 'Users',      icon: 'mdi:account-group-outline' },
  { to: ROUTES.ADMIN_USAGE,      label: 'Usage',      icon: 'mdi:gauge' },
  { to: ROUTES.ADMIN_COMMUNITY,  label: 'Community',  icon: 'mdi:comment-check-outline' },
  { to: ROUTES.ADMIN_REVENUE,    label: 'Revenue',    icon: 'mdi:cash-multiple' },
  {
    key: 'testing',
    label: 'Testing',
    icon: 'mdi:flask-outline',
    children: [
      { to: ROUTES.ADMIN_TESTING_LITERATURE_REVIEW, label: 'Literature Review' },
      { to: ROUTES.ADMIN_TESTING_RESEARCH_GAP,       label: 'Research Gap', badge: 'Update' },
    ],
  },
];

const THEME_ICONS = { light: 'mdi:weather-sunny', dark: 'mdi:weather-night', system: 'mdi:monitor' };

const getInitials = (user) =>
  user?.name
    ? user.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : (user?.email?.[0]?.toUpperCase() ?? '?');

// ── Profile popup (Facebook-style) ───────────────────────────────────────────

function MenuItem({ icon, label, onClick, danger }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: '100%', display: 'flex', alignItems: 'center', gap: 12,
        padding: '10px 12px', border: 'none', borderRadius: 8,
        background: 'transparent', cursor: 'pointer', textAlign: 'left',
        color: danger ? '#e53e3e' : 'var(--color-paper-dark)',
        fontSize: 14, transition: 'background 0.12s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = danger ? '#fff5f5' : 'var(--color-paper-surface)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <div style={{
        width: 34, height: 34, borderRadius: '50%', flexShrink: 0,
        background: danger ? '#fed7d7' : 'var(--color-paper-bg)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Icon icon={icon} style={{ fontSize: 17, color: danger ? '#e53e3e' : 'var(--color-paper-mid)' }} />
      </div>
      <span style={{ fontWeight: 500 }}>{label}</span>
    </button>
  );
}

function ProfilePopup({ user, onClose, popupRef }) {
  const navigate = useNavigate();
  const logout   = useAuthStore((s) => s.logout);
  const theme    = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const initials = getInitials(user);

  const go = (path) => { onClose(); navigate(path); };
  const handleLogout = async () => { onClose(); await logout(); navigate(ROUTES.LOGIN); };

  return (
    <motion.div
      ref={popupRef}
      initial={{ opacity: 0, scale: 0.95, y: 8 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95, y: 8 }}
      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
      style={{
        background: 'var(--color-paper-bg)',
        border: '1px solid var(--color-paper-light)',
        borderRadius: 12,
        boxShadow: '0 8px 40px rgba(0,0,0,0.18)',
        width: 280, overflow: 'hidden',
      }}
    >
      {/* User card */}
      <div style={{
        padding: '16px', borderBottom: '1px solid var(--color-paper-surface)',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: '50%', flexShrink: 0,
          background: 'var(--color-brand-100)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 16, fontWeight: 700, color: 'var(--color-brand-600)', overflow: 'hidden',
        }}>
          {user?.avatar_url
            ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : initials}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-paper-dark)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {user?.name || 'Admin'}
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-paper-mid)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginTop: 2 }}>
            {user?.email || ''}
          </div>
          <span style={{
            display: 'inline-block', marginTop: 4,
            padding: '1px 8px', borderRadius: 20,
            background: 'var(--color-brand-50)', color: 'var(--color-brand-600)',
            fontSize: 10, fontWeight: 700,
          }}>
            Admin
          </span>
        </div>
      </div>

      {/* Nav items */}
      <div style={{ padding: '8px' }}>
        <MenuItem icon="mdi:home-outline"    label="Go to App" onClick={() => go(ROUTES.APP)} />
        <MenuItem icon="mdi:flask-outline"   label="Research"  onClick={() => go(ROUTES.RESEARCH)} />
      </div>

      {/* Appearance */}
      <div style={{ padding: '8px', borderTop: '1px solid var(--color-paper-surface)' }}>
        <div style={{ padding: '4px 12px 8px', fontSize: 11, fontWeight: 600, color: 'var(--color-paper-light)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
          Appearance
        </div>
        <div style={{ display: 'flex', gap: 4, padding: '0 4px' }}>
          {['light', 'dark', 'system'].map((t) => (
            <button key={t} onClick={() => setTheme(t)} title={t} style={{
              flex: 1, padding: '8px 4px', border: '1px solid',
              borderColor: theme === t ? 'var(--color-brand-500)' : 'var(--color-paper-light)',
              borderRadius: 8,
              background: theme === t ? 'var(--color-brand-50)' : 'transparent',
              cursor: 'pointer', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
              transition: 'all 0.12s',
            }}>
              <Icon icon={THEME_ICONS[t]} style={{ fontSize: 16, color: theme === t ? 'var(--color-brand-500)' : 'var(--color-paper-mid)' }} />
              <span style={{ fontSize: 10, color: theme === t ? 'var(--color-brand-600)' : 'var(--color-paper-mid)', textTransform: 'capitalize', fontWeight: theme === t ? 600 : 400 }}>
                {t}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Logout */}
      <div style={{ padding: '8px', borderTop: '1px solid var(--color-paper-surface)' }}>
        <MenuItem icon="mdi:logout" label="Sign out" onClick={handleLogout} danger />
      </div>
    </motion.div>
  );
}

// ── Main layout ───────────────────────────────────────────────────────────────

export default function AdminLayout() {
  const user     = useAuthStore((s) => s.user);
  const navigate = useNavigate();
  const location = useLocation();
  const theme    = useThemeStore((s) => s.theme);

  const [collapsed, setCollapsed] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [popupPos, setPopupPos]   = useState({ bottom: 0, left: 0 });

  // Auto-expand whichever nav group contains the current route.
  const [expandedGroup, setExpandedGroup] = useState(() => {
    const group = NAV.find((item) => item.children?.some((c) => location.pathname.startsWith(c.to)));
    return group?.key ?? null;
  });

  const profileBtnRef = useRef(null);
  const popupRef      = useRef(null);

  const isDark = theme === 'dark' || (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  const logoSrc = isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png';
  const initials = getInitials(user);

  const openProfile = () => {
    if (!profileOpen && profileBtnRef.current) {
      const rect = profileBtnRef.current.getBoundingClientRect();
      setPopupPos({ bottom: window.innerHeight - rect.top + 8, left: collapsed ? rect.right + 8 : rect.left });
    }
    setProfileOpen((v) => !v);
  };

  useEffect(() => {
    if (!profileOpen) return;
    const handler = (e) => {
      if (!profileBtnRef.current?.contains(e.target) && !popupRef.current?.contains(e.target)) {
        setProfileOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [profileOpen]);

  const W = collapsed ? 56 : 220;

  return (
    <div style={{ display: 'flex', height: '100vh', background: 'var(--color-paper-bg)' }}>

      {/* Sidebar */}
      <motion.aside
        initial={{ width: W, opacity: 0, x: -20 }}
        animate={{ width: W, opacity: 1, x: 0 }}
        transition={{ type: 'spring', stiffness: 260, damping: 28 }}
        style={{
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          background: 'var(--color-paper-surface)',
          borderRight: '1px solid var(--color-paper-light)',
          overflow: 'hidden',
        }}
      >
        {/* Header — logo + toggle */}
        <div style={{
          height: 56, flexShrink: 0,
          display: 'flex', alignItems: 'center',
          justifyContent: collapsed ? 'center' : 'space-between',
          padding: collapsed ? 0 : '0 12px 0 16px',
          borderBottom: '1px solid var(--color-paper-light)',
        }}>
          {!collapsed && (
            <motion.button
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.1 }}
              onClick={() => navigate(ROUTES.HOME)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, display: 'flex', alignItems: 'center' }}
            >
              <img src={logoSrc} alt="PaperPulse" style={{ height: 26, width: 'auto', objectFit: 'contain' }} />
            </motion.button>
          )}

          <button
            onClick={() => setCollapsed((v) => !v)}
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            style={{
              background: 'none', border: 'none', cursor: 'pointer', padding: 4,
              borderRadius: 6, color: 'var(--color-paper-mid)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'background 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.background = 'var(--color-brand-50)'}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            <Icon icon={collapsed ? 'mdi:chevron-right' : 'mdi:chevron-left'} style={{ fontSize: 18 }} />
          </button>
        </div>

        {/* Nav */}
        <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: 2 }}>
          {NAV.map((item, i) => {
            const isGroup = Array.isArray(item.children);
            const isGroupActive = isGroup && item.children.some((c) => location.pathname.startsWith(c.to));
            const isExpanded = isGroup && expandedGroup === item.key;

            if (!isGroup) {
              return (
                <motion.div
                  key={item.to}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.08 + i * 0.05, type: 'spring', stiffness: 300, damping: 28 }}
                >
                  <NavLink
                    to={item.to}
                    title={collapsed ? item.label : undefined}
                    style={({ isActive }) => ({
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: collapsed ? 'center' : 'flex-start',
                      gap: 10,
                      padding: collapsed ? '10px' : '9px 12px',
                      borderRadius: 8,
                      textDecoration: 'none',
                      fontSize: 14,
                      fontWeight: isActive ? 600 : 400,
                      color: isActive ? 'var(--color-brand-600)' : 'var(--color-paper-mid)',
                      background: isActive ? 'var(--color-brand-50)' : 'transparent',
                      transition: 'all 0.15s',
                    })}
                  >
                    {({ isActive }) => (
                      <>
                        <Icon
                          icon={item.icon}
                          style={{ fontSize: 19, color: isActive ? 'var(--color-brand-500)' : 'var(--color-paper-light)', flexShrink: 0 }}
                        />
                        <AnimatePresence>
                          {!collapsed && (
                            <motion.span
                              key="label"
                              initial={{ opacity: 0, width: 0 }}
                              animate={{ opacity: 1, width: 'auto' }}
                              exit={{ opacity: 0, width: 0 }}
                              transition={{ duration: 0.15 }}
                              style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}
                            >
                              {item.label}
                            </motion.span>
                          )}
                        </AnimatePresence>
                        {!collapsed && isActive && (
                          <motion.div
                            layoutId="admin-nav-dot"
                            style={{ marginLeft: 'auto', width: 5, height: 5, borderRadius: '50%', background: 'var(--color-brand-500)', flexShrink: 0 }}
                          />
                        )}
                      </>
                    )}
                  </NavLink>
                </motion.div>
              );
            }

            // ── Dropdown group (e.g. "Testing") ──────────────────────────────
            return (
              <motion.div
                key={item.key}
                initial={{ opacity: 0, x: -12 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: 0.08 + i * 0.05, type: 'spring', stiffness: 300, damping: 28 }}
              >
                <button
                  onClick={() => {
                    if (collapsed) setCollapsed(false);
                    setExpandedGroup((g) => (g === item.key ? null : item.key));
                  }}
                  title={collapsed ? item.label : undefined}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: collapsed ? 'center' : 'flex-start',
                    gap: 10,
                    padding: collapsed ? '10px' : '9px 12px',
                    borderRadius: 8,
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: 14,
                    fontWeight: isGroupActive ? 600 : 400,
                    color: isGroupActive ? 'var(--color-brand-600)' : 'var(--color-paper-mid)',
                    background: isGroupActive ? 'var(--color-brand-50)' : 'transparent',
                    transition: 'all 0.15s',
                  }}
                >
                  <Icon
                    icon={item.icon}
                    style={{ fontSize: 19, color: isGroupActive ? 'var(--color-brand-500)' : 'var(--color-paper-light)', flexShrink: 0 }}
                  />
                  {!collapsed && (
                    <>
                      <span style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>{item.label}</span>
                      <Icon
                        icon="mdi:chevron-down"
                        style={{
                          marginLeft: 'auto', fontSize: 16, flexShrink: 0,
                          color: 'var(--color-paper-light)',
                          transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                          transition: 'transform 0.15s',
                        }}
                      />
                    </>
                  )}
                </button>

                <AnimatePresence initial={false}>
                  {isExpanded && !collapsed && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.18 }}
                      style={{ overflow: 'hidden' }}
                    >
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 1, paddingLeft: 14, marginTop: 2 }}>
                        {item.children.map((child) => (
                          <NavLink
                            key={child.to}
                            to={child.to}
                            style={({ isActive }) => ({
                              display: 'flex',
                              alignItems: 'center',
                              gap: 8,
                              padding: '7px 12px',
                              borderRadius: 8,
                              textDecoration: 'none',
                              fontSize: 13,
                              fontWeight: isActive ? 600 : 400,
                              color: isActive ? 'var(--color-brand-600)' : 'var(--color-paper-mid)',
                              background: isActive ? 'var(--color-brand-50)' : 'transparent',
                              borderLeft: '1px solid var(--color-paper-light)',
                            })}
                          >
                            <span style={{
                              width: 4, height: 4, borderRadius: '50%', flexShrink: 0,
                              background: 'currentColor', opacity: 0.6,
                            }} />
                            <span style={{ overflow: 'hidden', whiteSpace: 'nowrap' }}>{child.label}</span>
                            {child.badge && (
                              <span style={{
                                marginLeft: 'auto', fontSize: 9, fontWeight: 700, padding: '1px 6px',
                                borderRadius: 20, background: 'var(--color-brand-50)', color: 'var(--color-brand-500)',
                                textTransform: 'uppercase', letterSpacing: '0.03em', flexShrink: 0,
                              }}>
                                {child.badge}
                              </span>
                            )}
                          </NavLink>
                        ))}
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </nav>

        {/* Profile trigger — bottom */}
        <div style={{ padding: '8px', borderTop: '1px solid var(--color-paper-light)', flexShrink: 0 }}>
          <button
            ref={profileBtnRef}
            onClick={openProfile}
            title={collapsed ? (user?.name || 'Account') : undefined}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: collapsed ? '10px' : '9px 10px',
              justifyContent: collapsed ? 'center' : 'flex-start',
              border: '1px solid',
              borderColor: profileOpen ? 'var(--color-brand-500)' : 'var(--color-paper-light)',
              borderRadius: 8,
              background: profileOpen ? 'var(--color-brand-50)' : 'transparent',
              cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {/* Avatar */}
            <div style={{
              width: 28, height: 28, borderRadius: '50%', flexShrink: 0,
              background: 'var(--color-brand-100)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 11, fontWeight: 700, color: 'var(--color-brand-600)', overflow: 'hidden',
            }}>
              {user?.avatar_url
                ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : initials}
            </div>

            <AnimatePresence>
              {!collapsed && (
                <motion.div
                  key="profile-info"
                  initial={{ opacity: 0, width: 0 }}
                  animate={{ opacity: 1, width: 'auto' }}
                  exit={{ opacity: 0, width: 0 }}
                  transition={{ duration: 0.15 }}
                  style={{ flex: 1, minWidth: 0, overflow: 'hidden', textAlign: 'left' }}
                >
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-paper-dark)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {user?.name || 'Admin'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--color-paper-mid)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {user?.email || ''}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {!collapsed && (
              <Icon icon="mdi:dots-horizontal" style={{ fontSize: 16, color: 'var(--color-paper-light)', flexShrink: 0 }} />
            )}
          </button>
        </div>
      </motion.aside>

      {/* Main content */}
      <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', padding: '32px 36px' }}>
        <Outlet />
      </main>

      {/* Profile popup portal */}
      {createPortal(
        <AnimatePresence>
          {profileOpen && (
            <div style={{ position: 'fixed', bottom: popupPos.bottom, left: popupPos.left, zIndex: 9999 }}>
              <ProfilePopup
                user={user}
                onClose={() => setProfileOpen(false)}
                popupRef={popupRef}
              />
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </div>
  );
}
