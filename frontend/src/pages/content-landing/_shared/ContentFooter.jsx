import { Link } from 'react-router-dom';
import { useThemeStore } from '@/shared/store/useThemeStore';
import BackToTopButton from '@/shared/components/ui/BackToTopButton';

const PRODUCT_LINKS = [
  { label: 'Home',  to: '/'       },
  { label: 'About', to: '/about'  },
  { label: 'FAQ',   to: '/faq'    },
];

const LEGAL_LINKS = [
  { label: 'Privacy Policy', to: '/privacy' },
  { label: 'Terms of Service', to: '/terms' },
];

const ContentFooter = () => {
  const theme = useThemeStore((s) => s.theme);
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const colTitle = (text) => (
    <p style={{
      fontFamily: "'Noto Serif', serif", fontSize: 11, fontWeight: 600,
      color: 'var(--color-paper-light)', letterSpacing: '0.1em',
      textTransform: 'uppercase', margin: '0 0 16px',
    }}>
      {text}
    </p>
  );

  const linkStyle = {
    display: 'block', fontFamily: "'Noto Serif', serif", fontSize: 14,
    color: 'var(--color-paper-mid)', textDecoration: 'none',
    marginBottom: 10,
  };

  return (
    <>
    <footer style={{
      background: 'var(--color-paper-bg)',
      borderTop: '1px solid var(--color-paper-surface)',
    }}>
      {/* Top section */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '2fr 1fr 1fr',
        gap: 40,
        maxWidth: 960,
        margin: '0 auto',
        padding: '56px 24px 48px',
      }}>
        {/* Brand */}
        <div>
          <img
            src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
            alt="PaperPulse"
            style={{ height: 28, width: 'auto', marginBottom: 14 }}
          />
          <p style={{
            fontFamily: "'Noto Serif', serif", fontSize: 14, lineHeight: 1.6,
            color: 'var(--color-paper-mid)', margin: 0, maxWidth: 220,
          }}>
            AI-powered literature review. From research question to finished output.
          </p>
        </div>

        {/* Product */}
        <div>
          {colTitle('Product')}
          {PRODUCT_LINKS.map(({ label, to }) => (
            <Link
              key={to}
              to={to}
              style={linkStyle}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-paper-dark)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-paper-mid)'; }}
            >
              {label}
            </Link>
          ))}
        </div>

        {/* Legal */}
        <div>
          {colTitle('Legal')}
          {LEGAL_LINKS.map(({ label, to }) => (
            <Link
              key={to}
              to={to}
              style={linkStyle}
              onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--color-paper-dark)'; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--color-paper-mid)'; }}
            >
              {label}
            </Link>
          ))}
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{
        borderTop: '1px solid var(--color-paper-surface)',
        padding: '16px 24px',
        maxWidth: 960, margin: '0 auto',
      }}>
        <span style={{ fontFamily: "'Noto Serif', serif", fontSize: 13, color: 'var(--color-paper-mid)' }}>
          © 2026 PaperPulse · C2-App-069
        </span>
      </div>
    </footer>
    <BackToTopButton />
    </>
  );
};

export default ContentFooter;
