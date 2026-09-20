'use client'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import {
  Search,
  Bell,
  PanelLeft,
  Command,
  Target,
  Sparkles,
  CheckCircle2,
  ExternalLink,
  GraduationCap,
} from 'lucide-react'
import { Workspace, NotificationItem } from '@/lib/types/domain'
import { WorkspaceSwitcher } from './workspace-switcher'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'
import { tutorApiClient } from '@/lib/api/tutor-api-client'

interface WorkspaceHeaderProps {
  workspaces: Workspace[]
  currentWorkspace: Workspace
  notifications?: NotificationItem[]
  onToggleSidebar?: () => void
  onCreateWorkspaceClick?: () => void
}

export function WorkspaceHeader({
  workspaces,
  currentWorkspace,
  notifications = [],
  onToggleSidebar,
  onCreateWorkspaceClick,
}: WorkspaceHeaderProps) {
  const [notifOpen, setNotifOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const notifRef = useRef<HTMLDivElement>(null)

  const unreadCount = notifications.filter((n) => !n.read).length

  const checkStatus = async () => {
    setBackendStatus('checking')
    try {
      const h = await tutorApiClient.getHealth()
      if (h && h.status === 'healthy') {
        setBackendStatus('connected')
      } else {
        setBackendStatus('disconnected')
      }
    } catch {
      setBackendStatus('disconnected')
    }
  }

  useEffect(() => {
    checkStatus()
  }, [])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false)
      }
    }
    if (notifOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [notifOpen])

  return (
    <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border bg-background/85 px-4 backdrop-blur-xl md:px-6">
      <div className="flex items-center gap-3">
        {/* Mobile menu trigger */}
        <button
          onClick={onToggleSidebar}
          className="flex size-9 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:text-foreground lg:hidden"
          aria-label="Toggle navigation menu"
        >
          <PanelLeft className="size-4" />
        </button>

        {/* Mobile brand icon */}
        <Link href="/dashboard" className="flex items-center gap-2 lg:hidden">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <GraduationCap className="size-4" />
          </span>
        </Link>

        {/* Workspace Switcher */}
        <WorkspaceSwitcher
          workspaces={workspaces}
          currentWorkspace={currentWorkspace}
          onCreateWorkspaceClick={onCreateWorkspaceClick}
        />

        {/* Presentation Demo Data Badge */}
        <span className="hidden xl:inline-flex items-center gap-1 rounded-full border border-primary/20 bg-primary/5 px-2.5 py-0.5 text-[10px] font-medium text-primary">
          <Sparkles className="size-3" />
          Presentation Demo Data
        </span>

        {/* Backend Connection Status Pill */}
        <div className="hidden sm:flex items-center gap-1.5 rounded-xl border border-border bg-card/60 px-2.5 py-1 text-[11px]">
          <span
            className={cn(
              'size-2 rounded-full',
              backendStatus === 'connected'
                ? 'bg-success animate-pulse'
                : backendStatus === 'checking'
                ? 'bg-warning animate-pulse'
                : 'bg-destructive'
            )}
          />
          <span className="text-muted-foreground">
            {backendStatus === 'connected' ? 'FastAPI Connected' : backendStatus === 'checking' ? 'Connecting...' : 'Backend Offline'}
          </span>
          {backendStatus === 'disconnected' && (
            <button
              onClick={checkStatus}
              className="ml-1 text-[10px] font-medium text-destructive underline hover:text-destructive/80"
            >
              Retry
            </button>
          )}
        </div>

        {/* Compact Mastery Pill */}
        <div className="hidden items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-1.5 md:flex">
          <Target className="size-3.5 text-primary" />
          <span className="text-xs text-muted-foreground">Mastery:</span>
          <span className="text-xs font-semibold tabular-nums text-foreground">
            {currentWorkspace.overallMastery}%
          </span>
          <Badge variant="success" size="sm" className="ml-0.5 text-[10px]">
            +{currentWorkspace.masteryDelta}%
          </Badge>
        </div>
      </div>

      {/* Center / Right: Search & Actions */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Quick Search */}
        <div className="relative hidden md:block w-48 lg:w-64">
          <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search in workspace..."
            className="h-9 w-full rounded-xl border border-input bg-card pl-8 pr-12 text-xs text-foreground placeholder:text-muted-foreground/70 outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/20"
            aria-label="Search workspace sources and topics"
          />
          <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 hidden items-center gap-0.5 rounded border border-border bg-muted px-1 text-[9px] font-medium text-muted-foreground lg:flex">
            <Command className="size-2.5" />K
          </kbd>
        </div>

        {/* Theme Toggle Button - Mandatory Global Presence */}
        <ThemeToggle />

        {/* Notifications Popover */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => setNotifOpen(!notifOpen)}
            className="relative flex size-9 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:border-primary/40 hover:text-foreground"
            aria-label="Notifications"
            aria-expanded={notifOpen}
          >
            <Bell className="size-4" />
            {unreadCount > 0 && (
              <span className="absolute right-2 top-2 size-2 rounded-full bg-primary ring-2 ring-card" />
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 z-50 mt-2 w-80 origin-top-right rounded-2xl border border-border bg-card p-3 shadow-card animate-in fade-in zoom-in-95 duration-100">
              <div className="flex items-center justify-between border-b border-border pb-2">
                <span className="text-xs font-semibold text-foreground">Notifications</span>
                <span className="text-[11px] text-muted-foreground">{unreadCount} unread</span>
              </div>
              <div className="mt-2 flex flex-col gap-1.5 max-h-64 overflow-y-auto">
                {notifications.length === 0 ? (
                  <p className="py-4 text-center text-xs text-muted-foreground">No new notifications</p>
                ) : (
                  notifications.map((n) => (
                    <div
                      key={n.id}
                      className={cn(
                        'rounded-xl p-2.5 text-left transition-colors',
                        !n.read ? 'bg-primary/5 border border-primary/10' : 'hover:bg-accent/40'
                      )}
                    >
                      <div className="flex items-center justify-between gap-1">
                        <p className="text-xs font-semibold text-foreground">{n.title}</p>
                        <span className="text-[10px] text-muted-foreground">{n.timestamp}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] leading-relaxed text-muted-foreground">{n.message}</p>
                    </div>
                  ))
                )}
              </div>
            </div>
          )}
        </div>

        {/* User Profile */}
        <Link
          href="/dashboard"
          className="flex items-center gap-2 rounded-xl border border-border bg-card p-1 pr-2.5 transition-colors hover:bg-accent/40"
        >
          <span className="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-chart-2 text-[11px] font-bold text-primary-foreground">
            MF
          </span>
          <span className="hidden text-left leading-none md:block">
            <span className="block text-xs font-medium text-foreground">Mehveen</span>
            <span className="mt-0.5 block text-[10px] text-muted-foreground">Pro Learner</span>
          </span>
        </Link>
      </div>
    </header>
  )
}
