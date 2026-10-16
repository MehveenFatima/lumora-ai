'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import {
  Bell,
  BookOpenCheck,
  CheckCheck,
  FileCheck2,
  FileWarning,
  Layers,
  Loader2,
  PartyPopper,
  Target,
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NotificationEntry {
  id: string
  type: string
  title: string
  message: string
  link?: string | null
  read: boolean
  created_at: string
}

const POLL_MS = 60_000

const ICONS: Record<string, { icon: typeof Bell; tone: string }> = {
  document_ready: { icon: FileCheck2, tone: 'text-success bg-success/10' },
  document_failed: { icon: FileWarning, tone: 'text-destructive bg-destructive/10' },
  weak_topics: { icon: Target, tone: 'text-warning bg-warning/10' },
  quiz_complete: { icon: BookOpenCheck, tone: 'text-success bg-success/10' },
  flashcards_due: { icon: Layers, tone: 'text-primary bg-primary/10' },
  welcome: { icon: PartyPopper, tone: 'text-primary bg-primary/10' },
}

function timeAgo(iso: string): string {
  const seconds = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'yesterday' : `${days}d ago`
}

/** Bell with an unread badge and a dropdown of the signed-in user's notifications. */
export function NotificationBell() {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState<NotificationEntry[]>([])
  const [unread, setUnread] = useState(0)
  const [loading, setLoading] = useState(true)
  const ref = useRef<HTMLDivElement>(null)

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/v1/notifications?limit=20', { credentials: 'same-origin' })
      if (!res.ok) return
      const data = await res.json()
      setItems(data.items || [])
      setUnread(data.unread_count || 0)
    } catch {
      // offline or signed out: keep what we have
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(() => {
      if (document.visibilityState === 'visible') load()
    }, POLL_MS)
    const onFocus = () => load()
    window.addEventListener('focus', onFocus)
    window.addEventListener('lumora:notifications-changed', onFocus)
    return () => {
      clearInterval(t)
      window.removeEventListener('focus', onFocus)
      window.removeEventListener('lumora:notifications-changed', onFocus)
    }
  }, [load])

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

  async function openItem(n: NotificationEntry) {
    if (!n.read) {
      setItems((list) => list.map((x) => (x.id === n.id ? { ...x, read: true } : x)))
      setUnread((u) => Math.max(0, u - 1))
      fetch(`/api/v1/notifications/${encodeURIComponent(n.id)}/read`, { method: 'POST', credentials: 'same-origin' }).catch(
        () => null,
      )
    }
    setOpen(false)
    if (n.link && n.link.startsWith('/')) router.push(n.link)
  }

  async function markAll() {
    setItems((list) => list.map((x) => ({ ...x, read: true })))
    setUnread(0)
    await fetch('/api/v1/notifications/read-all', { method: 'POST', credentials: 'same-origin' }).catch(() => null)
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => {
          setOpen((o) => !o)
          if (!open) load()
        }}
        className="relative flex size-9 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
        aria-label={unread > 0 ? `Notifications, ${unread} unread` : 'Notifications'}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <Bell className="size-4" />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[9px] font-bold text-primary-foreground ring-2 ring-background">
            {unread > 9 ? '9+' : unread}
          </span>
        )}
      </button>

      {open && (
        <div
          role="dialog"
          aria-label="Notifications"
          className="absolute right-0 z-50 mt-2 w-[min(22rem,calc(100vw-2rem))] origin-top-right rounded-2xl border border-border bg-card p-2 shadow-card animate-in fade-in zoom-in-95 duration-100"
        >
          <div className="flex items-center justify-between px-2 pb-2 pt-1">
            <span className="text-sm font-semibold text-foreground">Notifications</span>
            {unread > 0 ? (
              <button
                type="button"
                onClick={markAll}
                className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:opacity-80"
              >
                <CheckCheck className="size-3.5" />
                Mark all as read
              </button>
            ) : null}
          </div>
          <div className="flex max-h-[min(24rem,60vh)] flex-col gap-1 overflow-y-auto">
            {loading ? (
              <div className="flex justify-center py-6 text-muted-foreground">
                <Loader2 className="size-4 animate-spin" />
              </div>
            ) : items.length === 0 ? (
              <div className="px-4 py-8 text-center">
                <Bell className="mx-auto size-5 text-muted-foreground/60" />
                <p className="mt-2 text-xs font-medium text-foreground">You&apos;re all caught up</p>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  Updates about your documents, quizzes and reviews will appear here.
                </p>
              </div>
            ) : (
              items.map((n) => {
                const meta = ICONS[n.type] || { icon: Bell, tone: 'text-muted-foreground bg-muted' }
                const Icon = meta.icon
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => openItem(n)}
                    className={cn(
                      'flex w-full gap-3 rounded-xl p-2.5 text-left transition-colors hover:bg-accent/50',
                      !n.read && 'bg-primary/5',
                    )}
                  >
                    <span className={cn('flex size-8 shrink-0 items-center justify-center rounded-lg', meta.tone)}>
                      <Icon className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-start justify-between gap-2">
                        <span className="text-xs font-semibold text-foreground">{n.title}</span>
                        <span className="shrink-0 text-[10px] text-muted-foreground">{timeAgo(n.created_at)}</span>
                      </span>
                      <span className="mt-0.5 block text-[11px] leading-relaxed text-muted-foreground">{n.message}</span>
                    </span>
                    {!n.read ? <span className="mt-1.5 size-2 shrink-0 rounded-full bg-primary" aria-label="Unread" /> : null}
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </div>
  )
}
