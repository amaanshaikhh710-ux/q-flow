/**
 * Canonical Date Utilities for Q-FLOW.
 * 
 * Strict Single-Source-of-Truth:
 * API, Database, and Query parameter dates must strictly follow YYYY-MM-DD (e.g. "2026-09-22").
 * All calendar-only operations MUST NOT convert calendar dates into local midnight timestamps,
 * which cause timezone drift across IST, UTC, and other client environments.
 * 
 * Corrupted years (< 2000 or > 2100, such as 0002 or 1902) are rejected immediately.
 */

const CANONICAL_DATE_REGEX = /^(\d{4})-(\d{2})-(\d{2})$/;

const MONTH_NAMES_LONG = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

const MONTH_NAMES_SHORT = [
  'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'
];

/**
 * Validate that a string is a strict canonical calendar date: YYYY-MM-DD
 * with year between 2000 and 2100.
 */
export function isValidCanonicalDate(dateStr: string | null | undefined): boolean {
  if (!dateStr || typeof dateStr !== 'string') return false;
  const match = CANONICAL_DATE_REGEX.exec(dateStr.trim());
  if (!match) return false;

  const year = parseInt(match[1], 10);
  const month = parseInt(match[2], 10);
  const day = parseInt(match[3], 10);

  if (year < 2000 || year > 2100) return false;
  if (month < 1 || month > 12) return false;
  if (day < 1 || day > 31) return false;

  return true;
}

/**
 * Normalize and sanitize any date input.
 * If valid canonical YYYY-MM-DD, returns trimmed string.
 * Otherwise returns null.
 */
export function normalizeToCanonicalDate(dateStr: string | null | undefined): string | null {
  if (!dateStr) return null;
  const trimmed = dateStr.trim();
  return isValidCanonicalDate(trimmed) ? trimmed : null;
}

/**
 * Format a canonical YYYY-MM-DD string into a human-readable display string
 * WITHOUT using JavaScript `new Date(y, m-1, d)` (which re-interprets 2-digit years and timezone).
 * 
 * Examples:
 * - "2026-09-22", "long"   -> "22 September 2026"
 * - "2026-09-22", "medium" -> "22 Sep 2026"
 * - "2026-09-22", "short"  -> "22/09/2026"
 */
export function formatCanonicalDateDisplay(
  dateStr: string | null | undefined,
  format: 'long' | 'medium' | 'short' = 'medium'
): string {
  if (!dateStr) return '—';
  const match = CANONICAL_DATE_REGEX.exec(dateStr.trim());
  if (!match) return dateStr;

  const year = match[1];
  const monthNum = parseInt(match[2], 10);
  const dayNum = parseInt(match[3], 10);

  if (monthNum < 1 || monthNum > 12) return dateStr;

  if (format === 'short') {
    return `${String(dayNum).padStart(2, '0')}/${String(monthNum).padStart(2, '0')}/${year}`;
  }

  const monthName = format === 'long'
    ? MONTH_NAMES_LONG[monthNum - 1]
    : MONTH_NAMES_SHORT[monthNum - 1];

  return `${dayNum} ${monthName} ${year}`;
}

/**
 * Return today's calendar date in hospital timezone (Asia/Kolkata) as YYYY-MM-DD.
 * Uses 'en-CA' locale which outputs YYYY-MM-DD natively.
 */
export function getHospitalTodayDateString(): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-CA', {
      timeZone: 'Asia/Kolkata',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
    });
    return formatter.format(new Date());
  } catch {
    // Fallback if Intl unavailable
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  }
}

/**
 * Add or subtract calendar days from a YYYY-MM-DD date string without local timezone distortion.
 */
export function addDaysToCanonicalDate(dateStr: string, days: number): string {
  const match = CANONICAL_DATE_REGEX.exec(dateStr.trim());
  if (!match) return dateStr;

  const y = parseInt(match[1], 10);
  const m = parseInt(match[2], 10) - 1;
  const d = parseInt(match[3], 10);

  // UTC calculations prevent daylight saving or local midnight shifts
  const utcDate = new Date(Date.UTC(y, m, d + days));
  const newY = utcDate.getUTCFullYear();
  const newM = String(utcDate.getUTCMonth() + 1).padStart(2, '0');
  const newD = String(utcDate.getUTCDate()).padStart(2, '0');

  return `${newY}-${newM}-${newD}`;
}

/**
 * Split a canonical date into { year, month (1-12), day (1-31) }
 */
export function parseCanonicalDateComponents(dateStr: string): { year: number; month: number; day: number } | null {
  const match = CANONICAL_DATE_REGEX.exec(dateStr.trim());
  if (!match) return null;
  return {
    year: parseInt(match[1], 10),
    month: parseInt(match[2], 10),
    day: parseInt(match[3], 10),
  };
}

/**
 * Generate a grid of calendar days for a specific year and month (1-12)
 * for custom interactive calendar pickers.
 */
export interface CalendarGridDay {
  dateStr: string;
  dayNumber: number;
  isCurrentMonth: boolean;
  isToday: boolean;
  isSelected: boolean;
}

export function buildMonthCalendarGrid(
  year: number,
  month: number, // 1-indexed (1 = Jan, 12 = Dec)
  selectedDateStr: string | null,
  todayDateStr: string
): CalendarGridDay[] {
  const days: CalendarGridDay[] = [];

  // First day of month
  const firstDayUtc = new Date(Date.UTC(year, month - 1, 1));
  // 0 = Sun, 1 = Mon ... convert to Monday-first: Mon=0, Tue=1 ... Sun=6
  const firstDayOfWeek = (firstDayUtc.getUTCDay() + 6) % 7;

  // Days in current month
  const daysInMonth = new Date(Date.UTC(year, month, 0)).getUTCDate();
  // Days in previous month
  const daysInPrevMonth = new Date(Date.UTC(year, month - 1, 0)).getUTCDate();

  // Trailing days from previous month
  for (let i = firstDayOfWeek - 1; i >= 0; i--) {
    const prevDay = daysInPrevMonth - i;
    const prevMonthDate = new Date(Date.UTC(year, month - 2, prevDay));
    const py = prevMonthDate.getUTCFullYear();
    const pm = String(prevMonthDate.getUTCMonth() + 1).padStart(2, '0');
    const pd = String(prevDay).padStart(2, '0');
    const dStr = `${py}-${pm}-${pd}`;

    days.push({
      dateStr: dStr,
      dayNumber: prevDay,
      isCurrentMonth: false,
      isToday: dStr === todayDateStr,
      isSelected: dStr === selectedDateStr,
    });
  }

  // Days of current month
  for (let d = 1; d <= daysInMonth; d++) {
    const yStr = String(year);
    const mStr = String(month).padStart(2, '0');
    const dStr = `${yStr}-${mStr}-${String(d).padStart(2, '0')}`;

    days.push({
      dateStr: dStr,
      dayNumber: d,
      isCurrentMonth: true,
      isToday: dStr === todayDateStr,
      isSelected: dStr === selectedDateStr,
    });
  }

  // Leading days of next month to complete standard 35 or 42 grid cells
  const remaining = (7 - (days.length % 7)) % 7;
  for (let d = 1; d <= remaining; d++) {
    const nextMonthDate = new Date(Date.UTC(year, month, d));
    const ny = nextMonthDate.getUTCFullYear();
    const nm = String(nextMonthDate.getUTCMonth() + 1).padStart(2, '0');
    const nd = String(d).padStart(2, '0');
    const dStr = `${ny}-${nm}-${nd}`;

    days.push({
      dateStr: dStr,
      dayNumber: d,
      isCurrentMonth: false,
      isToday: dStr === todayDateStr,
      isSelected: dStr === selectedDateStr,
    });
  }

  return days;
}

/**
 * Convert various date-like inputs into a canonical YYYY-MM-DD string.
 * Accepts canonical strings, Date objects, or null/undefined.
 * Returns null for invalid or out-of-range years.
 */
export function toCanonicalDateString(dateLike: string | Date | null | undefined): string | null {
  if (!dateLike) return null;
  if (dateLike instanceof Date) {
    // Use UTC to avoid timezone shifts
    const y = dateLike.getUTCFullYear();
    const m = String(dateLike.getUTCMonth() + 1).padStart(2, '0');
    const d = String(dateLike.getUTCDate()).padStart(2, '0');
    const res = `${y}-${m}-${d}`;
    return isValidCanonicalDate(res) ? res : null;
  }
  if (typeof dateLike === 'string') {
    const trimmed = dateLike.trim();
    if (isValidCanonicalDate(trimmed)) return trimmed;

    // Try to parse ISO-like strings
    // e.g. Date().toISOString() -> 2026-09-22T00:00:00.000Z
    const isoMatch = /^\s*(\d{4})-(\d{2})-(\d{2})/.exec(trimmed);
    if (isoMatch) {
      const candidate = `${isoMatch[1]}-${isoMatch[2]}-${isoMatch[3]}`;
      return isValidCanonicalDate(candidate) ? candidate : null;
    }
  }
  return null;
}
