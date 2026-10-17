'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { ArrowLeft, GraduationCap, KeyRound, Loader2, Mail, ShieldAlert, Trash2, User } from 'lucide-react'
import { TextField } from '@/components/auth/text-field'
import { AuthAlert } from '@/components/auth/auth-alert'
import { PasswordStrength, getPasswordStrength } from '@/components/auth/password-strength'
import { UserMenu } from '@/components/auth/user-menu'
import { NotificationBell } from '@/components/notifications/notification-bell'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { authClient, useCurrentUser } from '@/lib/api/auth-client'

function strongEnough(pw: string): boolean {
  return pw.length >= 8 && /[A-Za-z]/.test(pw) && /\d/.test(pw) && getPasswordStrength(pw).score >= 3
}

type Feedback = { variant: 'success' | 'error'; text: string } | null

function Section({
  icon,
  title,
  description,
  children,
  danger,
}: {
  icon: React.ReactNode
  title: string
  description: string
  children: React.ReactNode
  danger?: boolean
}) {
  return (
    <section
      className={`rounded-3xl border bg-card p-5 shadow-card sm:p-7 ${danger ? 'border-destructive/30' : 'border-border'}`}
    >
      <div className="mb-5 flex items-start gap-3">
        <span
          className={`flex size-9 shrink-0 items-center justify-center rounded-xl ${
            danger ? 'bg-destructive/10 text-destructive' : 'bg-primary/10 text-primary'
          }`}
        >
          {icon}
        </span>
        <div>
          <h2 className="font-display text-base font-semibold text-foreground">{title}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        </div>
      </div>
      {children}
    </section>
  )
}

const primaryButton =
  'inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-primary px-4 text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-opacity hover:opacity-90 disabled:opacity-60'

export default function AccountPage() {
  const user = useCurrentUser()

  const [name, setName] = useState('')
  const [savingName, setSavingName] = useState(false)
  const [nameFeedback, setNameFeedback] = useState<Feedback>(null)

  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [pwTouched, setPwTouched] = useState(false)
  const [savingPw, setSavingPw] = useState(false)
  const [pwFeedback, setPwFeedback] = useState<Feedback>(null)

  const [confirmText, setConfirmText] = useState('')
  const [deletePw, setDeletePw] = useState('')
  const [deleting, setDeleting] = useState(false)
  const [deleteFeedback, setDeleteFeedback] = useState<Feedback>(null)

  // Fill the name field once, when the account loads (never overwrite what the user is typing)
  const [nameLoaded, setNameLoaded] = useState(false)
  useEffect(() => {
    if (user && !nameLoaded) {
      setName((current) => current || user.name)
      setNameLoaded(true)
    }
  }, [user, nameLoaded])

  async function saveName(e: React.FormEvent) {
    e.preventDefault()
    if (name.trim().length < 2) {
      setNameFeedback({ variant: 'error', text: 'Enter your full name.' })
      return
    }
    setSavingName(true)
    setNameFeedback(null)
    try {
      await authClient.updateProfile(name.trim())
      setNameFeedback({ variant: 'success', text: 'Your name has been updated.' })
    } catch (err: any) {
      setNameFeedback({ variant: 'error', text: err?.message || 'Could not update your name.' })
    } finally {
      setSavingName(false)
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault()
    setPwTouched(true)
    if (!currentPw || !strongEnough(newPw)) return
    setSavingPw(true)
    setPwFeedback(null)
    try {
      await authClient.changePassword(currentPw, newPw)
      setCurrentPw('')
      setNewPw('')
      setPwTouched(false)
      setPwFeedback({
        variant: 'success',
        text: 'Password changed. You have been signed out on every other device.',
      })
    } catch (err: any) {
      setPwFeedback({ variant: 'error', text: err?.message || 'Could not change your password.' })
    } finally {
      setSavingPw(false)
    }
  }

  async function deleteAccount(e: React.FormEvent) {
    e.preventDefault()
    if (confirmText !== 'DELETE' || !deletePw) return
    setDeleting(true)
    setDeleteFeedback(null)
    try {
      await authClient.deleteAccount(deletePw)
      window.location.assign('/register')
    } catch (err: any) {
      setDeleting(false)
      setDeleteFeedback({ variant: 'error', text: err?.message || 'Could not delete your account.' })
    }
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border bg-background/85 px-4 backdrop-blur-xl md:px-8">
        <Link href="/dashboard" className="flex items-center gap-2.5">
          <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-glow">
            <GraduationCap className="size-5" strokeWidth={2.25} />
          </span>
          <span className="font-display text-base font-semibold tracking-tight text-foreground">
            Lumora<span className="text-primary">AI</span>
          </span>
        </Link>
        <div className="flex items-center gap-2 md:gap-2.5">
          <ThemeToggle />
          <NotificationBell />
          <UserMenu />
        </div>
      </header>

      <main className="mx-auto w-full max-w-2xl space-y-6 px-4 py-8 md:px-0">
        <div>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            <ArrowLeft className="size-3.5" />
            All workspaces
          </Link>
          <h1 className="mt-3 font-display text-2xl font-semibold tracking-tight">Account settings</h1>
          <p className="mt-1 text-sm text-muted-foreground">Manage your profile, password and account.</p>
        </div>

        <Section icon={<User className="size-4" />} title="Profile" description="Your name appears across LumoraAI.">
          <form onSubmit={saveName} className="flex flex-col gap-4" noValidate>
            {nameFeedback ? <AuthAlert variant={nameFeedback.variant}>{nameFeedback.text}</AuthAlert> : null}
            <TextField
              label="Full name"
              autoComplete="name"
              icon={<User />}
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
            />
            <TextField label="Email" icon={<Mail />} value={user?.email || ''} readOnly disabled hint="Your sign-in email can't be changed." />
            <div>
              <button type="submit" disabled={savingName || !user || name.trim() === user.name} className={primaryButton}>
                {savingName ? <Loader2 className="size-4 animate-spin" /> : null}
                Save changes
              </button>
            </div>
          </form>
        </Section>

        <Section
          icon={<KeyRound className="size-4" />}
          title="Password"
          description="Changing your password signs you out everywhere else."
        >
          <form onSubmit={savePassword} className="flex flex-col gap-4" noValidate>
            {pwFeedback ? <AuthAlert variant={pwFeedback.variant}>{pwFeedback.text}</AuthAlert> : null}
            <TextField
              label="Current password"
              type="password"
              autoComplete="current-password"
              value={currentPw}
              onChange={(e) => setCurrentPw(e.target.value)}
              error={pwTouched && !currentPw ? 'Enter your current password' : undefined}
            />
            <div className="flex flex-col gap-2">
              <TextField
                label="New password"
                type="password"
                autoComplete="new-password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                error={
                  pwTouched && !strongEnough(newPw)
                    ? 'Use at least 8 characters with a letter, a number and an uppercase letter or symbol'
                    : undefined
                }
              />
              <PasswordStrength password={newPw} />
            </div>
            <div>
              <button type="submit" disabled={savingPw} className={primaryButton}>
                {savingPw ? <Loader2 className="size-4 animate-spin" /> : null}
                Update password
              </button>
            </div>
          </form>
        </Section>

        <Section
          danger
          icon={<ShieldAlert className="size-4" />}
          title="Delete account"
          description="Permanently deletes your account, all workspaces, uploaded documents, quiz history and flashcards. This cannot be undone."
        >
          <form onSubmit={deleteAccount} className="flex flex-col gap-4" noValidate>
            {deleteFeedback ? <AuthAlert variant={deleteFeedback.variant}>{deleteFeedback.text}</AuthAlert> : null}
            <TextField
              label='Type "DELETE" to confirm'
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              autoComplete="off"
            />
            <TextField
              label="Your password"
              type="password"
              autoComplete="current-password"
              value={deletePw}
              onChange={(e) => setDeletePw(e.target.value)}
            />
            <div>
              <button
                type="submit"
                disabled={deleting || confirmText !== 'DELETE' || !deletePw}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-destructive px-4 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {deleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
                Delete my account
              </button>
            </div>
          </form>
        </Section>
      </main>
    </div>
  )
}
