import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export const useThemeStore = create(
  persist(
    (set, get) => ({
      theme: 'system', // 'light' | 'dark' | 'system'

      setTheme: (theme) => set({ theme }),

      toggleTheme: () => {
        const current = get().theme;
        // When toggling from system, resolve actual value first
        const resolved = current === 'system'
          ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
          : current;
        set({ theme: resolved === 'dark' ? 'light' : 'dark' });
      },
    }),
    { name: 'theme-storage' }
  )
);
