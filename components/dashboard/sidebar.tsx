'use client'

import type { LucideIcon } from 'lucide-react'
import {
  LayoutDashboard,
  FolderKanban,
  MessagesSquare,
  Layers,
  Map,
  BarChart3,
  Sparkles,
  Settings,
  LifeBuoy,
  GraduationCap,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

type NavItem = {
  label: string
  icon: LucideIcon
  badge?: string
}

const primaryNav: NavItem[] = [
  { label: 'Overview', icon: LayoutDashboard },
  { label: 'Workspaces', icon: FolderKanban, badge: '6' },
  { label: 'AI Tutor', icon: MessagesSquare },
  { label: 'Flashcards', icon: Layers },
  { label: 'Roadmaps', icon: Map },
  { label: 'Analytics', icon: BarChart3 },
]

const secondaryNav: NavItem[] = [
  { label: 'Settings', icon: Settings },
  { label: 'Support', icon: LifeBuoy },
]

interface SidebarProps {
  active: string
  onNavigate: (label: string) => void
  className?: string
}

export function Sidebar({ active, onNavigate, className }: SidebarProps) {
  return (
    <aside
      className={cn(
        'flex h-full w-64 shrink-0 flex-col gap-1 border-r border-sidebar-border bg-sidebar px-3 py-4',
        className,
      )}
    >
      <div className="flex items-center gap-2.5 px-3 py-2">
        <div className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-[var(--shadow-glow)]">
          <GraduationCap className="size-5" strokeWidth={2.25} />
        </div>
        <div className="flex flex-col leading-none">
          <span className="font-display text-[15px] font-semibold tracking-tight text-sidebar-foreground">
            Lumora<span className="text-primary">AI</span>
          </span>
          <span className="text-[11px] text-muted-foreground">Adaptive Learning</span>
        </div>
      </div>

      <nav className="mt-4 flex flex-col gap-0.5">
        <p className="px-3 pb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground/70">
          Learn
        </p>
        {primaryNav.map((item) => {
          const isActive = active === item.label
          return (
            <button
              key={item.label}
              onClick={() => onNavigate(item.label)}
              className={cn(
                'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-sidebar-accent text-sidebar-accent-foreground'
                  : 'text-sidebar-foreground hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground',
              )}
              aria-current={isActive ? 'page' : undefined}
            >
              <item.icon
                className={cn('size-[18px] shrink-0', isActive ? 'text-primary' : 'text-muted-foreground group-hover:text-foreground')}
                strokeWidth={2}
              />
              <span className="flex-1 text-left">{item.label}</span>
              {item.badge ? (
                <Badge variant="neutral" size="sm" className="tabular-nums">
                  {item.badge}
                </Badge>
              ) : null}
            </button>
          )
        })}
      </nav>

      <div className="mt-auto flex flex-col gap-0.5">
        {secondaryNav.map((item) => (
          <button
            key={item.label}
            onClick={() => onNavigate(item.label)}
            className="group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent/50 hover:text-sidebar-accent-foreground"
          >
            <item.icon className="size-[18px] text-muted-foreground group-hover:text-foreground" strokeWidth={2} />
            {item.label}
          </button>
        ))}

        <div className="mt-3 rounded-xl border border-sidebar-border bg-gradient-to-b from-primary/10 to-transparent p-3.5">
          <div className="flex items-center gap-2">
            <Sparkles className="size-4 text-primary" />
            <span className="text-xs font-semibold text-sidebar-accent-foreground">Upgrade to Pro</span>
          </div>
          <p className="mt-1.5 text-[12px] leading-relaxed text-muted-foreground">
            Unlimited workspaces, longer documents, and priority AI models.
          </p>
          <button className="mt-3 w-full rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-primary-foreground transition-opacity hover:opacity-90">
            View plans
          </button>
        </div>
      </div>
    </aside>
  )
}
