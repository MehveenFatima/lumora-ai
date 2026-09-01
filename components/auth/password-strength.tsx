'use client'

import { Check } from 'lucide-react'
import { cn } from '@/lib/utils'

export type StrengthResult = {
  score: number // 0-4
  checks: { label: string; met: boolean }[]
}

export function getPasswordStrength(pw: string): StrengthResult {
  const checks = [
    { label: 'At least 8 characters', met: pw.length >= 8 },
    { label: 'One uppercase letter', met: /[A-Z]/.test(pw) },
    { label: 'One number', met: /[0-9]/.test(pw) },
    { label: 'One symbol', met: /[^A-Za-z0-9]/.test(pw) },
  ]
  const score = checks.filter((c) => c.met).length
  return { score, checks }
}

const LABELS = ['Too weak', 'Weak', 'Fair', 'Good', 'Strong']
const COLORS = [
  'bg-destructive',
  'bg-destructive',
  'bg-warning',
  'bg-chart-2',
  'bg-success',
]

export function PasswordStrength({ password }: { password: string }) {
  if (!password) return null
  const { score, checks } = getPasswordStrength(password)
  const level = Math.max(1, score)

  return (
    <div className="flex flex-col gap-2.5 pt-0.5">
      <div className="flex items-center gap-2">
        <div className="flex flex-1 gap-1.5">
          {[0, 1, 2, 3].map((i) => (
            <span
              key={i}
              className={cn(
                'h-1.5 flex-1 rounded-full transition-colors duration-300',
                i < level ? COLORS[score] : 'bg-border',
              )}
            />
          ))}
        </div>
        <span
          className={cn(
            'w-16 text-right text-xs font-semibold tabular-nums',
            score <= 1 && 'text-destructive',
            score === 2 && 'text-warning',
            score === 3 && 'text-chart-2',
            score >= 4 && 'text-success',
          )}
        >
          {LABELS[score]}
        </span>
      </div>
      <ul className="grid grid-cols-2 gap-x-3 gap-y-1.5">
        {checks.map((c) => (
          <li
            key={c.label}
            className={cn(
              'flex items-center gap-1.5 text-xs transition-colors',
              c.met ? 'text-success' : 'text-muted-foreground',
            )}
          >
            <span
              className={cn(
                'flex size-3.5 items-center justify-center rounded-full border transition-colors',
                c.met ? 'border-success bg-success/15' : 'border-border',
              )}
            >
              {c.met ? <Check className="size-2.5" strokeWidth={3} /> : null}
            </span>
            {c.label}
          </li>
        ))}
      </ul>
    </div>
  )
}
