import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { ROUTES } from '@/shared/constant/routes';
import { useIsMobile } from '@/shared/hooks/useIsMobile';

const useIsScrolled = (threshold = 8) => {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > threshold);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, [threshold]);
  return scrolled;
};

const THEME_ICONS = { light: 'mdi:weather-sunny', dark: 'mdi:weather-night', system: 'mdi:monitor' };

const getInitials = (user) =>
  user?.name
    ? user.name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase()
    : (user?.email?.[0]?.toUpperCase() ?? '?');

const NAV_LINKS = [
  { label: 'Home',      to: ROUTES.HOME      },
  { label: 'Community', to: ROUTES.COMMUNITY },
];

// â”€â”€ Avatar dropdown (auth + profile menu) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const AvatarMenu = ({ user, onClose, menuRef, isMobile }) => {
  const navigate = useNavigate();
  const logout = useAuthStore((s) => s.logout);
  const theme = useThemeStore((s) => s.theme);
  const setTheme = useThemeStore((s) => s.setTheme);
  const isAdmin = user?.role === 'admin';
  const initials = getInitials(user);

  const go = (path) => { onClose(); navigate(path); };

  const handleLogout = async () => {
    onClose();
    await logout();
    navigate(ROUTES.LOGIN);
  };

  const menuItem = (icon, label, onClick, danger = false) => (
    <button
      key={label}
      onClick={onClick}
      style={{
        width: '100%',
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 10px',
        border: 'none',
        borderRadius: 2,
        background: 'transparent',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'background 0.12s',
      }}
      onMouseEnter={e => e.currentTarget.style.background = 'var(--color-paper-surface)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <Icon
        icon={icon}
        // #c0392b — same red used for "Sign out" in the chat UI's
        // ProfileModal.jsx and for "Delete" elsewhere (ReviewDetailPage,
        // Sidebar's kebab menu). This was wrongly using brand-600 (green),
        // which made "Sign out" look like a regular/safe action.
        style={{ fontSize: 16, color: danger ? '#c0392b' : 'var(--color-paper-mid)', flexShrink: 0 }}
      />
      <span style={{
        fontFamily: "'Newsreader', serif", fontSize: 14,
        color: danger ? '#c0392b' : 'var(--color-paper-dark)',
        fontWeight: 500,
      }}>
        {label}
      </span>
    </button>
  );

  return (
    <motion.div
      ref={menuRef}
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -6 }}
      transition={{ duration: 0.18, ease: [0.22, 1, 0.36, 1] }}
      style={{
        // Login-card convention (paper-surface bg + hairline border + 16px
        // radius + soft double-layer shadow) — same treatment already used
        // for the notifications dropdown, so every popover panel shares one
        // look instead of this one keeping its older sharp-corner style.
        background: 'var(--color-paper-surface)',
        border: '1px solid rgba(41, 17, 0, 0.08)',
        borderRadius: 16,
        boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 8px 24px rgba(41, 17, 0, 0.12)',
        width: isMobile ? 'min(256px, calc(100vw - 24px))' : 256,
        overflow: 'hidden',
        transformOrigin: 'top right',
      }}
    >
      {/* User card */}
      <div style={{
        padding: '14px 16px',
        borderBottom: '1px solid rgba(41, 17, 0, 0.08)',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          // Circular, matching the chat-UI avatar shape (Sidebar profile
          // row / round icon-button convention) instead of this menu's old
          // rounded-square swatch.
          width: 40, height: 40, borderRadius: '50%', flexShrink: 0,
          background: 'var(--color-paper-surface)',
          border: '1px solid var(--color-paper-light)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontFamily: 'var(--font-inknut)', fontSize: 14, fontWeight: 500,
          color: 'var(--color-paper-dark)', overflow: 'hidden',
        }}>
          {user?.avatar_url
            ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            : initials}
        </div>
        <div style={{ minWidth: 0 }}>
          <div style={{
            fontFamily: "'Newsreader', serif", fontSize: 14, fontWeight: 600,
            color: 'var(--color-paper-dark)', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis',
          }}>
            {user?.name || 'Account'}
          </div>
          <div style={{
            fontFamily: "'Newsreader', serif", fontSize: 12,
            color: 'var(--color-paper-mid)', whiteSpace: 'nowrap',
            overflow: 'hidden', textOverflow: 'ellipsis', marginTop: 2,
          }}>
            {user?.email || ''}
          </div>
          {isAdmin && (
            <span style={{
              display: 'inline-block', marginTop: 5,
              padding: '1px 7px', borderRadius: 2,
              border: '1px solid var(--color-paper-light)',
              fontFamily: "'Newsreader', serif",
              fontSize: 10, fontWeight: 700, letterSpacing: '0.06em',
              color: 'var(--color-paper-mid)', textTransform: 'uppercase',
            }}>
              Admin
            </span>
          )}
        </div>
      </div>

      {/* Menu items */}
      <div style={{ padding: '6px' }}>
        {menuItem('mdi:home-outline', 'Go to App', () => go(ROUTES.APP))}
        {menuItem('mdi:bookshelf', 'My Reviews', () => go(ROUTES.MY_REVIEWS))}
        {isAdmin && menuItem('mdi:view-dashboard-outline', 'Dashboard', () => go(ROUTES.ADMIN_DASHBOARD))}
      </div>

      {/* Appearance */}
      <div style={{ padding: '6px', borderTop: '1px solid rgba(41, 17, 0, 0.08)' }}>
        <div style={{
          padding: '4px 10px 8px',
          fontFamily: "'Newsreader', serif", fontSize: 10, fontWeight: 700,
          color: 'var(--color-paper-mid)', textTransform: 'uppercase', letterSpacing: '0.08em',
        }}>
          Appearance
        </div>
        <div style={{ display: 'flex', gap: 4, padding: '0 2px' }}>
          {['light', 'dark', 'system'].map((t) => (
            <button
              key={t}
              onClick={() => setTheme(t)}
              title={t}
              style={{
                flex: 1, padding: '8px 4px',
                border: '1px solid',
                borderColor: theme === t ? 'var(--color-paper-dark)' : 'rgba(41, 17, 0, 0.08)',
                borderRadius: 2,
                background: theme === t ? 'var(--color-paper-surface)' : 'transparent',
                cursor: 'pointer',
                display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 4,
                transition: 'all 0.12s',
              }}
            >
              <Icon icon={THEME_ICONS[t]} style={{ fontSize: 15, color: theme === t ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)' }} />
              <span style={{
                fontFamily: "'Newsreader', serif", fontSize: 10,
                color: theme === t ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
                textTransform: 'capitalize', fontWeight: theme === t ? 600 : 400,
              }}>
                {t}
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Sign out */}
      <div style={{ padding: '6px', borderTop: '1px solid rgba(41, 17, 0, 0.08)' }}>
        {menuItem('mdi:logout', 'Sign out', handleLogout, true)}
      </div>
    </motion.div>
  );
};

// â”€â”€ Header â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
const SiteHeader = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);
  const scrolled = useIsScrolled();
  const isMobile = useIsMobile(640);

  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState({ top: 0, right: 0 });
  const avatarBtnRef = useRef(null);
  const menuRef = useRef(null);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  // --color-landing-tone-1 to match the Landing hero's starting tone —
  // paper-surface (light) in light mode, paper-bg (dark) in dark mode, per
  // theme (see index.css). The scrolled/blurred rgba below is just that same
  // color pre-mixed with its own opacity (CSS can't blur a var() directly),
  // recomputed per branch so it still matches once glass-blur kicks in.
  const navBg = scrolled
    ? (isDark ? 'rgba(26,26,24,0.78)' : 'rgba(255,252,240,0.78)')
    : 'var(--color-landing-tone-1)';

  const openMenu = () => {
    if (!menuOpen && avatarBtnRef.current) {
      const rect = avatarBtnRef.current.getBoundingClientRect();
      setMenuPos({ top: rect.bottom + 8, right: window.innerWidth - rect.right });
    }
    setMenuOpen((v) => !v);
  };

  useEffect(() => {
    if (!menuOpen) return;
    const handler = (e) => {
      if (!avatarBtnRef.current?.contains(e.target) && !menuRef.current?.contains(e.target)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  const initials = getInitials(user);

  return (
    <>
      <motion.nav
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: 'easeOut' }}
        style={{
          position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
          background: navBg,
          backdropFilter: scrolled ? 'blur(12px)' : 'none',
          WebkitBackdropFilter: scrolled ? 'blur(12px)' : 'none',
          borderBottom: scrolled ? 'none' : '1px solid rgba(41, 17, 0, 0.08)',
          boxShadow: scrolled ? '0 1px 0 rgba(41, 17, 0, 0.08), 0 10px 30px rgba(41,17,0,0.06)' : 'none',
          padding: isMobile ? '10px 16px' : '12px 40px',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          gap: 8,
          transition: 'background 0.2s, box-shadow 0.2s',
        }}
      >
        {/* Logo */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer', flexShrink: 0 }} onClick={() => navigate(ROUTES.HOME)}>
          <img
            src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
            alt="PaperPulse"
            style={{ height: isMobile ? 26 : 32, width: 'auto' }}
          />
          {!isMobile && (
            <span style={{
              fontFamily: "'Newsreader', serif", fontSize: 10, fontWeight: 700, letterSpacing: '0.04em',
              color: 'var(--color-brand-600)', background: 'var(--color-brand-50)',
              border: '1px solid var(--color-brand-100)', borderRadius: 4, padding: '2px 6px',
            }}>
              BETA
            </span>
          )}
        </div>

        {/* Center nav links */}
        <div style={{ display: 'flex', gap: isMobile ? 14 : 32, alignItems: 'center' }}>
          {NAV_LINKS.map((item) => {
            const isActive = location.pathname === item.to;
            return (
              <button
                key={item.to}
                onClick={() => navigate(item.to)}
                style={{
                  position: 'relative',
                  background: 'none', border: 'none', cursor: 'pointer', padding: isMobile ? '6px 0' : '4px 0',
                  fontFamily: "'Newsreader', serif", fontSize: isMobile ? 13 : 15,
                  color: isActive ? 'var(--color-paper-dark)' : 'var(--color-paper-mid)',
                  fontWeight: isActive ? 600 : 400,
                  transition: 'color 0.15s',
                }}
              >
                {item.label}
                {isActive && (
                  <motion.div
                    layoutId="nav-underline"
                    transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                    style={{
                      position: 'absolute', left: 0, right: 0, bottom: -6,
                      height: 2, borderRadius: 2, background: 'var(--color-brand-500)',
                    }}
                  />
                )}
              </button>
            );
          })}
        </div>

        {/* Right */}
        <div style={{ display: 'flex', gap: isMobile ? 6 : 10, alignItems: 'center', flexShrink: 0 }}>
          <button
            onClick={toggleTheme}
            title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
            style={{
              background: 'none',
              // Matches the round icon-button border color used throughout
              // the chat UI (bell/graph/help buttons on ChatPage) so this
              // light/dark toggle reads as the same control family.
              border: '1px solid var(--color-paper-light)',
              borderRadius: 999, padding: isMobile ? '8px' : '6px 8px',
              minWidth: isMobile ? 38 : undefined, minHeight: isMobile ? 38 : undefined,
              cursor: 'pointer', color: 'var(--color-paper-mid)',
              display: 'flex', alignItems: 'center', justifyContent: 'center', lineHeight: 0,
            }}
          >
            <Icon icon={isDark ? 'mdi:weather-sunny' : 'mdi:weather-night'} style={{ fontSize: 18 }} />
          </button>

          {isAuthenticated ? (
            <button
              ref={avatarBtnRef}
              onClick={openMenu}
              title="Account"
              style={{
                width: isMobile ? 38 : 34, height: isMobile ? 38 : 34,
                // Circular, matching the chat-UI avatar shape instead of
                // this button's old rounded-square frame.
                borderRadius: '50%',
                border: menuOpen ? '1px solid var(--color-paper-dark)' : '1px solid var(--color-paper-light)',
                background: 'var(--color-paper-surface)',
                cursor: 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontFamily: 'var(--font-inknut)', fontSize: 12, fontWeight: 500,
                color: 'var(--color-paper-dark)',
                overflow: 'hidden',
                transition: 'border-color 0.15s',
                padding: 0,
              }}
            >
              {user?.avatar_url
                ? <img src={user.avatar_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : initials}
            </button>
          ) : (
            <>
              <button
                onClick={() => navigate(ROUTES.LOGIN)}
                style={{
                  background: 'transparent',
                  border: '1px solid var(--color-paper-mid)',
                  color: 'var(--color-paper-mid)', padding: isMobile ? '8px 12px' : '7px 20px',
                  borderRadius: 999, fontFamily: "'Newsreader', serif", fontSize: isMobile ? 13 : 15, cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                Log in
              </button>
              <button
                onClick={() => navigate(ROUTES.SIGNUP)}
                style={{
                  background: 'var(--color-paper-dark)', border: 'none',
                  color: 'var(--color-paper-bg)', padding: isMobile ? '8px 12px' : '7px 20px',
                  borderRadius: 999, fontFamily: "'Newsreader', serif", fontSize: isMobile ? 13 : 15, cursor: 'pointer',
                  whiteSpace: 'nowrap',
                }}
              >
                {isMobile ? 'Sign up' : 'Get Started'}
              </button>
            </>
          )}
        </div>
      </motion.nav>

      {/* Avatar dropdown portal */}
      {isAuthenticated && createPortal(
        <AnimatePresence>
          {menuOpen && (
            <div style={{
              position: 'fixed',
              top: menuPos.top,
              right: Math.max(12, menuPos.right),
              zIndex: 9999,
            }}>
              <AvatarMenu
                user={user}
                onClose={() => setMenuOpen(false)}
                menuRef={menuRef}
                isMobile={isMobile}
              />
            </div>
          )}
        </AnimatePresence>,
        document.body
      )}
    </>
  );
};

export default SiteHeader;
