import { useState } from 'react';
import { motion } from 'framer-motion';
import SiteHeader from '@/shared/components/layout/SiteHeader';
import ContentFooter from './_shared/ContentFooter';
import { dotGridBg } from '@/shared/utils/dotGridBg';

const NOTES = [
  {
    rot: '-2.2deg', pin: '#BB6A57', bg: '#f8ded5ff', bgDark: '#2A1615',
    title: 'Verified citations, always',
    body: 'Every claim traces back to a real paper — multi-tier pipeline from snippet matching to arXiv full-text. Low-confidence claims are flagged, never silently included.',
  },
  {
    rot: '1.8deg', pin: '#457a5bff', bg: '#ffe8d2ff', bgDark: '#281E10',
    title: 'You stay in control',
    body: 'Step in at any point. Adjust scope, refine themes, exclude papers, redirect the synthesis. PaperPulse is a collaborator, not a black box.',
  },
  {
    rot: '2.4deg', pin: '#5775bbff', bg: '#e0eff0ff', bgDark: '#141E22',
    title: 'Surfaces the gap',
    body: "Contradictions between studies, underexplored angles, open questions — PaperPulse names what existing work hasn't addressed so you can define your contribution.",
  },
  {
    rot: '-1.6deg', pin: '#B5A23F', bg: '#f5fef3ff', bgDark: '#161E18',
    title: 'Works with your files',
    body: 'Upload PDFs, ZIP archives, or .tex files. A live knowledge graph maps how concepts, authors, and findings connect across your entire literature set.',
  },
];

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
  { name: 'Nguyễn Phan Duy Bảo', id: '2A202600688' },
  { name: 'Lê Hữu Khoa', id: '2A202600863' },
  { name: 'Trần Nguyễn Anh Thư', id: '2A202600915' },
];

const NoteCard = ({ rot, pin, bg, bgDark, title, body, delay }) => {
  const [hovered, setHovered] = useState(false);
  const isDark = document.documentElement.classList.contains('dark');
  const noteBg = isDark ? bgDark : bg;

  return (
    <motion.div
      initial={{ opacity: 0, y: 28, rotate: 0 }}
      whileInView={{ opacity: 1, y: 0, rotate: rot }}
      whileHover={{
        y: -10, rotate: '0deg', scale: 1.03,
        transition: { type: 'spring', stiffness: 260, damping: 18 },
      }}
      viewport={{ once: true, margin: '-40px' }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1], delay }}
      onHoverStart={() => setHovered(true)}
      onHoverEnd={() => setHovered(false)}
      style={{
        position: 'relative',
        background: noteBg,
        padding: '36px 24px 28px',
        boxShadow: hovered
          ? '6px 14px 36px rgba(41,17,0,0.18)'
          : '3px 6px 20px rgba(41,17,0,0.10)',
        cursor: 'default',
        transition: 'box-shadow 0.25s',
      }}
    >
      {/* Pin — lifts on hover */}
      <motion.div
        animate={{ y: hovered ? -5 : 0, scale: hovered ? 1.12 : 1 }}
        transition={{ type: 'spring', stiffness: 380, damping: 14 }}
        style={{
          position: 'absolute', top: -10, left: '50%', marginLeft: -10,
          width: 20, height: 20, borderRadius: '50%',
          background: pin,
          boxShadow: '0 2px 6px rgba(0,0,0,0.28)',
          border: '2px solid rgba(255,255,255,0.35)',
          zIndex: 1,
        }}
      />

      <p style={{
        fontFamily: 'var(--font-inknut)', fontSize: 15, fontWeight: 500,
        color: 'var(--color-paper-dark)', margin: '0 0 12px', lineHeight: 1.4,
      }}>
        {title}
      </p>
      <p style={{
        fontFamily: "'Newsreader', serif", fontSize: 16, lineHeight: 1.8,
        color: 'var(--color-paper-mid)', margin: 0,
      }}>
        {body}
      </p>
    </motion.div>
  );
};

const Divider = () => (
  <div style={{ borderTop: '1px solid rgba(41, 17, 0, 0.08)', maxWidth: 720, margin: '0 auto' }} />
);

const AboutPage = () => (
  // --color-landing-tone-1 + re-added dot-grain — matches
  // SiteHeader/SiteFooter/ContentFooter in both themes now, so the page
  // doesn't read as a separate strip sandwiched between them.
  <div style={{ ...dotGridBg('--color-landing-tone-1'), fontFamily: "'Newsreader', serif", minHeight: '100vh' }}>
    <SiteHeader />

    <div style={{ paddingTop: 57 }}>
      {/* Hero */}
      <section style={{ maxWidth: 720, margin: '0 auto', padding: '80px 24px 64px' }}>
        <motion.p {...fadeUp(0.1)} style={{
          fontSize: 13, color: 'var(--color-paper-mid)',
          letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 16px',
        }}>
          About Us
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
      <section style={{ maxWidth: 760, margin: '0 auto', padding: '64px 24px' }}>
        <motion.h2 {...inView()} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 26, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 48px',
        }}>
          What makes us different
        </motion.h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '40px 32px' }}>
          {NOTES.map(({ rot, pin, bg, bgDark, title, body }, i) => (
            <NoteCard
              key={title}
              rot={rot} pin={pin} bg={bg} bgDark={bgDark}
              title={title} body={body}
              delay={i * 0.1}
            />
          ))}
        </div>
      </section>

      <Divider />

      {/* Team */}
      <section style={{ maxWidth: 720, margin: '0 auto', padding: '64px 24px' }}>
        <motion.h2 {...inView()} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 26, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 32px',
        }}>
          Meet the Team
        </motion.h2>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {TEAM.map(({ name, id }, i) => (
            <motion.div
              key={name}
              {...inView(i * 0.08)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '16px 20px',
                border: '1px solid rgba(41, 17, 0, 0.08)',
                borderRadius: 4,
              }}
            >
              <span style={{ fontSize: 16, color: 'var(--color-paper-dark)', fontWeight: 500 }}>
                {name}
              </span>
              <span style={{ fontSize: 13, color: 'var(--color-paper-mid)', fontFamily: "'Newsreader', serif" }}>
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
          fontSize: 16, lineHeight: 1.7, color: 'var(--color-paper-mid)', margin: 0,
          fontStyle: 'italic',
        }}>
          PaperPulse was built as part of an intensive 6-week AI in Action program Cohort 2 in 2026,
          with a focus on production-quality LLM + RAG systems for the research domain.
        </motion.p>
      </section>

      <ContentFooter />
    </div>
  </div>
);

export default AboutPage;
