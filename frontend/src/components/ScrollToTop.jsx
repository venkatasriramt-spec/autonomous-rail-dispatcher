import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * ScrollToTop component
 * Automatically resets window scroll position to the top whenever
 * the route pathname changes, ensuring newly opened pages start at the top.
 */
export default function ScrollToTop() {
  const { pathname } = useLocation();

  useEffect(() => {
    // Reset window scroll position instantly on route transition
    window.scrollTo({
      top: 0,
      left: 0,
      behavior: 'instant'
    });

    // Ensure documentElement and document.body scroll positions are also reset
    if (document.documentElement) {
      document.documentElement.scrollTop = 0;
    }
    if (document.body) {
      document.body.scrollTop = 0;
    }
  }, [pathname]);

  return null;
}
