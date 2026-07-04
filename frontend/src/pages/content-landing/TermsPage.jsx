import { motion } from 'framer-motion';
import SiteHeader from '@/shared/components/layout/SiteHeader';
import ContentFooter from './_shared/ContentFooter';
import { dotGridBg } from '@/shared/utils/dotGridBg';

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 22 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1], delay },
});

const scrollUp = (delay = 0) => ({
  initial: { opacity: 0, y: 18 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: '-60px' },
  transition: { duration: 0.45, ease: [0.22, 1, 0.36, 1], delay },
});

const prose = { fontSize: 17, lineHeight: 1.85, color: 'var(--color-paper-mid)', margin: '0 0 16px' };
const h2Style = {
  fontFamily: 'var(--font-inknut)', fontSize: 20, fontWeight: 500,
  color: 'var(--color-paper-dark)', margin: '40px 0 12px',
};

const TermsPage = () => (
  // --color-landing-tone-1 + re-added dot-grain — matches
  // SiteHeader/SiteFooter/ContentFooter in both themes now, so the page
  // doesn't read as a separate strip between them.
  <div style={{ ...dotGridBg('--color-landing-tone-1'), fontFamily: "'Newsreader', serif", minHeight: '100vh' }}>
    <SiteHeader />

    <div style={{ paddingTop: 57 }}>
      <article style={{ maxWidth: 720, margin: '0 auto', padding: '80px 24px 80px' }}>
        <motion.p {...fadeUp(0.1)} style={{
          fontSize: 13, color: 'var(--color-paper-mid)',
          letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 16px',
        }}>
          Legal
        </motion.p>

        <motion.h1 {...fadeUp(0.2)} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 38, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 12px', lineHeight: 1.2,
        }}>
          Terms of Service
        </motion.h1>

        <motion.p {...fadeUp(0.3)} style={{
          fontSize: 14, color: 'var(--color-paper-mid)', margin: '0 0 48px',
        }}>
          Last updated: June 23, 2026
        </motion.p>

        <div style={{ borderTop: '1px solid rgba(41, 17, 0, 0.08)', marginBottom: 8 }} />

        <motion.div {...scrollUp(0.1)}>
          <h2 style={h2Style}>1. Acceptance of Terms</h2>
          <p style={prose}>
            By accessing or using PaperPulse, you agree to be bound by these Terms of Service.
            If you do not agree to these terms, please do not use the service.
          </p>

          <h2 style={h2Style}>2. Acceptable Use</h2>
          <p style={prose}>
            PaperPulse is intended for academic, educational, and personal research purposes.
            You agree not to:
          </p>
          <ul style={{ ...prose, paddingLeft: 24, margin: '0 0 16px' }}>
            <li style={{ marginBottom: 8 }}>Resell, sublicense, or commercially redistribute PaperPulse outputs without our written permission.</li>
            <li style={{ marginBottom: 8 }}>Attempt to circumvent rate limits, access controls, or authentication mechanisms.</li>
            <li style={{ marginBottom: 8 }}>Use the service in any way that violates applicable laws or regulations.</li>
            <li style={{ marginBottom: 8 }}>Systematically scrape or extract data from PaperPulse in bulk.</li>
          </ul>

          <h2 style={h2Style}>3. No Warranty on Accuracy</h2>
          <p style={prose}>
            PaperPulse uses AI and automated verification pipelines to generate literature
            reviews. While we take significant steps to ensure citation accuracy, AI-generated
            content may contain errors, omissions, or outdated information.
          </p>
          <p style={prose}>
            Users are responsible for verifying all claims before using them in published
            academic work. PaperPulse is a research aid — it does not replace professional
            academic judgment or peer review.
          </p>

          <h2 style={h2Style}>4. Intellectual Property</h2>
          <p style={prose}>
            The PaperPulse platform, interface, and underlying technology are proprietary
            to Team C2-App-069. Paper content retrieved from Semantic Scholar remains
            subject to each paper's original license and copyright. PaperPulse does not
            claim ownership over any retrieved academic papers.
          </p>

          <h2 style={h2Style}>5. Account Termination</h2>
          <p style={prose}>
            We reserve the right to suspend or terminate accounts that violate these terms,
            engage in abusive behavior, or misuse the service. We will notify you where
            possible before taking action.
          </p>

          <h2 style={h2Style}>6. Limitation of Liability</h2>
          <p style={prose}>
            To the maximum extent permitted by law, PaperPulse is provided "as is" without
            warranty of any kind. We are not liable for any indirect, incidental, or
            consequential damages arising from your use of the service, including any
            errors in generated literature reviews.
          </p>

          <h2 style={h2Style}>7. Changes to Terms</h2>
          <p style={prose}>
            We may update these Terms of Service from time to time. Continued use of
            PaperPulse after changes are posted constitutes acceptance of the updated terms.
            The "Last updated" date at the top reflects the most recent revision.
          </p>

        </motion.div>
      </article>

      <ContentFooter />
    </div>
  </div>
);

export default TermsPage;
