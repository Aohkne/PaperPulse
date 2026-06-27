import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/** Scrolls the window to the top on every route change. Place inside <BrowserRouter>. */
const ScrollToTop = () => {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [pathname]);
  return null;
};

export default ScrollToTop;
