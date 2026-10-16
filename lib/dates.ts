/** Calendar-date helpers that use the learner's local date (not UTC). */

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

/** Today's local date as YYYY-MM-DD. */
export function localToday(): string {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

/** Adds whole days to a YYYY-MM-DD date. */
export function addDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const date = new Date(y, m - 1, d + days)
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** "31 Jul 2026" */
export function formatLongDate(isoDate?: string | null): string {
  if (!isoDate) return ''
  const [y, m, d] = isoDate.split('-').map(Number)
  if (!y || !m || !d) return isoDate
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })
}

export function isPastDate(isoDate?: string | null): boolean {
  return Boolean(isoDate) && (isoDate as string) < localToday()
}
