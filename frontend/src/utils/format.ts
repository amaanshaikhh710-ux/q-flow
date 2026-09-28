/**
 * Formatting utilities for Q-FLOW UI.
 * All ETA / time values come from the backend — never computed here.
 */

/** Format a UTC ISO datetime string to local time (HH:MM) in hospital timezone. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleTimeString([], {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

/** Format a UTC ISO datetime string to local date + time in hospital timezone. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString([], {
      timeZone: 'Asia/Kolkata',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '—';
  }
}

/** Format duration in minutes to "Xh Ym" or "X min". */
export function formatDuration(minutes: number | null | undefined): string {
  if (minutes == null) return '—';
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m === 0 ? `${h}h` : `${h}h ${m}m`;
}

/** Format distance in meters to "X.X km" or "X m". */
export function formatDistance(meters: number | null | undefined): string {
  if (meters == null) return '—';
  if (meters >= 1000) return `${(meters / 1000).toFixed(1)} km`;
  return `${meters} m`;
}

/** Returns a time window string like "2:30 PM – 2:50 PM". */
export function formatTimeWindow(
  start: string | null | undefined,
  end: string | null | undefined
): string {
  const s = formatTime(start);
  const e = formatTime(end);
  if (s === '—' || e === '—') return '—';
  return `${s} – ${e}`;
}

/** Returns relative "just now", "X min ago", "Xh ago", or formatted date. */
export function formatRelative(iso: string | null | undefined): string {
  if (!iso) return '—';
  try {
    const target = new Date(iso).getTime();
    if (isNaN(target)) return '—';
    const diffMs = target - Date.now();
    const diffMin = Math.round(diffMs / 60000);

    if (diffMin === 0) return 'just now';
    if (diffMin === -1) return '1 min ago';
    if (diffMin < -1 && diffMin > -60) return `${Math.abs(diffMin)} mins ago`;
    if (diffMin <= -60 && diffMin > -1440) {
      const h = Math.floor(Math.abs(diffMin) / 60);
      return `${h}h ago`;
    }
    if (diffMin <= -1440) {
      return formatDateTime(iso);
    }
    // Future times:
    if (diffMin === 1) return 'in 1 min';
    if (diffMin < 60) return `in ${diffMin} mins`;
    if (diffMin < 1440) {
      const h = Math.floor(diffMin / 60);
      return `in ${h}h`;
    }
    return formatDateTime(iso);
  } catch {
    return '—';
  }
}

/** Cleanly formats a doctor's name, preventing duplicate "Dr. Dr." prefixes. */
export function formatDoctorName(name: string | null | undefined, fallback: string = 'Attending Specialist'): string {
  if (!name) return fallback.startsWith('Dr.') ? fallback : `Dr. ${fallback}`;
  const clean = name.replace(/^(?:dr\.?|\s+)+/i, '').trim();
  return clean ? `Dr. ${clean}` : (fallback.startsWith('Dr.') ? fallback : `Dr. ${fallback}`);
}
