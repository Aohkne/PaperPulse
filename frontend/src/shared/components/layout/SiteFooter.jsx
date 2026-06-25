import { useNavigate } from 'react-router-dom';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { ROUTES } from '@/shared/constant/routes';

const FOOTER_COMPANY = [
  { label: 'About', to: ROUTES.ABOUT },
  { label: 'FAQ',   to: ROUTES.FAQ   },
];

const FOOTER_LEGAL = [
  { label: 'Privacy', to: ROUTES.PRIVACY },
  { label: 'Terms',   to: ROUTES.TERMS   },
];

const SiteFooter = () => {
  const navigate = useNavigate();
  const theme = useThemeStore((s) => s.theme);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const colTitle = (text) => (
    <p style={{
      fontFamily: 'Georgia, serif', fontSize: 11, fontWeight: 600,
      color: 'var(--color-paper-light)', letterSpacing: '0.1em',
      textTransform: 'uppercase', margin: '0 0 16px',
    }}>
      {text}
    </p>
  );

  const linkStyle = {
    display: 'block', fontFamily: 'Georgia, serif', fontSize: 14,
    color: 'var(--color-paper-mid)', textDecoration: 'none',
    marginBottom: 10, background: 'none', border: 'none',
    cursor: 'pointer', padding: 0, textAlign: 'left',
    transition: 'color 0.15s',
  };

  const hover = {
    onMouseEnter: (e) => { e.currentTarget.style.color = 'var(--color-paper-dark)'; },
    onMouseLeave: (e) => { e.currentTarget.style.color = 'var(--color-paper-mid)'; },
  };

  return (
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
            style={{ height: 28, width: 'auto', marginBottom: 14, cursor: 'pointer' }}
            onClick={() => navigate(ROUTES.HOME)}
          />
          <p style={{
            fontFamily: 'Georgia, serif', fontSize: 14, lineHeight: 1.65,
            color: 'var(--color-paper-mid)', margin: 0, maxWidth: 210,
          }}>
            AI-powered literature review. From research question to finished output.
          </p>
        </div>

        {/* Company */}
        <div>
          {colTitle('Company')}
          {FOOTER_COMPANY.map(({ label, to }) => (
            <button key={to} style={linkStyle} {...hover} onClick={() => navigate(to)}>
              {label}
            </button>
          ))}
        </div>

        {/* Legal */}
        <div>
          {colTitle('Legal')}
          {FOOTER_LEGAL.map(({ label, to }) => (
            <button key={to} style={linkStyle} {...hover} onClick={() => navigate(to)}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Bottom bar */}
      <div style={{
        borderTop: '1px solid var(--color-paper-surface)',
        padding: '16px 24px',
        maxWidth: 960, margin: '0 auto',
      }}>
        <span style={{ fontFamily: 'Georgia, serif', fontSize: 13, color: 'var(--color-paper-mid)' }}>
          © 2026 PaperPulse · C2-App-069
        </span>
      </div>
    </footer>
  );
};

export default SiteFooter;
