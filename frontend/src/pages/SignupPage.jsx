import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '@iconify/react';
import { authApi } from '@/features/auth/api/authApi';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { useGoogleIdentity } from '@/features/auth/hooks/useGoogleIdentity';
import { showError, showSuccess } from '@/shared/utils/toast';

const RESEND_COOLDOWN_S = 60;

// Card chrome shared with LoginPage — kept as plain style objects (not a
// shared component) since that's how LoginPage already does it. If a third
// auth page needs this, worth extracting into a shared AuthCard component.
const cardStyle = {
  width: '100%',
  maxWidth: '440px',
  background: 'var(--color-paper-surface)',
  border: '1px solid rgba(41, 17, 0, 0.08)',
  borderRadius: '16px',
  boxShadow: '0 1px 2px rgba(41, 17, 0, 0.04), 0 8px 24px rgba(41, 17, 0, 0.12)',
  padding: '40px',
  boxSizing: 'border-box',
};

const pageStyle = {
  minHeight: '100vh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '24px',
  position: 'relative',
};

const backLinkStyle = {
  position: 'absolute',
  top: 24,
  left: 28,
  background: 'none',
  border: 'none',
  fontFamily: "'Lora', 'Newsreader', serif",
  fontSize: '13px',
  color: 'var(--color-paper-mid)',
  cursor: 'pointer',
};

// Uppercase, letter-spaced labels — Lora instead of a sans-serif UI font
// (Thư's call on the login page, carried over here so both auth pages match).
const labelStyle = {
  display: 'block',
  fontFamily: "'Lora', 'Newsreader', serif",
  fontSize: '11px',
  fontWeight: 600,
  letterSpacing: '0.08em',
  textTransform: 'uppercase',
  color: 'var(--color-paper-mid)',
  marginBottom: '6px',
};

const inputStyle = {
  border: '1px solid rgba(41, 17, 0, 0.12)',
  borderRadius: '8px',
  padding: '11px 14px',
  background: 'var(--color-paper-bg)',
  fontFamily: "'Newsreader', serif",
  fontSize: '16px',
  color: 'var(--color-paper-dark)',
  width: '100%',
  boxSizing: 'border-box',
  outline: 'none',
  transition: 'border-color 0.15s ease',
};

const linkStyle = {
  fontFamily: "'Lora', 'Newsreader', serif",
  fontSize: '13px',
  color: 'var(--color-brand-500)',
  textDecoration: 'underline',
  cursor: 'pointer',
};

const primaryButtonStyle = (loading) => ({
  width: '100%',
  background: 'var(--color-paper-dark)',
  color: 'var(--color-paper-surface)',
  border: 'none',
  borderRadius: '10px',
  padding: '13px',
  fontFamily: "'Lora', 'Newsreader', serif",
  fontSize: '15px',
  fontWeight: 600,
  cursor: loading ? 'not-allowed' : 'pointer',
  marginTop: '8px',
  opacity: loading ? 0.7 : 1,
});

const focusBrand = (e) => (e.target.style.borderColor = 'var(--color-brand-500)');
const blurDefault = (e) => (e.target.style.borderColor = 'rgba(41, 17, 0, 0.12)');

const SignupPage = () => {
  const navigate = useNavigate();
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle);
  const theme = useThemeStore((s) => s.theme);
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [loading, setLoading] = useState(false);
  const [showVerification, setShowVerification] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [resendCooldown, setResendCooldown] = useState(0);
  const [resending, setResending] = useState(false);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const { prompt: promptGoogle } = useGoogleIdentity(async (idToken, nonce) => {
    setGoogleLoading(true);
    try {
      await loginWithGoogle(idToken, nonce);
      navigate('/app');
    } catch (err) {
      showError(err, 'Google sign-in failed. Please try again.');
    } finally {
      setGoogleLoading(false);
    }
  });

  const handleGoogleLogin = () => {
    setGoogleLoading(true);
    promptGoogle(() => {
      setGoogleLoading(false);
      showError(
        'Google sign-in popup was blocked. Please allow third-party cookies/popups and try again.'
      );
    });
  };

  // Cooldown ticks down once a verification email has been (re)sent, so the
  // user can't hammer Supabase's auth-email rate limit by clicking repeatedly.
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = setInterval(() => setResendCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(timer);
  }, [resendCooldown]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim() || !email.trim() || !password.trim() || !confirmPassword.trim()) {
      showError('Please fill in all fields.');
      return;
    }
    if (password !== confirmPassword) {
      showError('Passwords do not match.');
      return;
    }
    if (password.length < 6) {
      showError('Password must be at least 6 characters.');
      return;
    }
    setLoading(true);
    try {
      const redirectTo = `${window.location.origin}/login`;
      await authApi.register(email, password, redirectTo);
      setShowVerification(true);
      setResendCooldown(RESEND_COOLDOWN_S);
    } catch (err) {
      showError(err, 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    if (resendCooldown > 0 || resending) return;
    setResending(true);
    try {
      const redirectTo = `${window.location.origin}/login`;
      await authApi.register(email, password, redirectTo);
      showSuccess('Verification email sent again — check your inbox (and spam folder).');
      setResendCooldown(RESEND_COOLDOWN_S);
    } catch (err) {
      showError(err, "Couldn't resend the verification email right now.");
    } finally {
      setResending(false);
    }
  };

  if (showVerification) {
    return (
      <div style={pageStyle}>
        <div style={{ ...cardStyle, textAlign: 'center' }}>
          <div
            style={{
              width: 56,
              height: 56,
              borderRadius: '50%',
              background: 'var(--color-paper-bg)',
              border: '1px solid rgba(41, 17, 0, 0.08)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 24px',
              fontSize: '28px',
            }}
          >
            ✉
          </div>
          <h1
            style={{
              fontFamily: 'var(--font-inknut)',
              fontSize: '24px',
              color: 'var(--color-paper-dark)',
              margin: '0 0 12px',
              fontWeight: 500,
            }}
          >
            Check your email
          </h1>
          <p
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: '15px',
              color: 'var(--color-paper-mid)',
              margin: '0 0 8px',
              lineHeight: 1.6,
            }}
          >
            We sent a verification link to
          </p>
          <p
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: '15px',
              color: 'var(--color-paper-dark)',
              fontWeight: 600,
              margin: '0 0 24px',
            }}
          >
            {email}
          </p>
          <p
            style={{
              fontFamily: "'Newsreader', serif",
              fontSize: '14px',
              color: 'var(--color-paper-mid)',
              lineHeight: 1.6,
              margin: '0 0 32px',
            }}
          >
            Click the link in your email to activate your account. If you don't see it, check your
            spam folder.
          </p>

          <div
            style={{ display: 'flex', flexDirection: 'column', gap: '12px', alignItems: 'center' }}
          >
            <a
              href="https://mail.google.com"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '8px',
                width: '100%',
                boxSizing: 'border-box',
                background: 'var(--color-paper-dark)',
                color: 'var(--color-paper-surface)',
                border: 'none',
                borderRadius: '10px',
                padding: '13px',
                fontFamily: "'Lora', 'Newsreader', serif",
                fontSize: '15px',
                fontWeight: 600,
                cursor: 'pointer',
                textDecoration: 'none',
              }}
            >
              <Icon icon="mdi:email-outline" style={{ fontSize: '18px' }} />
              Open email app
            </a>
            <button
              type="button"
              onClick={handleResend}
              disabled={resendCooldown > 0 || resending}
              style={{
                background: 'none',
                border: 'none',
                color:
                  resendCooldown > 0 || resending
                    ? 'var(--color-paper-light)'
                    : 'var(--color-brand-500)',
                textDecoration: resendCooldown > 0 || resending ? 'none' : 'underline',
                fontFamily: "'Lora', 'Newsreader', serif",
                fontSize: '13px',
                cursor: resendCooldown > 0 || resending ? 'not-allowed' : 'pointer',
                padding: '4px',
              }}
            >
              {resending
                ? 'Resending…'
                : resendCooldown > 0
                  ? `Resend email (${resendCooldown}s)`
                  : "Didn't get it? Resend email"}
            </button>
            <button
              onClick={() => navigate('/login')}
              style={{
                width: '100%',
                boxSizing: 'border-box',
                background: 'var(--color-paper-bg)',
                color: 'var(--color-paper-dark)',
                border: '1px solid rgba(41, 17, 0, 0.12)',
                borderRadius: '10px',
                padding: '11px',
                fontFamily: "'Lora', 'Newsreader', serif",
                fontSize: '14px',
                cursor: 'pointer',
              }}
            >
              Go to sign in
            </button>
          </div>

          <p
            style={{
              fontFamily: "'Lora', 'Newsreader', serif",
              fontSize: '13px',
              color: 'var(--color-paper-mid)',
              marginTop: '20px',
            }}
          >
            Wrong email?{' '}
            <span onClick={() => setShowVerification(false)} style={linkStyle}>
              Go back
            </span>
          </p>
        </div>
      </div>
    );
  }

  return (
    // No explicit background — lets body's dot-grain texture (index.css)
    // show through around the card, same as LoginPage.
    <div style={pageStyle}>
      <button onClick={() => navigate('/')} style={backLinkStyle}>
        ← PaperPulse
      </button>

      <div style={cardStyle}>
        <img
          src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
          alt="PaperPulse"
          style={{ height: '32px', width: 'auto', display: 'block', marginBottom: '20px' }}
        />

        <h1
          style={{
            fontFamily: 'var(--font-inknut)',
            fontSize: '24px',
            fontWeight: 500,
            color: 'var(--color-paper-dark)',
            margin: '0 0 24px',
          }}
        >
          Start your research.
        </h1>

        <form
          onSubmit={handleSubmit}
          style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}
        >
          <div>
            <label style={labelStyle}>Full name</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onFocus={focusBrand}
              onBlur={blurDefault}
              style={inputStyle}
            />
          </div>

          <div>
            <label style={labelStyle}>Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              onFocus={focusBrand}
              onBlur={blurDefault}
              style={inputStyle}
            />
          </div>

          <div>
            <label style={labelStyle}>Password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={focusBrand}
                onBlur={blurDefault}
                style={{ ...inputStyle, paddingRight: '40px' }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                tabIndex={-1}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '4px',
                  color: 'var(--color-paper-mid)',
                  display: 'flex',
                  alignItems: 'center',
                  lineHeight: 0,
                }}
              >
                <Icon
                  icon={showPassword ? 'mdi:eye-off' : 'mdi:eye'}
                  style={{ fontSize: '18px' }}
                />
              </button>
            </div>
          </div>

          <div>
            <label style={labelStyle}>Confirm password</label>
            <div style={{ position: 'relative' }}>
              <input
                type={showConfirm ? 'text' : 'password'}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                onFocus={focusBrand}
                onBlur={blurDefault}
                style={{ ...inputStyle, paddingRight: '40px' }}
              />
              <button
                type="button"
                onClick={() => setShowConfirm(!showConfirm)}
                tabIndex={-1}
                style={{
                  position: 'absolute',
                  right: '10px',
                  top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '4px',
                  color: 'var(--color-paper-mid)',
                  display: 'flex',
                  alignItems: 'center',
                  lineHeight: 0,
                }}
              >
                <Icon icon={showConfirm ? 'mdi:eye-off' : 'mdi:eye'} style={{ fontSize: '18px' }} />
              </button>
            </div>
          </div>

          <button type="submit" disabled={loading} style={primaryButtonStyle(loading)}>
            {loading ? 'Creating account…' : 'Create account'}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '4px 0' }}>
            <div style={{ flex: 1, height: '1px', background: 'rgba(41, 17, 0, 0.08)' }} />
            <span
              style={{
                fontSize: '12px',
                color: 'var(--color-paper-mid)',
                fontFamily: "'Lora', 'Newsreader', serif",
              }}
            >
              or continue with
            </span>
            <div style={{ flex: 1, height: '1px', background: 'rgba(41, 17, 0, 0.08)' }} />
          </div>

          <button
            type="button"
            onClick={handleGoogleLogin}
            disabled={googleLoading}
            style={{
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '10px',
              padding: '11px',
              background: 'var(--color-paper-bg)',
              border: '1px solid rgba(41, 17, 0, 0.12)',
              borderRadius: '10px',
              cursor: googleLoading ? 'not-allowed' : 'pointer',
              opacity: googleLoading ? 0.7 : 1,
              fontFamily: "'Lora', 'Newsreader', serif",
              fontSize: '14px',
              color: 'var(--color-paper-dark)',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path
                fill="#4285F4"
                d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"
              />
              <path
                fill="#34A853"
                d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"
              />
              <path
                fill="#FBBC05"
                d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.55 0 9s.348 2.825.957 4.039l3.007-2.332z"
              />
              <path
                fill="#EA4335"
                d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z"
              />
            </svg>
            {googleLoading ? 'Signing up…' : 'Sign up with Google'}
          </button>
        </form>

        <p
          style={{
            fontFamily: "'Lora', 'Newsreader', serif",
            fontSize: '13px',
            color: 'var(--color-paper-mid)',
            textAlign: 'center',
            marginTop: '24px',
          }}
        >
          Already have an account?{' '}
          <span onClick={() => navigate('/login')} style={linkStyle}>
            Sign in
          </span>
        </p>
      </div>
    </div>
  );
};

export default SignupPage;
