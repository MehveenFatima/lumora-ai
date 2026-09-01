import { CheckCircle2, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'

export function AuthAlert({
  variant,
  children,
}: {
  variant: 'success' | 'error'
  children: React.ReactNode
}) {
  return (
    <div
      role={variant === 'error' ? 'alert' : 'status'}
      className={cn(
        'flex items-start gap-2.5 rounded-xl border px-3.5 py-3 text-sm',
        variant === 'success'
          ? 'border-success/30 bg-success/10 text-success'
          : 'border-destructive/30 bg-destructive/10 text-destructive',
      )}
    >
      {variant === 'success' ? (
        <CheckCircle2 className="mt-0.5 size-4 shrink-0" />
      ) : (
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      )}
      <span className="text-foreground/90">{children}</span>
    </div>
  )
}
