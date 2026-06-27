import { motion } from 'framer-motion';
import { Link } from 'react-router-dom';
import SiteHeader from '@/shared/components/layout/SiteHeader';
import ContentFooter from './_shared/ContentFooter';

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

const prose = { fontSize: 16, lineHeight: 1.85, color: 'var(--color-paper-mid)', margin: '0 0 16px' };
const h2Style = {
  fontFamily: 'var(--font-inknut)', fontSize: 20, fontWeight: 500,
  color: 'var(--color-paper-dark)', margin: '40px 0 12px',
};

const PrivacyPage = () => (
  <div style={{ fontFamily: "'Noto Serif', serif", background: 'var(--color-paper-bg)', minHeight: '100vh' }}>
    <SiteHeader />

    <div style={{ paddingTop: 57 }}>
      <article style={{ maxWidth: 720, margin: '0 auto', padding: '80px 24px 80px' }}>
        <motion.p {...fadeUp(0.1)} style={{
          fontSize: 13, color: 'var(--color-paper-light)',
          letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 16px',
        }}>
          Legal
        </motion.p>

        <motion.h1 {...fadeUp(0.2)} style={{
          fontFamily: 'var(--font-inknut)', fontSize: 38, fontWeight: 500,
          color: 'var(--color-paper-dark)', margin: '0 0 12px', lineHeight: 1.2,
        }}>
          Privacy Policy
        </motion.h1>

        <motion.p {...fadeUp(0.3)} style={{
          fontSize: 14, color: 'var(--color-paper-light)', margin: '0 0 48px',
        }}>
          Last updated: June 23, 2026
        </motion.p>

        <div style={{ borderTop: '1px solid var(--color-paper-surface)', marginBottom: 8 }} />

        <motion.div {...scrollUp(0.1)}>
          <h2 style={h2Style}>1. Introduction</h2>
          <p style={prose}>
            This Privacy Policy explains how PaperPulse ("we", "us", or "our") collects, uses,
            and protects information about you when you use our service. By using PaperPulse,
            you agree to the collection and use of information as described here.
          </p>

          <h2 style={h2Style}>2. Information We Collect</h2>
          <p style={prose}>
            <strong style={{ color: 'var(--color-paper-dark)' }}>Account data:</strong>{' '}
            When you register, we collect your email address and a hashed password via Supabase Auth.
            We do not store your password in plain text.
          </p>
          <p style={prose}>
            <strong style={{ color: 'var(--color-paper-dark)' }}>Usage data:</strong>{' '}
            We store the research queries you submit and the literature reviews you save, so you
            can revisit them later. This data is associated with your account.
          </p>
          <p style={prose}>
            We do not collect location data, device fingerprints, or behavioral tracking data.
            We do not serve ads and do not share your data with advertising networks.
          </p>

          <h2 style={h2Style}>3. Payment Information</h2>
          <p style={prose}>
            PaperPulse does not store payment card or banking information directly. If and when
            payment features are enabled, transactions will be processed by a third-party payment
            provider. We will store only your subscription status and transaction history — not
            your payment credentials. This policy will be updated when payment features launch.
          </p>

          <h2 style={h2Style}>4. How We Use Your Data</h2>
          <p style={prose}>
            We use collected information to provide and improve the PaperPulse service, authenticate
            your account, and communicate with you about your account or service updates. We do not
            use your research queries to train our models or share them with third parties for
            commercial purposes.
          </p>

          <h2 style={h2Style}>5. Data Sharing</h2>
          <p style={prose}>
            We do not sell your personal data. We share data only with the infrastructure providers
            necessary to operate the service — including Supabase (database and authentication) and
            LLM API providers (for generating literature review content). These providers process
            data under their own privacy agreements.
          </p>

          <h2 style={h2Style}>6. Data Retention</h2>
          <p style={prose}>
            Your data is retained for as long as your account is active. If you delete your account,
            we will delete your personal data within 30 days, except where retention is required by law.
          </p>

          <h2 style={h2Style}>7. Your Rights & Questions</h2>
          <p style={prose}>
            You may request access to, correction of, or deletion of your personal data at any time.
            For any privacy-related requests or questions, share them in our{' '}
            <Link to="/community" style={{ color: 'var(--color-paper-dark)' }}>community</Link>{' '}
            — we read and respond there.
          </p>

          <h2 style={h2Style}>8. Changes to This Policy</h2>
          <p style={prose}>
            We may update this Privacy Policy from time to time. When we do, we will update the
            "Last updated" date at the top of this page. Continued use of PaperPulse after any
            change constitutes acceptance of the updated policy.
          </p>
        </motion.div>
      </article>

      <ContentFooter />
    </div>
  </div>
);

export default PrivacyPage;
