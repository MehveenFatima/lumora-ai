'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Mail, ArrowRight, ArrowLeft, Loader2, MailCheck } from 'lucide-react'
import { TextField } from './text-field'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function ForgotPasswordForm() {
  const [email, setEmail] = useState('')
  const [touched, setTouched] = useState(false)
  const [status, setStatus] = useState<'idle' | 'loading' | 'sent'>('idle')

  const emailError = touched && !EMAIL_RE.test(email) ? 'Enter a valid email address' : undefined

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (!EMAIL_RE.test(email)) return
    setStatus('loading')
    setTimeout(() => setStatus('sent'), 1400)
  }

  if (status === 'sent') {
    return (
      <div className="flex flex-col items-center gap-6 text-center">
        <span className="flex size-14 items-center justify-center rounded-2xl bg-success/12 text-success">
          <MailCheck className="size-7" />
        </span>
        <div className="flex flex-col gap-2">
          <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
            Check your email
          </h1>
          <p className="text-sm leading-relaxed text-muted-foreground">
            We sent a password reset link to{' '}
            <span className="font-medium text-foreground">{email}</span>. Follow the link to set a
            new password.
          </p>
        </div>
        <button
          onClick={() => setStatus('idle')}
          className="text-sm font-medium text-primary transition-opacity hover:opacity-80"
        >
          Use a different email
        </button>
        <Link
          href="/login"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          Back to sign in
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
          Forgot password?
        </h1>
        <p className="text-sm text-muted-foreground">
          No worries. Enter your email and we&apos;ll send you a reset link.
        </p>
      </div>

      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <TextField
          label="Email"
          type="email"
          inputMode="email"
          autoComplete="email"
          placeholder="you@example.com"
          icon={<Mail />}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          onBlur={() => setTouched(true)}
          error={emailError}
          valid={EMAIL_RE.test(email)}
        />
        <button
          type="submit"
          disabled={status === 'loading'}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-all hover:opacity-90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40 disabled:opacity-70"
        >
          {status === 'loading' ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Sending link…
            </>
          ) : (
            <>
              Send reset link
              <ArrowRight className="size-4" />
            </>
          )}
        </button>
      </form>

      <Link
        href="/login"
        className="inline-flex items-center justify-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ArrowLeft className="size-4" />
        Back to sign in
      </Link>
    </div>
  )
}
