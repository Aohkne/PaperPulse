import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Icon } from '@iconify/react';
import { useAuthStore } from '@/features/auth/store/useAuthStore';
import { useThemeStore } from '@/shared/store/useThemeStore';
import { useGoogleIdentity } from '@/features/auth/hooks/useGoogleIdentity';
import { showError } from '@/shared/utils/toast';

const LoginPage = () => {
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);
  const loginWithGoogle = useAuthStore((s) => s.loginWithGoogle);
  const theme = useThemeStore((s) => s.theme);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  const inputStyle = {
    border: '1px solid var(--color-paper-surface)',
    borderRadius: '2px',
    padding: '10px 12px',
    background: 'var(--color-paper-bg)',
    fontFamily: "'Noto Serif', serif",
    fontSize: '16px',
    color: 'var(--color-paper-dark)',
    width: '100%',
    boxSizing: 'border-box',
    outline: 'none',
  };

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
      showError('Google sign-in popup was blocked. Please allow third-party cookies/popups and try again.');
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email.trim() || !password.trim()) {
      showError('Please enter your email and password.');
      return;
    }
    setLoading(true);
    try {
      await login(email, password);
      navigate('/app');
    } catch (err) {
      showError(err, 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ background: 'var(--color-paper-bg)', minHeight: '100vh', fontFamily: "'Noto Serif', serif" }}>
      <button
        onClick={() => navigate('/')}
        style={{
          position: 'absolute',
          top: 0,
          left: 0,
          padding: '20px 28px',
          background: 'none',
          border: 'none',
          fontFamily: "'Noto Serif', serif",
          fontSize: '15px',
          color: 'var(--color-paper-mid)',
          cursor: 'pointer',
        }}
      >
        ← PaperPulse
      </button>

      <div style={{ maxWidth: '400px', margin: '0 auto', paddingTop: '80px', paddingBottom: '60px', paddingLeft: '24px', paddingRight: '24px' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '0' }}>
          <img
            src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
            alt="PaperPulse"
            style={{ height: '48px', width: 'auto' }}
          />
        </div>

        <h1 style={{
          fontFamily: 'var(--font-inknut)',
          fontSize: '26px',
          color: 'var(--color-paper-dark)',
          textAlign: 'center',
          margin: '20px 0 8px',
          fontWeight: 500,
        }}>
          Welcome back
        </h1>
        <p style={{ fontFamily: "'Noto Serif', serif", fontSize: '15px', color: 'var(--color-paper-mid)', textAlign: 'center', margin: '0 0 32px' }}>
          Sign in to continue your research
        </p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontFamily: "'Noto Serif', serif", fontSize: '14px', color: 'var(--color-paper-mid)', marginBottom: '4px' }}>
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onFocus={(e) => e.target.style.borderColor = 'var(--color-paper-mid)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--color-paper-surface)'}
              style={inputStyle}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontFamily: "'Noto Serif', serif", fontSize: '14px', color: 'var(--color-paper-mid)', marginBottom: '4px' }}>
              Password
            </label>
            <div style={{ position: 'relative' }}>
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                onFocus={(e) => e.target.style.borderColor = 'var(--color-paper-mid)'}
                onBlur={(e) => e.target.style.borderColor = 'var(--color-paper-surface)'}
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
                <Icon icon={showPassword ? 'mdi:eye-off' : 'mdi:eye'} style={{ fontSize: '18px' }} />
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            style={{
              width: '100%',
              background: 'var(--color-paper-dark)',
              color: 'var(--color-paper-bg)',
              border: 'none',
              borderRadius: '2px',
              padding: '11px',
              fontFamily: "'Noto Serif', serif",
              fontSize: '17px',
              cursor: loading ? 'not-allowed' : 'pointer',
              marginTop: '4px',
              opacity: loading ? 0.7 : 1,
            }}
          >
            {loading ? 'Signing in…' : 'Sign in →'}
          </button>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px', margin: '4px 0' }}>
            <div style={{ flex: 1, height: '1px', background: 'var(--color-paper-surface)' }} />
            <span style={{ fontSize: '13px', color: 'var(--color-paper-mid)', fontFamily: "'Noto Serif', serif" }}>
              or continue with
            </span>
            <div style={{ flex: 1, height: '1px', background: 'var(--color-paper-surface)' }} />
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
              padding: '10px',
              background: 'var(--color-paper-bg)',
              border: '1px solid var(--color-paper-surface)',
              borderRadius: '2px',
              cursor: googleLoading ? 'not-allowed' : 'pointer',
              opacity: googleLoading ? 0.7 : 1,
              fontFamily: "'Noto Serif', serif",
              fontSize: '15px',
              color: 'var(--color-paper-dark)',
            }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.874 2.684-6.615z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332C2.438 15.983 5.482 18 9 18z"/>
              <path fill="#FBBC05" d="M3.964 10.707c-.18-.54-.282-1.117-.282-1.707s.102-1.167.282-1.707V4.961H.957C.347 6.175 0 7.55 0 9s.348 2.825.957 4.039l3.007-2.332z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0 5.482 0 2.438 2.017.957 4.961L3.964 7.293C4.672 5.166 6.656 3.58 9 3.58z"/>
            </svg>
            {googleLoading ? 'Signing in…' : 'Sign in with Google'}
          </button>
        </form>

        <p style={{ fontFamily: "'Noto Serif', serif", fontSize: '15px', color: 'var(--color-paper-mid)', textAlign: 'center', marginTop: '20px' }}>
          Don't have an account?{' '}
          <span
            onClick={() => navigate('/signup')}
            style={{ color: 'var(--color-paper-dark)', textDecoration: 'underline', cursor: 'pointer' }}
          >
            Get started
          </span>
        </p>
      </div>
    </div>
  );
};

export default LoginPage;
