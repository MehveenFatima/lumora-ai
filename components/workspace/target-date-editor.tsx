'use client'

import { useState } from 'react'
import { CalendarClock, Loader2 } from 'lucide-react'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import { addDays, localToday } from '@/lib/dates'
import { cn } from '@/lib/utils'

/** Date picker that saves a new target completion date (today or later) for a workspace. */
export function TargetDateEditor({
  workspaceId,
  currentDate,
  onSaved,
  compact,
}: {
  workspaceId: string
  currentDate?: string | null
  onSaved: (newDate: string) => void
  compact?: boolean
}) {
  const today = localToday()
  const [value, setValue] = useState(currentDate && currentDate >= today ? currentDate : addDays(today, 30))
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const invalid = !value || value < today

  async function save() {
    if (invalid) {
      setError('Choose today or a later date.')
      return
    }
    setSaving(true)
    setError(null)
    try {
      await tutorApiClient.updateWorkspace(workspaceId, { targetDate: value })
      onSaved(value)
    } catch (err: any) {
      setError(err?.message || 'Could not save the new date.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className={cn('flex flex-col gap-2 sm:flex-row sm:items-center', compact && 'sm:flex-row')}>
        <label className="relative flex-1">
          <span className="sr-only">New target completion date</span>
          <CalendarClock className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <input
            type="date"
            min={today}
            value={value}
            onChange={(e) => {
              setValue(e.target.value)
              setError(null)
            }}
            aria-invalid={invalid}
            className="h-10 w-full rounded-xl border border-border bg-background pl-9 pr-3 text-sm text-foreground outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/20"
          />
        </label>
        <button
          type="button"
          onClick={save}
          disabled={saving || invalid || value === currentDate}
          className="inline-flex h-10 shrink-0 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {saving ? <Loader2 className="size-3.5 animate-spin" /> : null}
          Save target date
        </button>
      </div>
      {error ? <p className="text-[11px] font-medium text-destructive">{error}</p> : null}
    </div>
  )
}
