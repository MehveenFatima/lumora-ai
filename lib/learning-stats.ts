import type { LearningActivity } from '@/lib/types/domain'

function toDayKey(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

/**
 * Counts consecutive days (ending today, or yesterday if nothing has happened yet today)
 * that have at least one recorded learning activity.
 */
export function computeStudyStreak(activities: LearningActivity[]): number {
  const activeDays = new Set<string>()
  for (const act of activities) {
    const raw = act.occurredAt || act.timestamp
    if (!raw) continue
    const d = new Date(raw)
    if (!isNaN(d.getTime())) activeDays.add(toDayKey(d))
  }
  if (activeDays.size === 0) return 0

  const cursor = new Date()
  if (!activeDays.has(toDayKey(cursor))) {
    cursor.setDate(cursor.getDate() - 1)
    if (!activeDays.has(toDayKey(cursor))) return 0
  }

  let streak = 0
  while (activeDays.has(toDayKey(cursor))) {
    streak++
    cursor.setDate(cursor.getDate() - 1)
  }
  return streak
}
