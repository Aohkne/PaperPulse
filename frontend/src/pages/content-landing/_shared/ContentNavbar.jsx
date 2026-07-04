import { Link, useNavigate } from 'react-router-dom';
import { Icon } from '@iconify/react';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { useAuthStore } from '@/features/auth/store/useAuthStore';

const ContentNavbar = () => {
  const navigate = useNavigate();
  const theme = useThemeStore((s) => s.theme);
  const toggleTheme = useThemeStore((s) => s.toggleTheme);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  return (
    <nav
      style={{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 100,
        background: 'var(--color-paper-bg)',
        borderBottom: '1px solid var(--color-paper-surface)',
        padding: '12px 40px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}
    >
      {/* Logo */}
      <Link to="/" style={{ lineHeight: 0 }}>
        <img
          src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
          alt="PaperPulse"
          style={{ height: 32, width: 'auto', cursor: 'pointer' }}
        />
      </Link>

      {/* Center — Home link */}
      <Link
        to="/"
        style={{
          fontFamily: "'Newsreader', serif", fontSize: 15,
          color: 'var(--color-paper-mid)', textDecoration: 'none',
          transition: 'color 0.15s',
        }}
        onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-paper-dark)'; }}
        onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-paper-mid)'; }}
      >
        Home
      </Link>

      {/* Right */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <button
          onClick={toggleTheme}
          title={isDark ? 'Switch to light mode' : 'Switch to dark mode'}
          style={{
            background: 'none',
            border: '1px solid var(--color-paper-surface)',
            borderRadius: 2, padding: '6px 8px',
            cursor: 'pointer', color: 'var(--color-paper-mid)',
            display: 'flex', alignItems: 'center', lineHeight: 0,
          }}
        >
          <Icon icon={isDark ? 'mdi:weather-sunny' : 'mdi:weather-night'} style={{ fontSize: 18 }} />
        </button>

        {isAuthenticated ? (
          <button
            onClick={() => navigate('/app')}
            style={{
              background: 'var(--color-paper-dark)', border: 'none',
              color: 'var(--color-paper-bg)', padding: '7px 20px',
              borderRadius: 2, fontFamily: "'Newsreader', serif", fontSize: 16, cursor: 'pointer',
            }}
          >
            Go to App
          </button>
        ) : (
          <>
            <button
              onClick={() => navigate('/login')}
              style={{
                background: 'transparent',
                border: '1px solid var(--color-paper-mid)',
                color: 'var(--color-paper-mid)', padding: '7px 20px',
                borderRadius: 2, fontFamily: "'Newsreader', serif", fontSize: 16, cursor: 'pointer',
              }}
            >
              Log in
            </button>
            <button
              onClick={() => navigate('/signup')}
              style={{
                background: 'var(--color-paper-dark)', border: 'none',
                color: 'var(--color-paper-bg)', padding: '7px 20px',
                borderRadius: 2, fontFamily: "'Newsreader', serif", fontSize: 16, cursor: 'pointer',
              }}
            >
              Get Started
            </button>
          </>
        )}
      </div>
    </nav>
  );
};

export default ContentNavbar;
