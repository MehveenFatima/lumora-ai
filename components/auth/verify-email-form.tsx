'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { ArrowRight, Loader2, MailCheck, RotateCw } from 'lucide-react'
import { AuthAlert } from './auth-alert'
import { OtpInput } from './otp-input'
import { authClient } from '@/lib/api/auth-client'

const RESEND_SECONDS = 60

export function VerifyEmailForm() {
  const router = useRouter()
  const params = useSearchParams()
  const email = (params.get('email') || '').trim().toLowerCase()
  const notSent = params.get('sent') === '0'

  const [code, setCode] = useState('')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success'>('idle')
  const [error, setError] = useState<string | null>(
    notSent ? "We couldn't send the email just now. Use “Send a new code” below." : null,
  )
  const [info, setInfo] = useState<string | null>(null)
  const [cooldown, setCooldown] = useState(notSent ? 0 : RESEND_SECONDS)
  const [resending, setResending] = useState(false)

  useEffect(() => {
    if (cooldown <= 0) return
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000)
    return () => clearTimeout(t)
  }, [cooldown])

  async function submit(value: string) {
    if (value.length !== 6 || status !== 'idle') return
    setStatus('loading')
    setError(null)
    setInfo(null)
    try {
      await authClient.verifyEmail(email, value)
      setStatus('success')
      router.replace('/dashboard')
      router.refresh()
    } catch (err: any) {
      setStatus('idle')
      setCode('')
      setError(err?.message || 'That code did not work. Please try again.')
    }
  }

  async function resend() {
    setResending(true)
    setError(null)
    setInfo(null)
    try {
      await authClient.resendVerification(email)
      setInfo('A new code is on its way. Check your inbox and spam folder.')
      setCooldown(RESEND_SECONDS)
    } catch (err: any) {
      setError(err?.message || 'Could not send a new code. Please try again shortly.')
    } finally {
      setResending(false)
    }
  }

  if (!email) {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">Verify your email</h1>
        <AuthAlert variant="error">This link is missing an email address. Sign in again to get a new code.</AuthAlert>
        <Link href="/login" className="text-sm font-medium text-primary hover:opacity-80">
          Back to sign in
        </Link>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
          <MailCheck className="size-5" />
        </span>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">Check your email</h1>
        <p className="text-sm text-muted-foreground">
          We sent a 6-digit code to <span className="font-medium text-foreground">{email}</span>. Enter it below to
          activate your account.
        </p>
      </div>

      {error ? <AuthAlert variant="error">{error}</AuthAlert> : null}
      {info ? <AuthAlert variant="success">{info}</AuthAlert> : null}
      {status === 'success' ? <AuthAlert variant="success">Email verified. Taking you to your dashboard…</AuthAlert> : null}

      <form
        onSubmit={(e) => {
          e.preventDefault()
          submit(code)
        }}
        className="flex flex-col gap-4"
        noValidate
      >
        <OtpInput
          value={code}
          onChange={(v) => {
            setCode(v)
            if (v.length === 6) submit(v)
          }}
          disabled={status !== 'idle'}
          invalid={!!error && code.length === 0}
          autoFocus
        />
        <button
          type="submit"
          disabled={status !== 'idle' || code.length !== 6}
          className="inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-all hover:opacity-90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40 disabled:opacity-60"
        >
          {status === 'loading' ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Verifying…
            </>
          ) : (
            <>
              Verify email
              <ArrowRight className="size-4" />
            </>
          )}
        </button>
      </form>

      <div className="flex flex-col items-center gap-2 text-sm text-muted-foreground">
        <span>Didn&apos;t get it? Check spam, or</span>
        <button
          type="button"
          onClick={resend}
          disabled={cooldown > 0 || resending}
          className="inline-flex items-center gap-1.5 font-medium text-primary transition-opacity hover:opacity-80 disabled:cursor-not-allowed disabled:text-muted-foreground"
        >
          {resending ? <Loader2 className="size-3.5 animate-spin" /> : <RotateCw className="size-3.5" />}
          {cooldown > 0 ? `Send a new code in ${cooldown}s` : 'Send a new code'}
        </button>
        <Link href="/login" className="mt-2 text-xs hover:text-foreground">
          Use a different account
        </Link>
      </div>
    </div>
  )
}
