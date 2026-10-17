'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { PanelLeft, Target, GraduationCap } from 'lucide-react'
import { UserMenu } from '@/components/auth/user-menu'
import { NotificationBell } from '@/components/notifications/notification-bell'
import { CommandSearch } from './command-search'
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
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking')
  const [aiStatus, setAiStatus] = useState<'healthy' | 'degraded' | 'unavailable' | 'unknown'>('unknown')

  const checkStatus = async () => {
    setBackendStatus('checking')
    try {
      const h = await tutorApiClient.getHealth()
      const isBackendHealthy = h && (h.status === 'ok' || h.status === 'healthy' || h.backend === 'healthy')
      if (isBackendHealthy) {
        setBackendStatus('connected')
        if (h.ai?.status) {
          setAiStatus(h.ai.status as any)
        } else {
          setAiStatus('healthy')
        }
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

        {/* AI Provider Status Pill (visible when backend is connected and AI is in rate-limit cooldown) */}
        {backendStatus === 'connected' && aiStatus === 'degraded' && (
          <div
            className="hidden lg:flex items-center gap-1.5 rounded-xl border border-warning/30 bg-warning/10 px-2.5 py-1 text-[11px] text-warning"
            title="AI model rate limit cooldown active; grounded knowledge retrieval fallback is operational"
          >
            <span className="size-2 rounded-full bg-warning animate-pulse" />
            <span className="font-medium">AI: Cooldown (Fallback Active)</span>
          </div>
        )}

        {/* Compact Mastery Pill */}
        <div className="hidden items-center gap-2 rounded-xl border border-border bg-card/60 px-3 py-1.5 md:flex">
          <Target className="size-3.5 text-primary" />
          <span className="text-xs text-muted-foreground">Mastery:</span>
          <span className="text-xs font-semibold tabular-nums text-foreground">
            {currentWorkspace.overallMastery}%
          </span>
          <Badge
            variant={(currentWorkspace.masteryDelta || 0) < 0 ? 'warning' : 'success'}
            size="sm"
            className="ml-0.5 text-[10px]"
          >
            {(currentWorkspace.masteryDelta || 0) >= 0 ? '+' : ''}
            {currentWorkspace.masteryDelta || 0}%
          </Badge>
        </div>
      </div>

      {/* Center / Right: Search & Actions */}
      <div className="flex items-center gap-2 md:gap-3">
        {/* Workspace search (Ctrl/Cmd + K) */}
        <div className="hidden md:block">
          <CommandSearch workspaceId={currentWorkspace.id} />
        </div>

        {/* Theme Toggle Button - Mandatory Global Presence */}
        <ThemeToggle />

        <NotificationBell />

        {/* User Profile */}
        <UserMenu />
      </div>
    </header>
  )
}
