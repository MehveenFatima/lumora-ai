'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Mail, Lock, ArrowRight, Loader2 } from 'lucide-react'
import { TextField } from './text-field'
import { AuthAlert } from './auth-alert'
import { authClient } from '@/lib/api/auth-client'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Only follow same-site relative paths after login (prevents open redirects). */
export function safeNextPath(): string {
  if (typeof window === 'undefined') return '/dashboard'
  const next = new URLSearchParams(window.location.search).get('next') || ''
  return next.startsWith('/') && !next.startsWith('//') ? next : '/dashboard'
}

export function LoginForm() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [touched, setTouched] = useState<{ email?: boolean; password?: boolean }>({})
  const [status, setStatus] = useState<'idle' | 'loading' | 'success'>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const emailError =
    touched.email && !EMAIL_RE.test(email) ? 'Enter a valid email address' : undefined
  const passwordError =
    touched.password && password.length < 1 ? 'Password is required' : undefined

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setTouched({ email: true, password: true })
    if (!EMAIL_RE.test(email) || password.length < 1) return
    setStatus('loading')
    setErrorMessage(null)
    try {
      await authClient.login(email.trim(), password)
      setStatus('success')
      router.replace(safeNextPath())
      router.refresh()
    } catch (err: any) {
      setStatus('idle')
      setErrorMessage(err?.message || 'Could not sign in. Please try again.')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
          Welcome back
        </h1>
        <p className="text-sm text-muted-foreground">
          Sign in to continue your learning journey.
        </p>
      </div>

      {errorMessage ? <AuthAlert variant="error">{errorMessage}</AuthAlert> : null}
      {status === 'success' ? (
        <AuthAlert variant="success">Signed in successfully. Redirecting…</AuthAlert>
      ) : null}

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
          onBlur={() => setTouched((t) => ({ ...t, email: true }))}
          error={emailError}
          valid={EMAIL_RE.test(email)}
        />
        <TextField
          label="Password"
          type="password"
          autoComplete="current-password"
          placeholder="Enter your password"
          icon={<Lock />}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, password: true }))}
          error={passwordError}
        />

        <button
          type="submit"
          disabled={status !== 'idle'}
          className="mt-1 inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-all hover:opacity-90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40 disabled:opacity-70"
        >
          {status === 'loading' ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Signing in…
            </>
          ) : (
            <>
              Sign in
              <ArrowRight className="size-4" />
            </>
          )}
        </button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{' '}
        <Link href="/register" className="font-medium text-primary transition-opacity hover:opacity-80">
          Sign up
        </Link>
      </p>
    </div>
  )
}
