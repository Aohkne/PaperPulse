import { useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';
import SiteHeader from '@/shared/components/layout/SiteHeader';
import SiteFooter from '@/shared/components/layout/SiteFooter';
import { ROUTES } from '@/shared/constant/routes';

// ── Animation helpers ─────────────────────────────────────────────────────────
const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 22 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1], delay },
});

const inView = (delay = 0) => ({
  initial: { opacity: 0, y: 24 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1], delay },
});

// ── Data ──────────────────────────────────────────────────────────────────────
const STEPS = [
  {
    num: '01',
    icon: 'mdi:text-search',
    title: 'Ask your research question',
    body: 'Type a topic or question. PaperPulse turns it into structured search terms automatically.',
  },
  {
    num: '02',
    icon: 'mdi:filter-check-outline',
    title: 'AI finds & screens papers',
    body: 'We search academic sources, score relevance, and filter out noise — surfacing only what matters.',
  },
  {
    num: '03',
    icon: 'mdi:book-open-page-variant-outline',
    title: 'Read your review & discover gaps',
    body: 'Get a structured summary, knowledge graph, and detected research gaps. Every citation is real.',
  },
];

const FEATURES = [
  {
    icon: 'mdi:magnify',
    title: 'Smart Paper Discovery',
    body: 'Search and filter thousands of academic papers by topic, method, year, and citation count.',
  },
  {
    icon: 'mdi:graph-outline',
    title: 'Knowledge Graph',
    body: 'Visualise connections between papers, authors, and research topics to spot patterns and clusters.',
  },
  {
    icon: 'mdi:shield-check-outline',
    title: 'Citation Guardrails',
    body: 'PaperPulse only cites papers that exist. No hallucinated references, no fabricated authors — ever.',
  },
  {
    icon: 'mdi:text-box-search-outline',
    title: 'Research Gap Detection',
    body: 'Surfaces contradictions, understudied angles, and open questions across your paper set.',
  },
  {
    icon: 'mdi:file-export-outline',
    title: 'Export & Edit',
    body: 'Download your review as PDF or edit inline — structured for academic use.',
  },
  {
    icon: 'mdi:robot-outline',
    title: 'No Hallucinations',
    body: 'Every claim links to a real paper. PaperPulse refuses to fabricate authors, titles, or dates.',
  },
];

const PAYG_BORDER = '#6F1F06';

const PLANS = [
  {
    id: 'free',
    name: 'Free',
    price: '0đ',
    sub: 'forever',
    cta: 'Get Started',
    ctaOutline: true,
    highlight: false,
    features: [
      { ok: true, label: '3 Literature Reviews / month' },
      { ok: true, label: '5 PDF Agent uses / month' },
      { ok: true, label: 'Knowledge Graph included free' },
      { ok: true, label: '3 Research Gaps / month' },
      { ok: false, label: 'Top up when you run out of quota' },
    ],
  },
  {
    id: 'plus',
    name: 'Plus',
    badge: 'Most Popular',
    price: '19.000đ',
    sub: 'per month',
    cta: 'Upgrade',
    ctaOutline: false,
    highlight: true,
    features: [
      { ok: true, label: '5 Literature Reviews / month' },
      { ok: true, label: '10 PDF Agent uses / month' },
      { ok: true, label: 'Knowledge Graph included free' },
      { ok: true, label: '5 Research Gaps / month' },
      { ok: true, label: 'Top up when you run out of quota' },
    ],
  },
  {
    id: 'unlimited',
    name: 'Unlimited',
    price: '299.000đ',
    sub: 'per month',
    cta: 'Upgrade',
    ctaOutline: true,
    highlight: false,
    features: [
      { ok: true, label: 'Unlimited Literature Reviews' },
      { ok: true, label: 'Unlimited PDF Agent' },
      { ok: true, label: 'Knowledge Graph included free' },
      { ok: true, label: 'Unlimited Research Gaps' },
      { ok: true, label: 'No need to top up' },
    ],
  },
];

// ── Small shared bits ─────────────────────────────────────────────────────────
const Eyebrow = ({ icon, children }) => (
  <div style={{
    display: 'inline-flex', alignItems: 'center', gap: 7,
    padding: '6px 14px', borderRadius: 999,
    border: '1px solid var(--color-paper-surface)',
    background: 'var(--color-paper-surface)',
    fontFamily: "'Noto Serif', serif", fontSize: 13,
    color: 'var(--color-paper-mid)', letterSpacing: '0.08em',
    textTransform: 'uppercase',
  }}>
    {icon && <Icon icon={icon} style={{ fontSize: 14, color: 'var(--color-brand-500)' }} />}
    {children}
  </div>
);

const PillButton = ({ children, onClick, variant = 'primary', arrow = false, style }) => {
  const [hover, setHover] = useState(false);
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: 8,
    padding: '12px 26px', borderRadius: 999,
    fontFamily: "'Noto Serif', serif", fontSize: 16,
    cursor: 'pointer', border: 'none', transition: 'opacity 0.15s, background 0.15s',
  };
  const variants = {
    primary: { background: 'var(--color-paper-dark)', color: 'var(--color-paper-bg)' },
    secondary: { background: 'transparent', color: 'var(--color-paper-mid)', border: '1px solid var(--color-paper-mid)' },
  };
  return (
    <motion.button
      whileHover={{ scale: 1.03 }}
      whileTap={{ scale: 0.97 }}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
      style={{ ...base, ...variants[variant], ...style }}
    >
      {children}
      {arrow && (
        <motion.span
          animate={{ x: hover ? 4 : 0 }}
          transition={{ duration: 0.15 }}
          style={{ display: 'inline-flex' }}
        >
          <Icon icon="mdi:arrow-right" style={{ fontSize: 17 }} />
        </motion.span>
      )}
    </motion.button>
  );
};

const IconTile = ({ icon, size = 44 }) => (
  <div style={{
    width: size, height: size, borderRadius: 12,
    background: 'var(--color-paper-surface)',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    marginBottom: 16,
  }}>
    <Icon icon={icon} style={{ fontSize: size * 0.5, color: 'var(--color-paper-mid)' }} />
  </div>
);

// ── Page ──────────────────────────────────────────────────────────────────────
const LandingPage = () => {
  const navigate = useNavigate();
  const howItWorksRef = useRef(null);

  return (
    <div style={{ fontFamily: "'Noto Serif', serif", background: 'var(--color-paper-bg)', minHeight: '100vh' }}>
      <SiteHeader />

      <div style={{ paddingTop: 57 }}>

        {/* ── Hero ─────────────────────────────────────────────────────── */}
        <section style={{
          position: 'relative', overflow: 'hidden',
          minHeight: '84vh', display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          textAlign: 'center', padding: '80px 24px 60px',
        }}>
          {/* Soft background blobs */}
          <div style={{ position: 'absolute', inset: 0, zIndex: 0, pointerEvents: 'none' }}>
            <div style={{
              position: 'absolute', top: -140, left: '6%', width: 380, height: 380,
              borderRadius: '50%', background: 'var(--color-brand-100)', opacity: 0.35, filter: 'blur(80px)',
            }} />
            <div style={{
              position: 'absolute', top: 60, right: '4%', width: 340, height: 340,
              borderRadius: '50%', background: 'var(--color-paper-light)', opacity: 0.25, filter: 'blur(90px)',
            }} />
          </div>

          <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <motion.div {...fadeUp(0.1)} style={{ marginBottom: 24 }}>
              <Eyebrow icon="mdi:sparkles-outline">AI Research Assistant</Eyebrow>
            </motion.div>

            <h1 style={{ margin: 0, lineHeight: 1.15 }}>
              <motion.span {...fadeUp(0.25)} style={{
                display: 'block', fontFamily: 'var(--font-inknut)',
                fontSize: 'clamp(32px, 8vw, 56px)', color: 'var(--color-paper-dark)', fontWeight: 500, letterSpacing: '-0.01em',
              }}>
                Your Literature Review,
              </motion.span>
              <motion.span {...fadeUp(0.38)} style={{
                display: 'block', fontFamily: 'var(--font-inknut)',
                fontSize: 'clamp(32px, 8vw, 56px)', color: 'var(--color-paper-mid)', fontWeight: 500, letterSpacing: '-0.01em',
              }}>
                Done in Hours.
              </motion.span>
            </h1>

            <motion.p {...fadeUp(0.52)} style={{
              fontFamily: "'Noto Serif', serif", fontSize: 18,
              color: 'var(--color-paper-mid)', maxWidth: 560,
              margin: '24px auto', lineHeight: 1.7,
            }}>
              Analyse hundreds of papers, detect research gaps, and generate
              citation-verified summaries — without fabricating a single source.
            </motion.p>

            <motion.div {...fadeUp(0.65)} style={{
              display: 'flex', gap: 12, justifyContent: 'center',
              marginTop: 32, flexWrap: 'wrap',
            }}>
              <PillButton variant="primary" arrow onClick={() => navigate(ROUTES.APP)}>
                Start Researching
              </PillButton>
              <PillButton variant="secondary" onClick={() => howItWorksRef.current?.scrollIntoView({ behavior: 'smooth' })}>
                See how it works
              </PillButton>
            </motion.div>
          </div>
        </section>

        {/* ── Demo Video ───────────────────────────────────────────────── */}
        <section
          id="demo"
          style={{ background: 'var(--color-paper-bg)', padding: '88px 24px' }}
        >
          <div style={{ textAlign: 'center', marginBottom: 40 }}>
            <motion.div {...inView()} style={{ marginBottom: 18 }}>
              <Eyebrow icon="mdi:play-circle-outline">Demo</Eyebrow>
            </motion.div>
            <motion.h2 {...inView(0.08)} style={{
              fontFamily: 'var(--font-inknut)', fontSize: 30, fontWeight: 500,
              color: 'var(--color-paper-dark)', margin: 0,
            }}>
              See PaperPulse in action
            </motion.h2>
          </div>

          <motion.div {...inView(0.1)} style={{ maxWidth: 760, margin: '0 auto' }}>
            <div style={{
              position: 'relative', width: '100%', paddingTop: '56.25%',
              borderRadius: 16, overflow: 'hidden',
              boxShadow: '0 16px 40px rgba(0,0,0,0.16)',
            }}>
              <iframe
                src="https://www.youtube.com/embed/g7bTfmkbx7g"
                title="PaperPulse demo"
                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', border: 0 }}
                allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                allowFullScreen
                loading="lazy"
              />
            </div>
          </motion.div>
        </section>

        {/* ── How It Works ─────────────────────────────────────────────── */}
        <section
          ref={howItWorksRef}
          id="how-it-works"
          style={{ background: 'var(--color-paper-surface)', padding: '88px 24px' }}
        >
          <div style={{ textAlign: 'center', marginBottom: 56 }}>
            <motion.div {...inView()} style={{ marginBottom: 18 }}>
              <Eyebrow>Process</Eyebrow>
            </motion.div>
            <motion.h2 {...inView(0.08)} style={{
              fontFamily: 'var(--font-inknut)', fontSize: 30, fontWeight: 500,
              color: 'var(--color-paper-dark)', margin: 0,
            }}>
              From question to insight — in minutes
            </motion.h2>
          </div>

          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: '32px 0', maxWidth: 900, margin: '0 auto',
          }}>
            {STEPS.map(({ num, icon, title, body }, i) => (
              <motion.div
                key={num}
                {...inView(i * 0.12)}
                style={{
                  padding: '0 36px',
                  borderRight: i < STEPS.length - 1
                    ? '1px solid var(--color-paper-light)'
                    : 'none',
                }}
              >
                <div style={{
                  fontFamily: 'var(--font-inknut)', fontSize: 44, fontWeight: 500,
                  color: 'var(--color-paper-light)', lineHeight: 1, marginBottom: 16,
                }}>
                  {num}
                </div>
                <IconTile icon={icon} size={48} />
                <p style={{
                  fontFamily: 'var(--font-inknut)', fontSize: 17, fontWeight: 500,
                  color: 'var(--color-paper-dark)', margin: '0 0 10px',
                }}>
                  {title}
                </p>
                <p style={{
                  fontFamily: "'Noto Serif', serif", fontSize: 15, lineHeight: 1.7,
                  color: 'var(--color-paper-mid)', margin: 0,
                }}>
                  {body}
                </p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* ── Features ─────────────────────────────────────────────────── */}
        <section
          id="features"
          style={{ background: 'var(--color-paper-bg)', padding: '88px 24px' }}
        >
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <motion.div {...inView()} style={{ marginBottom: 18 }}>
              <Eyebrow>Capabilities</Eyebrow>
            </motion.div>
            <motion.h2 {...inView(0.08)} style={{
              fontFamily: 'var(--font-inknut)', fontSize: 30, fontWeight: 500,
              color: 'var(--color-paper-dark)', margin: 0,
            }}>
              Everything you need for rigorous research
            </motion.h2>
          </div>

          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))',
            gap: 20, maxWidth: 940, margin: '0 auto',
          }}>
            {FEATURES.map(({ icon, title, body }, i) => (
              <motion.div
                key={title}
                {...inView(i * 0.08)}
                whileHover={{ y: -5, boxShadow: '0 12px 30px rgba(41,17,0,0.08)' }}
                style={{
                  background: 'var(--color-paper-bg)',
                  border: '1px solid var(--color-paper-surface)',
                  borderRadius: 14, padding: 28, cursor: 'default',
                }}
              >
                <IconTile icon={icon} />
                <p style={{
                  fontFamily: 'var(--font-inknut)', fontSize: 17, fontWeight: 500,
                  color: 'var(--color-paper-dark)', margin: '0 0 8px',
                }}>
                  {title}
                </p>
                <p style={{
                  fontFamily: "'Noto Serif', serif", fontSize: 15, lineHeight: 1.7,
                  color: 'var(--color-paper-mid)', margin: 0,
                }}>
                  {body}
                </p>
              </motion.div>
            ))}
          </div>
        </section>

        {/* ── Pricing ──────────────────────────────────────────────────── */}
        <section
          id="pricing"
          style={{ background: 'var(--color-paper-surface)', padding: '88px 24px' }}
        >
          <div style={{ textAlign: 'center', marginBottom: 48 }}>
            <motion.div {...inView()} style={{ marginBottom: 18 }}>
              <Eyebrow>Pricing</Eyebrow>
            </motion.div>
            <motion.h2 {...inView(0.08)} style={{
              fontFamily: 'var(--font-inknut)', fontSize: 30, fontWeight: 500,
              color: 'var(--color-paper-dark)', margin: '0 0 10px',
            }}>
              Simple, transparent pricing
            </motion.h2>
            <motion.p {...inView(0.16)} style={{
              fontFamily: "'Noto Serif', serif", fontSize: 16,
              color: 'var(--color-paper-mid)', margin: 0,
            }}>
              Start free. Pay only when you need more.
            </motion.p>
          </div>

          <div style={{
            display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
            gap: 24, maxWidth: 900, margin: '0 auto', alignItems: 'start',
          }}>
            {PLANS.map((plan, i) => (
              <motion.div
                key={plan.id}
                {...inView(i * 0.1)}
                style={{
                  background: 'var(--color-paper-bg)',
                  border: plan.highlight ? `2px solid ${PAYG_BORDER}` : '1px solid var(--color-paper-surface)',
                  borderRadius: 16, padding: 28, position: 'relative',
                  boxShadow: plan.highlight ? '0 16px 40px rgba(111,31,6,0.12)' : 'none',
                  transform: plan.highlight ? 'translateY(-6px)' : 'none',
                }}
              >
                {/* Badge */}
                {plan.badge && (
                  <div style={{
                    position: 'absolute', top: -13, left: '50%', transform: 'translateX(-50%)',
                    background: PAYG_BORDER, color: '#fff',
                    padding: '3px 14px', borderRadius: 20,
                    fontSize: 10, fontWeight: 700, letterSpacing: '0.05em',
                    whiteSpace: 'nowrap',
                  }}>
                    {plan.badge}
                  </div>
                )}

                {/* Plan name */}
                <p style={{
                  fontFamily: 'var(--font-inknut)', fontSize: 15, fontWeight: 500,
                  color: 'var(--color-paper-dark)', margin: '0 0 8px',
                }}>
                  {plan.name}
                </p>

                {/* Price */}
                <p style={{
                  fontFamily: "'Calistoga', serif",
                  fontSize: plan.highlight ? 36 : 44,
                  fontWeight: 400, color: 'var(--color-paper-dark)',
                  margin: '0 0 4px', lineHeight: 1.1,
                }}>
                  {plan.price}
                </p>
                <p style={{
                  fontFamily: "'Noto Serif', serif", fontSize: 13,
                  color: 'var(--color-paper-mid)', margin: '0 0 20px',
                }}>
                  {plan.sub}
                </p>

                {/* CTA */}
                <button
                  onClick={() => navigate(ROUTES.APP)}
                  style={{
                    width: '100%', padding: '11px 0', marginBottom: 20,
                    borderRadius: 999, cursor: 'pointer',
                    fontFamily: "'Noto Serif', serif", fontSize: 15,
                    background: plan.ctaOutline ? 'transparent' : PAYG_BORDER,
                    color: plan.ctaOutline ? 'var(--color-paper-mid)' : '#fff',
                    border: plan.ctaOutline ? '1px solid var(--color-paper-mid)' : 'none',
                    transition: 'opacity 0.15s',
                  }}
                >
                  {plan.cta}
                </button>

                {/* Feature list */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {plan.features.map(({ ok, label }) => (
                    <div key={label} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                      <Icon
                        icon={ok ? 'mdi:check-circle' : 'mdi:close-circle'}
                        style={{ fontSize: 18, flexShrink: 0, color: ok ? 'var(--color-paper-mid)' : '#CDBFAD' }}
                      />
                      <span style={{
                        fontFamily: "'Noto Serif', serif", fontSize: 14,
                        color: 'var(--color-paper-mid)',
                      }}>
                        {label}
                      </span>
                    </div>
                  ))}
                </div>
              </motion.div>
            ))}
          </div>

          <p style={{
            textAlign: 'center', marginTop: 28,
            fontFamily: "'Noto Serif', serif", fontSize: 13,
            color: 'var(--color-paper-mid)',
          }}>
            Need more mid-cycle? Top up Literature Review / PDF Agent right inside the app.
          </p>
        </section>

        {/* ── Footer ───────────────────────────────────────────────────── */}
        <SiteFooter />

      </div>
    </div>
  );
};

export default LandingPage;
