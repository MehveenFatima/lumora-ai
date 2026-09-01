import { cn } from '@/lib/utils'

interface ProgressProps {
  value: number
  className?: string
  indicatorClassName?: string
  'aria-label'?: string
}

export function Progress({ value, className, indicatorClassName, ...rest }: ProgressProps) {
  const clamped = Math.min(100, Math.max(0, value))
  return (
    <div
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      className={cn('h-2 w-full overflow-hidden rounded-full bg-muted', className)}
      {...rest}
    >
      <div
        className={cn('h-full rounded-full bg-primary transition-all duration-500 ease-out', indicatorClassName)}
        style={{ width: `${clamped}%` }}
      />
    </div>
  )
}
