import type { LucideIcon } from 'lucide-react'
import { TrendingUp, TrendingDown } from 'lucide-react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: string
  delta: number
  hint: string
  icon: LucideIcon
}

export function StatCard({ label, value, delta, hint, icon: Icon }: StatCardProps) {
  const positive = delta >= 0
  return (
    <div className="rounded-2xl border border-border bg-card p-5 shadow-soft transition-shadow hover:shadow-card">
      <div className="flex items-center justify-between">
        <span className="flex size-9 items-center justify-center rounded-lg bg-accent text-accent-foreground">
          <Icon className="size-[18px]" strokeWidth={2} />
        </span>
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
            positive ? 'bg-success/12 text-success' : 'bg-destructive/12 text-destructive',
          )}
        >
          {positive ? <TrendingUp className="size-3" /> : <TrendingDown className="size-3" />}
          {positive ? '+' : ''}
          {delta}%
        </span>
      </div>
      <p className="mt-4 font-display text-3xl font-semibold tracking-tight tabular-nums text-foreground">
        {value}
      </p>
      <p className="mt-1 text-sm font-medium text-foreground">{label}</p>
      <p className="mt-0.5 text-[13px] text-muted-foreground">{hint}</p>
    </div>
  )
}
