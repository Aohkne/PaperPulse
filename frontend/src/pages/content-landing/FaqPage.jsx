import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Icon } from '@iconify/react';
import SiteHeader from '@/shared/components/layout/SiteHeader';
import ContentFooter from './_shared/ContentFooter';
import { dotGridBg } from '@/shared/utils/dotGridBg';

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 22 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1], delay },
});

const FAQ_GROUPS = [
  {
    title: 'Getting Started',
    items: [
      {
        q: 'What is PaperPulse?',
        a: 'PaperPulse is an AI-powered literature review assistant. You enter a research question and it automatically searches academic databases, screens papers for relevance, groups them by theme, and generates a structured review — with every citation verified against a real source.',
      },
      {
        q: 'Do I need an account to use PaperPulse?',
        a: "You need an account to save and revisit your reviews. You can start a research session without signing in, but your results won't be saved.",
      },
      {
        q: 'What kind of research queries work best?',
        a: 'Specific academic topics work best — for example, "transformer models for biomedical NLP" or "randomized controlled trials for mindfulness-based stress reduction". Very broad queries (e.g. "artificial intelligence") return less focused results.',
      },
      {
        q: 'How long does a literature review take to generate?',
        a: "Typically 2–5 minutes end-to-end, depending on the number of papers found and the number of themes in your outline. The process streams results in real time so you'll see progress as it runs.",
      },
    ],
  },
  {
    title: 'How It Works',
    items: [
      {
        q: 'Where do the papers come from?',
        a: 'PaperPulse searches Semantic Scholar, one of the largest open academic databases. It retrieves up to 100 candidate papers per query, then filters and ranks them by relevance using semantic embeddings (SPECTER v2).',
      },
      {
        q: 'What is citation snowballing?',
        a: 'After the initial search, PaperPulse expands the paper set by following citation chains — pulling in papers that cite or are cited by the most relevant results. This surfaces important work that keyword search alone might miss.',
      },
      {
        q: 'Can I export my review?',
        a: 'Yes. Completed reviews can be exported as Markdown or LaTeX with full citations included.',
      },
    ],
  },
  {
    title: 'Trust & Accuracy',
    items: [
      {
        q: 'Can PaperPulse hallucinate citations?',
        a: 'No — this is the core design goal. Every source tag in a generated review is traced back to a real paper via a multi-tier verification pipeline: snippet matching, arXiv full-text retrieval, and abstract fallback. Claims that can\'t be verified are flagged as "low confidence" for your review — they are never silently included.',
      },
      {
        q: 'What does "low confidence" mean on a claim?',
        a: 'When PaperPulse cannot find sufficient evidence in the source paper to support a generated claim, it marks it as low confidence. This is your signal to check that passage before including it in your work.',
      },
      {
        q: 'Is PaperPulse a replacement for reading the original papers?',
        a: 'No. PaperPulse accelerates the screening and synthesis phase — it helps you identify which papers matter and understand how they relate. Critical academic work still requires reading primary sources and exercising your own judgment.',
      },
    ],
  },
];

const FaqItem = ({ q, a }) => {
  const [open, setOpen] = useState(false);

  return (
    <div style={{ borderBottom: '1px solid rgba(41, 17, 0, 0.08)' }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{
          width: '100%', textAlign: 'left',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '18px 0', background: 'none', border: 'none', cursor: 'pointer',
          gap: 16,
        }}
      >
        <span style={{
          fontFamily: "'Newsreader', serif", fontSize: 16,
          color: 'var(--color-paper-dark)', fontWeight: 500, lineHeight: 1.5,
        }}>
          {q}
        </span>
        <Icon
          icon={open ? 'mdi:minus' : 'mdi:plus'}
          style={{ fontSize: 20, flexShrink: 0, color: 'var(--color-paper-mid)' }}
        />
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            style={{ overflow: 'hidden' }}
          >
            <p style={{
              fontFamily: "'Newsreader', serif", fontSize: 17, lineHeight: 1.8,
              color: 'var(--color-paper-mid)', margin: '0 0 20px', paddingRight: 32,
            }}>
              {a}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

const FaqPage = () => (
  // --color-landing-tone-1 + re-added dot-grain — matches
  // SiteHeader/SiteFooter/ContentFooter in both themes now, so the page
  // doesn't read as a separate strip between them.
  <div style={{ ...dotGridBg('--color-landing-tone-1'), fontFamily: "'Newsreader', serif", minHeight: '100vh' }}>
    <SiteHeader />

    <div style={{ paddingTop: 57 }}>
      {/* Header */}
      <section style={{ maxWidth: 720, margin: '0 auto', padding: '80px 24px 32px' }}>
        <motion.p {...fadeUp(0.1)} style={{
          fontSize: 13, color: 'var(--color-paper-mid)',
          letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 16px',
        }}>
          FAQ
        </motion.p>
        <motion.h1 {...fadeUp(0.2)} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 42, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 12px', lineHeight: 1.2,
        }}>
          Frequently asked questions
        </motion.h1>
        <motion.p {...fadeUp(0.3)} style={{
          fontSize: 17, color: 'var(--color-paper-mid)', margin: 0, lineHeight: 1.7,
        }}>
          Common questions about how PaperPulse works.
        </motion.p>
      </section>

      {/* FAQ groups */}
      {FAQ_GROUPS.map(({ title, items }) => (
        <section key={title} style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px 0' }}>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4, delay: 0.05 }}
            style={{
              fontFamily: 'var(--font-inknut)', fontSize: 20, fontWeight: 500,
              color: 'var(--color-paper-dark)', margin: '0 0 8px',
            }}
          >
            {title}
          </motion.h2>
          <div style={{ borderTop: '2px solid var(--color-paper-dark)', marginBottom: 4 }} />
          {items.map(({ q, a }) => <FaqItem key={q} q={q} a={a} />)}
        </section>
      ))}

      <div style={{ paddingBottom: 80 }} />

      <ContentFooter />
    </div>
  </div>
);

export default FaqPage;
