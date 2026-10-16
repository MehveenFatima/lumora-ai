'use client'

import { useState } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { User, Mail, Lock, ArrowRight, Loader2 } from 'lucide-react'
import { TextField } from './text-field'
import { AuthAlert } from './auth-alert'
import { PasswordStrength, getPasswordStrength } from './password-strength'
import { authClient } from '@/lib/api/auth-client'
import { safeNextPath } from './login-form'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Mirrors the server rule: at least 8 characters with a letter and a number. */
function meetsServerPasswordRule(pw: string): boolean {
  return pw.length >= 8 && /[A-Za-z]/.test(pw) && /\d/.test(pw)
}

export function RegisterForm() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [status, setStatus] = useState<'idle' | 'loading' | 'success'>('idle')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const nameError = touched.name && name.trim().length < 2 ? 'Enter your full name' : undefined
  const emailError =
    touched.email && !EMAIL_RE.test(email) ? 'Enter a valid email address' : undefined
  const strong = meetsServerPasswordRule(password) && getPasswordStrength(password).score >= 3
  const passwordError =
    touched.password && !strong
      ? 'Use at least 8 characters with a letter, a number and an uppercase letter or symbol'
      : undefined

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setTouched({ name: true, email: true, password: true })
    if (name.trim().length < 2 || !EMAIL_RE.test(email) || !strong) return
    setStatus('loading')
    setErrorMessage(null)
    try {
      const result = await authClient.register(name.trim(), email.trim(), password)
      if (result.verificationRequired) {
        const q = new URLSearchParams({ email: result.email })
        if (!result.emailSent) q.set('sent', '0')
        router.replace(`/verify-email?${q.toString()}`)
        return
      }
      setStatus('success')
      router.replace(safeNextPath())
      router.refresh()
    } catch (err: any) {
      setStatus('idle')
      setErrorMessage(err?.message || 'Could not create your account. Please try again.')
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
          Create your account
        </h1>
        <p className="text-sm text-muted-foreground">
          Upload your study material and start learning with grounded answers.
        </p>
      </div>

      {errorMessage ? <AuthAlert variant="error">{errorMessage}</AuthAlert> : null}
      {status === 'success' ? (
        <AuthAlert variant="success">Account created. Taking you to your dashboard…</AuthAlert>
      ) : null}

      <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
        <TextField
          label="Full name"
          autoComplete="name"
          placeholder="Ada Lovelace"
          icon={<User />}
          value={name}
          onChange={(e) => setName(e.target.value)}
          onBlur={() => setTouched((t) => ({ ...t, name: true }))}
          error={nameError}
          valid={name.trim().length >= 2}
        />
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
        <div className="flex flex-col gap-2">
          <TextField
            label="Password"
            type="password"
            autoComplete="new-password"
            placeholder="Create a password"
            icon={<Lock />}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onBlur={() => setTouched((t) => ({ ...t, password: true }))}
            error={passwordError}
          />
          <PasswordStrength password={password} />
        </div>

        <button
          type="submit"
          disabled={status !== 'idle'}
          className="mt-1 inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-primary text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-all hover:opacity-90 focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/40 disabled:opacity-60"
        >
          {status === 'loading' ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Creating account…
            </>
          ) : (
            <>
              Create account
              <ArrowRight className="size-4" />
            </>
          )}
        </button>
      </form>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link href="/login" className="font-medium text-primary transition-opacity hover:opacity-80">
          Sign in
        </Link>
      </p>
    </div>
  )
}
