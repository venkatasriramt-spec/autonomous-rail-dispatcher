import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';

/**
 * ScrollToTop component
 * Automatically resets window scroll position to the top whenever
 * the route pathname changes, ensuring newly opened pages start at the top.
 */
export default function ScrollToTop() {
  const { pathname, hash } = useLocation();

  useEffect(() => {
    if (hash) {
      const targetId = hash.replace(/^#/, '');
      const scrollToHashElement = () => {
        const elem = document.getElementById(targetId);
        if (elem) {
          elem.scrollIntoView({ behavior: 'smooth', block: 'start' });
          return true;
        }
        return false;
      };

      // Attempt to scroll immediately, and retry if the DOM element is still mounting
      if (!scrollToHashElement()) {
        const timer = setTimeout(scrollToHashElement, 100);
        return () => clearTimeout(timer);
      }
    } else {
      // Reset window scroll position instantly on regular route transitions
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
    }
  }, [pathname, hash]);

  return null;
}
