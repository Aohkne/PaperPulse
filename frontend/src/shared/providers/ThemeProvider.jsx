import { useEffect } from 'react';
import { useThemeStore } from '@/shared/store/useThemeStore';

export function ThemeProvider({ children }) {
  const theme = useThemeStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;

    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)');
      const apply = (e) => root.classList.toggle('dark', e.matches);
      apply(mq);
      mq.addEventListener('change', apply);
      return () => mq.removeEventListener('change', apply);
    }

    root.classList.toggle('dark', theme === 'dark');
  }, [theme]);

  return children;
}
