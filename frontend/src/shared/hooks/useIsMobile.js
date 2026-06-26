import { useEffect, useState } from 'react';

/**
 * useIsMobile — tracks whether the viewport is at or below `breakpoint`.
 * Defaults to 768px (tablet/mobile boundary used across the app).
 */
export function useIsMobile(breakpoint = 768) {
  const query = `(max-width: ${breakpoint}px)`;
  const [isMobile, setIsMobile] = useState(
    () => typeof window !== 'undefined' && window.matchMedia(query).matches
  );

  useEffect(() => {
    const mql = window.matchMedia(query);
    const handler = (e) => setIsMobile(e.matches);
    mql.addEventListener('change', handler);
    setIsMobile(mql.matches);
    return () => mql.removeEventListener('change', handler);
  }, [query]);

  return isMobile;
}
