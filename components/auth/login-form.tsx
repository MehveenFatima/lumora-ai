'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { Mail, Lock, ArrowRight, Loader2 } from 'lucide-react'
import { TextField } from './text-field'
import { GoogleButton } from './google-button'
import { AuthAlert } from './auth-alert'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function LoginForm() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [touched, setTouched] = useState<{ email?: boolean; password?: boolean }>({})
  const [status, setStatus] = useState<'idle' | 'loading' | 'error' | 'success'>('idle')

  const emailError =
    touched.email && !EMAIL_RE.test(email) ? 'Enter a valid email address' : undefined
  const passwordError =
    touched.password && password.length < 1 ? 'Password is required' : undefined

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setTouched({ email: true, password: true })
    if (!EMAIL_RE.test(email) || password.length < 1) return
    setStatus('loading')
    setTimeout(() => {
      // Demo: treat a specific password as wrong to showcase the error state
      if (password === 'wrong') {
        setStatus('error')
      } else {
        setStatus('success')
        setTimeout(() => {
          router.push('/dashboard')
        }, 500)
      }
    }, 1000)
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

      {status === 'error' ? (
        <AuthAlert variant="error">
          Incorrect email or password. Please try again.
        </AuthAlert>
      ) : null}
      {status === 'success' ? (
        <AuthAlert variant="success">Signed in successfully. Redirecting…</AuthAlert>
      ) : null}

      <GoogleButton />

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs font-medium text-muted-foreground">or continue with email</span>
        <span className="h-px flex-1 bg-border" />
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
          onBlur={() => setTouched((t) => ({ ...t, email: true }))}
          error={emailError}
          valid={EMAIL_RE.test(email)}
        />
        <div className="flex flex-col gap-1.5">
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
        </div>

        <div className="flex items-center justify-between">
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground select-none">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="size-4 rounded-[6px] border-border bg-card text-primary accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
            />
            Remember me
          </label>
          <Link
            href="/forgot-password"
            className="text-sm font-medium text-primary transition-opacity hover:opacity-80"
          >
            Forgot password?
          </Link>
        </div>

        <button
          type="submit"
          disabled={status === 'loading'}
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
