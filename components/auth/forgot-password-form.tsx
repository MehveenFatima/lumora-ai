'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { ArrowLeft, ArrowRight, KeyRound, Loader2, Lock, Mail, RotateCw } from 'lucide-react'
import { TextField } from './text-field'
import { AuthAlert } from './auth-alert'
import { OtpInput } from './otp-input'
import { PasswordStrength, getPasswordStrength } from './password-strength'
import { authClient } from '@/lib/api/auth-client'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
const RESEND_SECONDS = 60

function strongEnough(pw: string): boolean {
  return pw.length >= 8 && /[A-Za-z]/.test(pw) && /\d/.test(pw) && getPasswordStrength(pw).score >= 3
}

export function ForgotPasswordForm() {
  const router = useRouter()
  const [step, setStep] = useState<'email' | 'reset'>('email')
  const [email, setEmail] = useState('')
  const [code, setCode] = useState('')
  const [password, setPassword] = useState('')
  const [touched, setTouched] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [info, setInfo] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  async function requestCode(e?: React.FormEvent) {
    e?.preventDefault()
    setTouched(true)
    if (!EMAIL_RE.test(email)) return
    setLoading(true)
    setError(null)
    try {
      const message = await authClient.forgotPassword(email.trim())
      setInfo(message)
      setStep('reset')
      setCooldown(RESEND_SECONDS)
    } catch (err: any) {
      setError(err?.message || 'Could not send a reset code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  async function resetPassword(e: React.FormEvent) {
    e.preventDefault()
    setTouched(true)
    if (code.length !== 6 || !strongEnough(password)) return
    setLoading(true)
    setError(null)
    try {
      await authClient.resetPassword(email.trim(), code, password)
      setInfo('Password updated. Signing you in…')
      router.replace('/dashboard')
      router.refresh()
    } catch (err: any) {
      setLoading(false)
      setError(err?.message || 'Could not reset your password. Please try again.')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <KeyRound className="size-5" />
        </span>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
          {step === 'email' ? 'Reset your password' : 'Choose a new password'}
        </h1>
        <p className="text-sm text-muted-foreground">
          {step === 'email'
            ? "Enter the email you signed up with and we'll send you a 6-digit code."
            : 'Enter the code from your email and pick a new password.'}
        </p>
      </div>

      {error ? <AuthAlert variant="error">{error}</AuthAlert> : null}
      {info ? <AuthAlert variant="success">{info}</AuthAlert> : null}

      {step === 'email' ? (
        <form onSubmit={requestCode} className="flex flex-col gap-4" noValidate>
          <TextField
            label="Email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="you@example.com"
            icon={<Mail />}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            error={touched && !EMAIL_RE.test(email) ? 'Enter a valid email address' : undefined}
            valid={EMAIL_RE.test(email)}
            autoFocus
          />
          <button
            type="submit"
            disabled={loading}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-all hover:opacity-90 disabled:opacity-60"
          >
            {loading ? <Loader2 className="size-4 animate-spin" /> : null}
            Send reset code
            {!loading ? <ArrowRight className="size-4" /> : null}
          </button>
        </form>
      ) : (
        <form onSubmit={resetPassword} className="flex flex-col gap-4" noValidate>
          <div className="flex flex-col gap-1.5">
            <span className="text-sm font-medium text-foreground">6-digit code</span>
            <OtpInput value={code} onChange={setCode} disabled={loading} invalid={touched && code.length !== 6} autoFocus />
          </div>
          <div className="flex flex-col gap-2">
            <TextField
              label="New password"
              type="password"
              autoComplete="new-password"
              placeholder="Create a new password"
              icon={<Lock />}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={
                touched && !strongEnough(password)
                  ? 'Use at least 8 characters with a letter, a number and an uppercase letter or symbol'
                  : undefined
              }
            />
            <PasswordStrength password={password} />
          </div>
          <button
            type="submit"
            disabled={loading}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-all hover:opacity-90 disabled:opacity-60"
          >
            {loading ? <Loader2 className="size-4 animate-spin" /> : null}
            Reset password and sign in
          </button>
          <button
            type="button"
            onClick={() => requestCode()}
            disabled={cooldown > 0 || loading}
            className="inline-flex items-center justify-center gap-1.5 text-sm font-medium text-primary hover:opacity-80 disabled:cursor-not-allowed disabled:text-muted-foreground"
          >
            <RotateCw className="size-3.5" />
            {cooldown > 0 ? `Send a new code in ${cooldown}s` : 'Send a new code'}
          </button>
        </form>
      )}

      <Link
        href="/login"
        className="inline-flex items-center justify-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" />
        Back to sign in
      </Link>
    </div>
  )
}
