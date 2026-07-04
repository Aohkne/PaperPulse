import { useNavigate } from 'react-router-dom';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { ROUTES } from '@/shared/constant/routes';
import BackToTopButton from '@/shared/components/ui/BackToTopButton';
import { useIsMobile } from '@/shared/hooks/useIsMobile';

const FOOTER_PRODUCT = [
  { label: 'Home',  to: ROUTES.HOME  },
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
  const isMobile = useIsMobile(640);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const colTitle = (text) => (
    <p style={{
      fontFamily: "'Newsreader', serif", fontSize: 11, fontWeight: 600,
      color: 'var(--color-paper-mid)', letterSpacing: '0.1em',
      textTransform: 'uppercase', margin: '0 0 16px',
    }}>
      {text}
    </p>
  );

  const linkStyle = {
    display: 'block', fontFamily: "'Newsreader', serif", fontSize: 15,
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
    <>
    <footer style={{
      // --color-landing-tone-1 so the footer matches the Landing hero's
      // starting tone in both themes (light-mode surface / dark-mode bg).
      background: 'var(--color-landing-tone-1)',
      borderTop: '1px solid rgba(41, 17, 0, 0.08)',
    }}>
      {/* Top section */}
      <div style={{
        display: 'flex',
        flexDirection: isMobile ? 'column' : 'row',
        gap: isMobile ? 32 : 40,
        maxWidth: 960,
        margin: '0 auto',
        padding: '56px 24px 48px',
      }}>
        {/* Brand */}
        <div style={{ flex: isMobile ? 'none' : 2 }}>
          <img
            src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
            alt="PaperPulse"
            style={{ height: 28, width: 'auto', marginBottom: 14, cursor: 'pointer' }}
            onClick={() => navigate(ROUTES.HOME)}
          />
          <p style={{
            fontFamily: "'Newsreader', serif", fontSize: 15, lineHeight: 1.65,
            color: 'var(--color-paper-mid)', margin: 0, maxWidth: 210,
          }}>
            AI-powered literature review. From research question to finished output.
          </p>
        </div>

        {/* Product */}
        <div style={{ flex: isMobile ? 'none' : 1 }}>
          {colTitle('Product')}
          {FOOTER_PRODUCT.map(({ label, to }) => (
            <button key={to} style={linkStyle} {...hover} onClick={() => navigate(to)}>
              {label}
            </button>
          ))}
        </div>

        {/* Legal */}
        <div style={{ flex: isMobile ? 'none' : 1 }}>
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
        borderTop: '1px solid rgba(41, 17, 0, 0.08)',
        padding: '16px 24px',
        maxWidth: 960, margin: '0 auto',
      }}>
        <span style={{ fontFamily: "'Newsreader', serif", fontSize: 14, color: 'var(--color-paper-mid)' }}>
          © 2026 PaperPulse · C2-App-069
        </span>
      </div>
    </footer>
    <BackToTopButton />
    </>
  );
};

export default SiteFooter;
