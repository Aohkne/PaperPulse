import { Link } from 'react-router-dom';
import { useThemeStore } from '@/shared/store/useThemeStore';
import BackToTopButton from '@/shared/components/ui/BackToTopButton';
import { useIsMobile } from '@/shared/hooks/useIsMobile';

const PRODUCT_LINKS = [
  { label: 'Home', to: '/' },
  { label: 'About', to: '/about' },
  { label: 'FAQ', to: '/faq' },
];

const LEGAL_LINKS = [
  { label: 'Privacy Policy', to: '/privacy' },
  { label: 'Terms of Service', to: '/terms' },
];

const ContentFooter = () => {
  const theme = useThemeStore((s) => s.theme);
  const isMobile = useIsMobile(640);
  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const colTitle = (text) => (
    <p
      style={{
        fontFamily: "'Newsreader', serif",
        fontSize: 11,
        fontWeight: 600,
        color: 'var(--color-paper-mid)',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        margin: '0 0 16px',
      }}
    >
      {text}
    </p>
  );

  const linkStyle = {
    display: 'block',
    fontFamily: "'Newsreader', serif",
    fontSize: 15,
    color: 'var(--color-paper-mid)',
    textDecoration: 'none',
    marginBottom: 10,
  };

  return (
    <>
      {/* Flat --color-landing-tone-1 bg, no dot-grain — matches SiteFooter
        (the same footer on the main landing page) exactly in both themes,
        instead of the two footers rendering visibly different textures. */}
      <footer
        style={{
          background: 'var(--color-landing-tone-1)',
          borderTop: '1px solid rgba(41, 17, 0, 0.08)',
        }}
      >
        {/* Top section */}
        <div
          style={{
            display: 'flex',
            flexDirection: isMobile ? 'column' : 'row',
            gap: isMobile ? 32 : 40,
            maxWidth: 960,
            margin: '0 auto',
            padding: '56px 24px 48px',
          }}
        >
          {/* Brand */}
          <div style={{ flex: isMobile ? 'none' : 2 }}>
            <img
              src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
              alt="PaperPulse"
              style={{ height: 28, width: 'auto', marginBottom: 14 }}
            />
            <p
              style={{
                fontFamily: "'Newsreader', serif",
                fontSize: 15,
                lineHeight: 1.6,
                color: 'var(--color-paper-mid)',
                margin: 0,
                maxWidth: 220,
              }}
            >
              AI-powered literature review. From research question to finished output.
            </p>
          </div>

          {/* Product */}
          <div style={{ flex: isMobile ? 'none' : 1 }}>
            {colTitle('Product')}
            {PRODUCT_LINKS.map(({ label, to }) => (
              <Link
                key={to}
                to={to}
                style={linkStyle}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--color-paper-dark)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--color-paper-mid)';
                }}
              >
                {label}
              </Link>
            ))}
          </div>

          {/* Legal */}
          <div style={{ flex: isMobile ? 'none' : 1 }}>
            {colTitle('Legal')}
            {LEGAL_LINKS.map(({ label, to }) => (
              <Link
                key={to}
                to={to}
                style={linkStyle}
                onMouseEnter={(e) => {
                  e.currentTarget.style.color = 'var(--color-paper-dark)';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.color = 'var(--color-paper-mid)';
                }}
              >
                {label}
              </Link>
            ))}
          </div>
        </div>

        {/* Bottom bar */}
        <div
          style={{
            borderTop: '1px solid rgba(41, 17, 0, 0.08)',
            padding: '16px 24px',
            maxWidth: 960,
            margin: '0 auto',
          }}
        >
          <span
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: 14,
              color: 'var(--color-paper-mid)',
            }}
          >
            © 2026 PaperPulse · C2-App-069
          </span>
        </div>
      </footer>
      <BackToTopButton />
    </>
  );
};

export default ContentFooter;
