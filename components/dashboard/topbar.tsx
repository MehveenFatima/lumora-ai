'use client'

import { Search, Bell, Plus, PanelLeft, Command } from 'lucide-react'

interface TopbarProps {
  onToggleSidebar?: () => void
}

export function Topbar({ onToggleSidebar }: TopbarProps) {
  return (
    <header className="sticky top-0 z-20 flex h-16 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur-xl md:px-6">
      <button
        onClick={onToggleSidebar}
        className="flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground lg:hidden"
        aria-label="Toggle sidebar"
      >
        <PanelLeft className="size-[18px]" />
      </button>

      <div className="relative hidden flex-1 items-center sm:flex md:max-w-md">
        <Search className="pointer-events-none absolute left-3 size-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search documents, workspaces, topics..."
          className="h-10 w-full rounded-xl border border-input bg-card pl-9 pr-16 text-sm text-foreground placeholder:text-muted-foreground/70 outline-none transition-colors focus:border-ring focus:ring-4 focus:ring-ring/12"
          aria-label="Search"
        />
        <kbd className="pointer-events-none absolute right-3 hidden items-center gap-0.5 rounded-md border border-border bg-muted px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground md:flex">
          <Command className="size-3" />K
        </kbd>
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button className="inline-flex h-10 items-center gap-2 rounded-xl bg-primary px-3.5 text-sm font-semibold text-primary-foreground shadow-[var(--shadow-glow)] transition-opacity hover:opacity-90">
          <Plus className="size-4" strokeWidth={2.5} />
          <span className="hidden sm:inline">New workspace</span>
        </button>

        <button
          className="relative flex size-10 items-center justify-center rounded-xl border border-border bg-card text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Notifications"
        >
          <Bell className="size-[18px]" />
          <span className="absolute right-2.5 top-2.5 size-2 rounded-full bg-primary ring-2 ring-card" />
        </button>

        <button className="flex items-center gap-2 rounded-xl border border-border bg-card py-1 pl-1 pr-2.5 transition-colors hover:bg-accent/50">
          <span className="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-chart-5 text-xs font-semibold text-primary-foreground">
            MA
          </span>
          <span className="hidden text-left leading-none md:block">
            <span className="block text-sm font-medium text-foreground">Mehveen A.</span>
            <span className="mt-0.5 block text-[11px] text-muted-foreground">Pro trial</span>
          </span>
        </button>
      </div>
    </header>
  )
}
