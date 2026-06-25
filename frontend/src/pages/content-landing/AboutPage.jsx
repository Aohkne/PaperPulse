import { motion } from 'framer-motion';
import SiteHeader from '@/shared/components/layout/SiteHeader';
import ContentFooter from './_shared/ContentFooter';

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

const TEAM = [
  { name: 'Nguyễn Phan Duy Bảo', id: '[ID TBD]' },
  { name: 'Lê Hữu Khoa', id: '[ID TBD]' },
  { name: 'Trần Nguyễn Anh Thư', id: '[ID TBD]' },
];

const Divider = () => (
  <div style={{ borderTop: '1px solid var(--color-paper-surface)', maxWidth: 720, margin: '0 auto' }} />
);

const AboutPage = () => (
  <div style={{ fontFamily: 'Georgia, serif', background: 'var(--color-paper-bg)', minHeight: '100vh' }}>
    <SiteHeader />

    <div style={{ paddingTop: 57 }}>
      {/* Hero */}
      <section style={{ maxWidth: 720, margin: '0 auto', padding: '80px 24px 64px' }}>
        <motion.p {...fadeUp(0.1)} style={{
          fontSize: 13, color: 'var(--color-paper-light)',
          letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 16px',
        }}>
          About
        </motion.p>

        <motion.h1 {...fadeUp(0.2)} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 42, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 28px', lineHeight: 1.2,
        }}>
          Built for researchers who can't afford to miss a paper.
        </motion.h1>

        <motion.p {...fadeUp(0.3)} style={{
          fontSize: 18, lineHeight: 1.8, color: 'var(--color-paper-mid)', margin: '0 0 16px',
        }}>
          Researchers spend weeks combing through hundreds of papers before writing a
          single paragraph. PaperPulse compresses that into hours — without sacrificing
          the rigor that academic work demands.
        </motion.p>

        <motion.p {...fadeUp(0.38)} style={{
          fontSize: 18, lineHeight: 1.8, color: 'var(--color-paper-mid)', margin: 0,
        }}>
          We built PaperPulse because we experienced this pain firsthand: too many papers,
          too little time, and existing AI tools that fabricated sources with alarming
          confidence. Accuracy isn't optional in academic work — so we made it the foundation.
        </motion.p>
      </section>

      <Divider />

      {/* What makes us different */}
      <section style={{ maxWidth: 720, margin: '0 auto', padding: '64px 24px' }}>
        <motion.h2 {...inView()} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 26, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 24px',
        }}>
          Rigorous by design
        </motion.h2>

        <motion.p {...inView(0.1)} style={{
          fontSize: 17, lineHeight: 1.8, color: 'var(--color-paper-mid)', margin: '0 0 16px',
        }}>
          Unlike general-purpose AI assistants, PaperPulse only cites papers that actually
          exist. Every claim in a generated review is traced back to a real source via a
          multi-tier verification pipeline — from snippet matching to full-text retrieval on
          arXiv.
        </motion.p>

        <motion.p {...inView(0.15)} style={{
          fontSize: 17, lineHeight: 1.8, color: 'var(--color-paper-mid)', margin: 0,
        }}>
          Low-confidence claims are flagged for human review rather than silently included.
          No fabricated authors, no hallucinated DOIs, no citation drift — ever.
        </motion.p>
      </section>

      <Divider />

      {/* Team */}
      <section style={{ maxWidth: 720, margin: '0 auto', padding: '64px 24px' }}>
        <motion.h2 {...inView()} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 26, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 32px',
        }}>
          The team
        </motion.h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {TEAM.map(({ name, id }, i) => (
            <motion.div
              key={name}
              {...inView(i * 0.08)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '16px 20px',
                border: '1px solid var(--color-paper-surface)',
                borderRadius: 4,
              }}
            >
              <span style={{ fontSize: 16, color: 'var(--color-paper-dark)', fontWeight: 500 }}>
                {name}
              </span>
              <span style={{ fontSize: 13, color: 'var(--color-paper-light)', fontFamily: 'Georgia, serif' }}>
                {id}
              </span>
            </motion.div>
          ))}
        </div>
      </section>

      <Divider />

      {/* Built at */}
      <section style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px 80px' }}>
        <motion.p {...inView()} style={{
          fontSize: 15, lineHeight: 1.7, color: 'var(--color-paper-mid)', margin: 0,
          fontStyle: 'italic',
        }}>
          PaperPulse was built as part of an intensive 6-week AI engineering program in 2026,
          with a focus on production-quality LLM + RAG systems for the research domain.
        </motion.p>
      </section>

      <ContentFooter />
    </div>
  </div>
);

export default AboutPage;
