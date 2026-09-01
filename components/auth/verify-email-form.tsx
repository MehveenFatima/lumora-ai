'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { MailCheck, CheckCircle2, Loader2, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { AuthAlert } from './auth-alert'

const LENGTH = 6

export function VerifyEmailForm({ email = 'you@example.com' }: { email?: string }) {
  const [digits, setDigits] = useState<string[]>(Array(LENGTH).fill(''))
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')
  const [seconds, setSeconds] = useState(30)
  const inputs = useRef<(HTMLInputElement | null)[]>([])

  useEffect(() => {
    if (seconds <= 0) return
    const t = setTimeout(() => setSeconds((s) => s - 1), 1000)
    return () => clearTimeout(t)
  }, [seconds])

  const code = digits.join('')

  function setDigit(i: number, val: string) {
    const clean = val.replace(/\D/g, '')
    if (!clean) {
      setDigits((d) => d.map((x, idx) => (idx === i ? '' : x)))
      return
    }
    setStatus('idle')
    setDigits((d) => {
      const next = [...d]
      // support pasting multiple chars
      clean.split('').forEach((ch, k) => {
        if (i + k < LENGTH) next[i + k] = ch
      })
      return next
    })
    const nextIndex = Math.min(i + clean.length, LENGTH - 1)
    inputs.current[nextIndex]?.focus()
  }

  function onKeyDown(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace' && !digits[i] && i > 0) {
      inputs.current[i - 1]?.focus()
    }
  }

  function submit(e: React.FormEvent) {
    e.preventDefault()
    if (code.length < LENGTH) return
    setStatus('loading')
    setTimeout(() => {
      // Demo: "000000" fails, anything else succeeds
      setStatus(code === '000000' ? 'error' : 'success')
    }, 1300)
  }

  if (status === 'success') {
    return (
      <div className="flex flex-col items-center gap-6 text-center">
        <span className="flex size-14 items-center justify-center rounded-2xl bg-success/12 text-success">
          <CheckCircle2 className="size-7" />
        </span>
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            Email verified
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            Your account is all set. Welcome to LumoraAI!
          </p>
        </div>
        <Link
          href="/dashboard"
          className="inline-flex h-11 w-full items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-opacity hover:opacity-90"
        >
          Go to dashboard
          <ArrowRight className="size-4" />
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col items-center gap-4 text-center">
        <span className="flex size-14 items-center justify-center rounded-2xl bg-accent text-primary">
          <MailCheck className="size-7" />
        </span>
        <div className="flex flex-col gap-1.5">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            Verify your email
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            We sent a 6-digit code to{' '}
            <span className="font-medium text-foreground">{email}</span>. Enter it below to
            continue.
          </p>
        </div>
      </div>

      {status === 'error' ? (
        <AuthAlert variant="error">That code is incorrect or expired. Try again.</AuthAlert>
      ) : null}

      <form onSubmit={submit} className="flex flex-col gap-6">
        <div className="flex justify-center gap-2 sm:gap-2.5">
          {digits.map((d, i) => (
            <input
              key={i}
              ref={(el) => {
                inputs.current[i] = el
              }}
              inputMode="numeric"
              maxLength={LENGTH}
              value={d}
              onChange={(e) => setDigit(i, e.target.value)}
              onKeyDown={(e) => onKeyDown(i, e)}
              aria-label={`Digit ${i + 1}`}
              className={cn(
                'size-12 rounded-xl border bg-card text-center font-display text-lg font-semibold text-foreground transition-all focus:outline-none focus:ring-3',
                status === 'error'
                  ? 'border-destructive focus:border-destructive focus:ring-destructive/20'
                  : d
                    ? 'border-primary/50 focus:border-ring focus:ring-ring/30'
                    : 'border-border focus:border-ring focus:ring-ring/30',
              )}
            />
          ))}
        </div>

        <button
          type="submit"
          disabled={status === 'loading' || code.length < LENGTH}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-all hover:opacity-90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40 disabled:opacity-60"
        >
          {status === 'loading' ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Verifying…
            </>
          ) : (
            'Verify email'
          )}
        </button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        Didn&apos;t get a code?{' '}
        {seconds > 0 ? (
          <span className="tabular-nums">Resend in {seconds}s</span>
        ) : (
          <button
            onClick={() => setSeconds(30)}
            className="font-medium text-primary transition-opacity hover:opacity-80"
          >
            Resend code
          </button>
        )}
      </p>
    </div>
  )
}
