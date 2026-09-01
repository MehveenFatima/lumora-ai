'use client'

import { useState } from 'react'
import Link from 'next/link'
import { User, Mail, Lock, ArrowRight, Loader2 } from 'lucide-react'
import { TextField } from './text-field'
import { GoogleButton } from './google-button'
import { AuthAlert } from './auth-alert'
import { PasswordStrength, getPasswordStrength } from './password-strength'

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

export function RegisterForm() {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [agree, setAgree] = useState(false)
  const [touched, setTouched] = useState<Record<string, boolean>>({})
  const [status, setStatus] = useState<'idle' | 'loading' | 'success'>('idle')

  const nameError = touched.name && name.trim().length < 2 ? 'Enter your full name' : undefined
  const emailError =
    touched.email && !EMAIL_RE.test(email) ? 'Enter a valid email address' : undefined
  const strong = getPasswordStrength(password).score >= 3
  const passwordError =
    touched.password && !strong ? 'Choose a stronger password' : undefined

  function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setTouched({ name: true, email: true, password: true })
    if (name.trim().length < 2 || !EMAIL_RE.test(email) || !strong || !agree) return
    setStatus('loading')
    setTimeout(() => setStatus('success'), 1500)
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-1.5">
        <h1 className="font-display text-2xl font-semibold tracking-tight text-foreground">
          Create your account
        </h1>
        <p className="text-sm text-muted-foreground">
          Start learning smarter with LumoraAI — it&apos;s free.
        </p>
      </div>

      {status === 'success' ? (
        <AuthAlert variant="success">
          Account created! Check your inbox to verify your email.
        </AuthAlert>
      ) : null}

      <GoogleButton label="Sign up with Google" />

      <div className="flex items-center gap-3">
        <span className="h-px flex-1 bg-border" />
        <span className="text-xs font-medium text-muted-foreground">or sign up with email</span>
        <span className="h-px flex-1 bg-border" />
      </div>

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

        <label className="flex cursor-pointer items-start gap-2.5 text-sm text-muted-foreground select-none">
          <input
            type="checkbox"
            checked={agree}
            onChange={(e) => setAgree(e.target.checked)}
            className="mt-0.5 size-4 rounded-[6px] border-border bg-card accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/40"
          />
          <span>
            I agree to the{' '}
            <a href="#" className="font-medium text-primary hover:opacity-80">
              Terms
            </a>{' '}
            and{' '}
            <a href="#" className="font-medium text-primary hover:opacity-80">
              Privacy Policy
            </a>
            .
          </span>
        </label>

        <button
          type="submit"
          disabled={status === 'loading' || !agree}
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
