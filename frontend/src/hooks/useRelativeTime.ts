import { useState, useEffect } from 'react';
import { formatRelative } from '../utils/format';

/**
 * Hook that returns an auto-updating relative timestamp (e.g. "just now" -> "1 min ago")
 * refreshed every 10 seconds without needing a manual page reload.
 */
export function useRelativeTime(iso: string | null | undefined, intervalMs = 10000): string {
  const [relativeText, setRelativeText] = useState(() => formatRelative(iso));

  useEffect(() => {
    setRelativeText(formatRelative(iso));
    if (!iso) return;

    const timer = setInterval(() => {
      setRelativeText(formatRelative(iso));
    }, intervalMs);

    return () => clearInterval(timer);
  }, [iso, intervalMs]);

  return relativeText;
}
