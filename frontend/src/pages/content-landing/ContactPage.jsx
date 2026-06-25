import { useState } from 'react';
import { motion } from 'framer-motion';
import { Icon } from '@iconify/react';
import ContentNavbar from './_shared/ContentNavbar';
import ContentFooter from './_shared/ContentFooter';

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 22 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.5, ease: [0.22, 1, 0.36, 1], delay },
});

// TODO: replace with actual team email before shipping
const TEAM_EMAIL = 'paperpulse.c2app069@gmail.com';

const inputStyle = {
  width: '100%',
  padding: '10px 14px',
  fontFamily: 'Georgia, serif', fontSize: 15,
  color: 'var(--color-paper-dark)',
  background: 'var(--color-paper-bg)',
  border: '1px solid var(--color-paper-surface)',
  borderRadius: 2,
  outline: 'none',
  boxSizing: 'border-box',
  transition: 'border-color 0.15s',
};

const labelStyle = {
  display: 'block',
  fontFamily: 'Georgia, serif', fontSize: 13, fontWeight: 600,
  color: 'var(--color-paper-mid)',
  letterSpacing: '0.05em', textTransform: 'uppercase',
  marginBottom: 6,
};

const ContactPage = () => {
  const [submitted, setSubmitted] = useState(false);
  const [form, setForm] = useState({ name: '', email: '', message: '' });

  const handleChange = (e) => setForm((f) => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = (e) => {
    e.preventDefault();
    const subject = encodeURIComponent(`PaperPulse message from ${form.name}`);
    const body = encodeURIComponent(`Name: ${form.name}\nEmail: ${form.email}\n\n${form.message}`);
    window.location.href = `mailto:${TEAM_EMAIL}?subject=${subject}&body=${body}`;
    setSubmitted(true);
  };

  return (
    <div style={{ fontFamily: 'Georgia, serif', background: 'var(--color-paper-bg)', minHeight: '100vh' }}>
      <ContentNavbar />

      <div style={{ paddingTop: 57 }}>
        <section style={{ maxWidth: 640, margin: '0 auto', padding: '80px 24px 80px' }}>
          <motion.p {...fadeUp(0.1)} style={{
            fontSize: 13, color: 'var(--color-paper-light)',
            letterSpacing: '0.12em', textTransform: 'uppercase', margin: '0 0 16px',
          }}>
            Contact
          </motion.p>

          <motion.h1 {...fadeUp(0.2)} style={{
            fontFamily: 'var(--font-inknut)', fontSize: 42, fontWeight: 500,
            color: 'var(--color-paper-dark)', margin: '0 0 16px', lineHeight: 1.2,
          }}>
            Get in touch
          </motion.h1>

          <motion.p {...fadeUp(0.3)} style={{
            fontSize: 17, lineHeight: 1.8, color: 'var(--color-paper-mid)', margin: '0 0 48px',
          }}>
            Have a question, bug report, or just want to say hello? We'd love to hear from you.
          </motion.p>

          {submitted ? (
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              style={{
                padding: '40px 32px', textAlign: 'center',
                background: 'var(--color-paper-surface)', borderRadius: 4,
              }}
            >
              <Icon
                icon="mdi:check-circle-outline"
                style={{ fontSize: 40, color: 'var(--color-paper-mid)', display: 'block', margin: '0 auto 16px' }}
              />
              <p style={{
                fontFamily: 'var(--font-inknut)', fontSize: 20,
                color: 'var(--color-paper-dark)', margin: '0 0 8px',
              }}>
                Thanks for reaching out!
              </p>
              <p style={{ fontSize: 15, color: 'var(--color-paper-mid)', margin: 0 }}>
                We'll get back to you as soon as we can.
              </p>
            </motion.div>
          ) : (
            <motion.form {...fadeUp(0.4)} onSubmit={handleSubmit}>
              <div style={{ marginBottom: 20 }}>
                <label style={labelStyle}>Name</label>
                <input
                  name="name" required value={form.name} onChange={handleChange}
                  placeholder="Your name"
                  style={inputStyle}
                  onFocus={(e) => { e.target.style.borderColor = 'var(--color-paper-mid)'; }}
                  onBlur={(e) => { e.target.style.borderColor = 'var(--color-paper-surface)'; }}
                />
              </div>

              <div style={{ marginBottom: 20 }}>
                <label style={labelStyle}>Email</label>
                <input
                  name="email" type="email" required value={form.email} onChange={handleChange}
                  placeholder="your@email.com"
                  style={inputStyle}
                  onFocus={(e) => { e.target.style.borderColor = 'var(--color-paper-mid)'; }}
                  onBlur={(e) => { e.target.style.borderColor = 'var(--color-paper-surface)'; }}
                />
              </div>

              <div style={{ marginBottom: 28 }}>
                <label style={labelStyle}>Message</label>
                <textarea
                  name="message" required value={form.message} onChange={handleChange}
                  placeholder="Tell us what's on your mind..."
                  rows={5}
                  style={{ ...inputStyle, resize: 'vertical', lineHeight: 1.7 }}
                  onFocus={(e) => { e.target.style.borderColor = 'var(--color-paper-mid)'; }}
                  onBlur={(e) => { e.target.style.borderColor = 'var(--color-paper-surface)'; }}
                />
              </div>

              <button
                type="submit"
                style={{
                  background: 'var(--color-paper-dark)', border: 'none',
                  color: 'var(--color-paper-bg)', padding: '11px 28px',
                  borderRadius: 2, fontFamily: 'Georgia, serif', fontSize: 16,
                  cursor: 'pointer', width: '100%',
                }}
              >
                Send message →
              </button>
            </motion.form>
          )}

          {/* Email fallback */}
          <motion.div {...fadeUp(0.5)} style={{ marginTop: 40, textAlign: 'center' }}>
            <p style={{ fontSize: 14, color: 'var(--color-paper-light)', margin: '0 0 6px' }}>
              Prefer email?
            </p>
            <a
              href={`mailto:${TEAM_EMAIL}`}
              style={{
                fontFamily: 'Georgia, serif', fontSize: 15,
                color: 'var(--color-paper-mid)', textDecoration: 'none',
                borderBottom: '1px solid var(--color-paper-surface)',
                paddingBottom: 1,
              }}
            >
              {TEAM_EMAIL}
            </a>
          </motion.div>
        </section>

        <ContentFooter />
      </div>
    </div>
  );
};

export default ContactPage;
