import { useNavigate } from 'react-router-dom';
import { useThemeStore } from '@/shared/store/useThemeStore';

const AppLayout = ({ children }) => {
  const navigate = useNavigate();
  const theme = useThemeStore((s) => s.theme);

  const isDark =
    theme === 'dark' ||
    (theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);

  return (
    <div className="h-screen flex flex-col bg-[#808847]">
      <header className="w-full bg-[#6b6e30] border-b border-[#52551f] shrink-0">
        <div className="max-w-5xl mx-auto px-6 py-3 flex items-center gap-3">
          <button
            onClick={() => navigate('/')}
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              display: 'flex',
              alignItems: 'center',
            }}
          >
            <img
              src={isDark ? '/paperpulse-logo_dark.png' : '/paperpulse-logo_light.png'}
              alt="PaperPulse"
              className="bg-cover"
              style={{ height: '80px', width: 'auto' }}
            />
          </button>
        </div>
      </header>

      <main className="flex-1 w-full max-w-5xl mx-auto flex flex-col overflow-hidden">
        {children}
      </main>
    </div>
  );
};

export default AppLayout;
