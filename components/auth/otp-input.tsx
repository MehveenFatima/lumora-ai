'use client'

import { useRef } from 'react'
import { cn } from '@/lib/utils'

const LENGTH = 6

/** Six single-digit boxes; supports typing, backspace, arrow keys and pasting a whole code. */
export function OtpInput({
  value,
  onChange,
  disabled,
  invalid,
  autoFocus,
}: {
  value: string
  onChange: (code: string) => void
  disabled?: boolean
  invalid?: boolean
  autoFocus?: boolean
}) {
  const refs = useRef<Array<HTMLInputElement | null>>([])
  const digits = Array.from({ length: LENGTH }, (_, i) => value[i] || '')

  function setAt(index: number, digit: string) {
    const next = digits.slice()
    next[index] = digit
    onChange(next.join('').slice(0, LENGTH))
  }

  function focus(index: number) {
    refs.current[Math.max(0, Math.min(LENGTH - 1, index))]?.focus()
  }

  return (
    <div className="flex justify-between gap-2" role="group" aria-label="6-digit verification code">
      {digits.map((d, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el
          }}
          value={d}
          disabled={disabled}
          autoFocus={autoFocus && i === 0}
          inputMode="numeric"
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
          maxLength={1}
          aria-label={`Digit ${i + 1}`}
          aria-invalid={invalid}
          onChange={(e) => {
            const v = e.target.value.replace(/\D/g, '')
            if (!v) return setAt(i, '')
            if (v.length > 1) {
              // Autofill or paste into a single box
              const merged = (digits.slice(0, i).join('') + v).slice(0, LENGTH)
              onChange(merged)
              focus(merged.length)
              return
            }
            setAt(i, v)
            focus(i + 1)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Backspace' && !digits[i]) {
              e.preventDefault()
              setAt(i - 1, '')
              focus(i - 1)
            } else if (e.key === 'ArrowLeft') {
              e.preventDefault()
              focus(i - 1)
            } else if (e.key === 'ArrowRight') {
              e.preventDefault()
              focus(i + 1)
            }
          }}
          onPaste={(e) => {
            const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, LENGTH)
            if (!pasted) return
            e.preventDefault()
            onChange(pasted)
            focus(pasted.length)
          }}
          onFocus={(e) => e.target.select()}
          className={cn(
            'h-12 w-full min-w-0 rounded-xl border bg-card text-center font-display text-xl font-semibold tabular-nums text-foreground transition-all',
            'focus:outline-none focus:ring-3',
            invalid
              ? 'border-destructive focus:border-destructive focus:ring-destructive/20'
              : 'border-border focus:border-ring focus:ring-ring/30',
            'disabled:opacity-60',
          )}
        />
      ))}
    </div>
  )
}
