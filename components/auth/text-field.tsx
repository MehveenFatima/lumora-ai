'use client'

import { forwardRef, useId, useState } from 'react'
import { Eye, EyeOff, Check, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

type TextFieldProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label: string
  icon?: React.ReactNode
  error?: string
  valid?: boolean
  hint?: string
}

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(function TextField(
  { label, icon, error, valid, hint, type = 'text', className, id, ...props },
  ref,
) {
  const autoId = useId()
  const fieldId = id ?? autoId
  const [show, setShow] = useState(false)
  const isPassword = type === 'password'
  const resolvedType = isPassword ? (show ? 'text' : 'password') : type

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={fieldId} className="text-sm font-medium text-foreground">
        {label}
      </label>
      <div
        className={cn(
          'group flex h-11 items-center gap-2.5 rounded-xl border bg-card px-3.5 transition-all',
          'focus-within:ring-3',
          error
            ? 'border-destructive focus-within:border-destructive focus-within:ring-destructive/20'
            : valid
              ? 'border-success/60 focus-within:border-success focus-within:ring-success/20'
              : 'border-border focus-within:border-ring focus-within:ring-ring/30',
        )}
      >
        {icon ? (
          <span className="text-muted-foreground transition-colors group-focus-within:text-foreground [&_svg]:size-[18px]">
            {icon}
          </span>
        ) : null}
        <input
          ref={ref}
          id={fieldId}
          type={resolvedType}
          aria-invalid={!!error}
          className="h-full w-full bg-transparent text-sm text-foreground placeholder:text-muted-foreground/70 focus:outline-none"
          {...props}
        />
        {isPassword ? (
          <button
            type="button"
            onClick={() => setShow((v) => !v)}
            className="text-muted-foreground transition-colors hover:text-foreground"
            aria-label={show ? 'Hide password' : 'Show password'}
          >
            {show ? <EyeOff className="size-[18px]" /> : <Eye className="size-[18px]" />}
          </button>
        ) : valid && !error ? (
          <Check className="size-[18px] text-success" />
        ) : null}
      </div>
      {error ? (
        <p className="flex items-center gap-1.5 text-xs font-medium text-destructive">
          <AlertCircle className="size-3.5" />
          {error}
        </p>
      ) : hint ? (
        <p className="text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  )
})
