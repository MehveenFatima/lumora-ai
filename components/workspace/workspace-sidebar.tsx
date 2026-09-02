'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  MessagesSquare,
  Zap,
  Layers,
  BookOpen,
  BarChart3,
  CalendarCheck,
  FileText,
  Clock,
  ArrowLeft,
  GraduationCap,
  Sparkles,
  ChevronRight,
  Home,
} from 'lucide-react'
import { Workspace } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface WorkspaceSidebarProps {
  workspace: Workspace
  onNavigate?: () => void
  className?: string
}

export function WorkspaceSidebar({ workspace, onNavigate, className }: WorkspaceSidebarProps) {
  const pathname = usePathname()
  const basePath = `/dashboard/workspace/${workspace.id}`
  const isRootActive = pathname === basePath

  const navItems = [
    { label: 'AI Tutor', href: `${basePath}/tutor`, icon: MessagesSquare, badge: 'Grounded' },
    { label: 'Adaptive Quiz', href: `${basePath}/quiz`, icon: Zap },
    { label: 'Flashcards', href: `${basePath}/flashcards`, icon: Layers, badge: workspace.flashcardsDueCount > 0 ? `${workspace.flashcardsDueCount}` : undefined },
    { label: 'Topics', href: `${basePath}/topics`, icon: BookOpen },
    { label: 'Analytics', href: `${basePath}/analytics`, icon: BarChart3 },
    { label: 'Study Plan', href: `${basePath}/study-plan`, icon: CalendarCheck },
    { label: 'Sources', href: `${basePath}/sources`, icon: FileText, badge: `${workspace.documentCount}` },
    { label: 'Activity', href: `${basePath}/activity`, icon: Clock },
  ]

  return (
    <aside
      className={cn(
        'flex h-full w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar px-3 py-4 transition-colors',
        className
      )}
    >
      {/* Brand Header */}
      <div className="flex items-center justify-between px-2 py-1">
        <Link href="/dashboard" className="flex items-center gap-2.5 group">
          <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-glow transition-transform group-hover:scale-105">
            <GraduationCap className="size-5" strokeWidth={2.25} />
          </div>
          <div className="flex flex-col leading-none">
            <span className="font-display text-[15px] font-semibold tracking-tight text-sidebar-foreground">
              Lumora<span className="text-primary">AI</span>
            </span>
            <span className="text-[10px] text-muted-foreground">Adaptive Workspace</span>
          </div>
        </Link>
      </div>

      {/* Global Dashboard Return */}
      <div className="mt-3 px-1">
        <Link
          href="/dashboard"
          onClick={onNavigate}
          className="flex items-center gap-2 rounded-lg px-2.5 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
        >
          <ArrowLeft className="size-3.5" />
          <span>All Workspaces</span>
        </Link>
      </div>

      {/* Primary Workspace Navigation (8 Core Modules) */}
      <div className="mt-4 flex flex-1 flex-col overflow-y-auto">
        <div className="px-2 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/70">
          Workspace Modules
        </div>
        <nav className="flex flex-col gap-0.5" aria-label="Workspace pages">
          {navItems.map((item) => {
            const isActive = pathname === item.href || pathname?.startsWith(`${item.href}/`)
            const Icon = item.icon

            return (
              <Link
                key={item.label}
                href={item.href}
                onClick={onNavigate}
                className={cn(
                  'group flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-primary text-primary-foreground font-semibold shadow-soft'
                    : 'text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground'
                )}
                aria-current={isActive ? 'page' : undefined}
              >
                <Icon
                  className={cn(
                    'size-4 shrink-0 transition-colors',
                    isActive ? 'text-primary-foreground' : 'text-muted-foreground group-hover:text-sidebar-foreground'
                  )}
                  strokeWidth={isActive ? 2.2 : 1.8}
                />
                <span className="flex-1 truncate">{item.label}</span>
                {item.badge && (
                  <Badge
                    variant={isActive ? 'outline' : 'neutral'}
                    size="sm"
                    className={cn(
                      'text-[10px] px-1.5 py-0',
                      isActive && 'border-primary-foreground/30 text-primary-foreground bg-primary-foreground/10'
                    )}
                  >
                    {item.badge}
                  </Badge>
                )}
              </Link>
            )
          })}
        </nav>
      </div>

      {/* Workspace Command Center Return Card */}
      <div className="mt-auto pt-3 border-t border-sidebar-border/80">
        <Link
          href={basePath}
          onClick={onNavigate}
          className={cn(
            'block rounded-xl border p-3 shadow-soft transition-all',
            isRootActive
              ? 'border-primary/40 bg-primary/5 ring-1 ring-primary/20'
              : 'border-sidebar-border bg-card/60 hover:border-primary/30 hover:bg-card'
          )}
        >
          <div className="flex items-center justify-between text-xs">
            <span className="font-semibold text-foreground truncate max-w-[130px]">{workspace.name}</span>
            <span className="text-[11px] font-bold tabular-nums text-primary">{workspace.overallMastery}%</span>
          </div>
          <div className="mt-2">
            <Progress value={workspace.overallMastery} className="h-1.5" />
          </div>
          <div className="mt-2.5 flex items-center justify-between text-[11px] text-muted-foreground">
            <span>{workspace.documentCount} sources</span>
            <span className="text-primary font-medium flex items-center gap-0.5">
              Command Center <ChevronRight className="size-3" />
            </span>
          </div>
        </Link>
      </div>
    </aside>
  )
}
