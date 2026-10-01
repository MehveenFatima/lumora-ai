'use client'

import { useEffect, useRef, useState } from 'react'
import Link from 'next/link'
import { LayoutGrid, LogOut, Loader2 } from 'lucide-react'
import { authClient, initialsOf, useCurrentUser } from '@/lib/api/auth-client'

export function UserMenu() {
  const user = useCurrentUser()
  const [open, setOpen] = useState(false)
  const [signingOut, setSigningOut] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  async function signOut() {
    setSigningOut(true)
    await authClient.logout().catch(() => null)
    window.location.assign('/login')
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        className="flex items-center gap-2 rounded-xl border border-border bg-card p-1 pr-2.5 transition-colors hover:bg-accent/40"
      >
        <span className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-chart-2 text-[11px] font-bold text-primary-foreground">
          {user ? initialsOf(user.name) : '·'}
        </span>
        <span className="hidden max-w-[140px] text-left leading-none md:block">
          <span className="block truncate text-xs font-medium text-foreground">{user?.name || 'Account'}</span>
          <span className="mt-0.5 block text-[10px] text-muted-foreground">Learner</span>
        </span>
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 z-50 mt-2 w-60 overflow-hidden rounded-2xl border border-border bg-card shadow-card"
        >
          <div className="border-b border-border px-4 py-3">
            <p className="truncate text-sm font-semibold text-foreground">{user?.name}</p>
            <p className="truncate text-xs text-muted-foreground">{user?.email}</p>
          </div>
          <div className="p-1.5">
            <Link
              href="/dashboard"
              role="menuitem"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2 rounded-xl px-3 py-2 text-sm text-foreground hover:bg-accent/50"
            >
              <LayoutGrid className="size-4 text-muted-foreground" />
              All workspaces
            </Link>
            <button
              type="button"
              role="menuitem"
              onClick={signOut}
              disabled={signingOut}
              className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm text-foreground hover:bg-accent/50 disabled:opacity-60"
            >
              {signingOut ? (
                <Loader2 className="size-4 animate-spin text-muted-foreground" />
              ) : (
                <LogOut className="size-4 text-muted-foreground" />
              )}
              Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
