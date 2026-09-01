'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import {
  Braces,
  Cpu,
  BrainCircuit,
  Network,
  FolderKanban,
  Check,
  ChevronDown,
  Plus,
} from 'lucide-react'
import { Workspace } from '@/lib/types/domain'
import { cn } from '@/lib/utils'

interface WorkspaceSwitcherProps {
  workspaces: Workspace[]
  currentWorkspace: Workspace
  onCreateWorkspaceClick?: () => void
}

const iconMap: Record<string, typeof Braces> = {
  Braces,
  Cpu,
  BrainCircuit,
  Network,
  FolderKanban,
}

export function WorkspaceSwitcher({
  workspaces,
  currentWorkspace,
  onCreateWorkspaceClick,
}: WorkspaceSwitcherProps) {
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  const router = useRouter()

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  const CurrentIcon = iconMap[currentWorkspace.iconName] || FolderKanban

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-2.5 rounded-xl border border-border bg-card px-3 py-1.5 text-left transition-all hover:border-primary/40 hover:bg-accent/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/20',
          open && 'border-primary/50 ring-2 ring-primary/10'
        )}
        aria-label="Switch workspace"
        aria-expanded={open}
      >
        <span className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
          <CurrentIcon className="size-4" />
        </span>
        <div className="flex flex-col leading-none">
          <span className="max-w-[140px] truncate text-xs font-semibold text-foreground sm:max-w-[200px]">
            {currentWorkspace.name}
          </span>
          <span className="mt-0.5 max-w-[140px] truncate text-[10px] text-muted-foreground sm:max-w-[180px]">
            {currentWorkspace.goal}
          </span>
        </div>
        <ChevronDown className={cn('ml-1 size-3.5 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="absolute left-0 z-50 mt-2 w-72 origin-top-left rounded-2xl border border-border bg-card p-2 shadow-card animate-in fade-in zoom-in-95 duration-100">
          <div className="px-2.5 py-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Your Workspaces
          </div>
          <div className="mt-1 flex flex-col gap-1 max-h-72 overflow-y-auto">
            {workspaces.map((ws) => {
              const Icon = iconMap[ws.iconName] || FolderKanban
              const isSelected = ws.id === currentWorkspace.id
              return (
                <button
                  key={ws.id}
                  onClick={() => {
                    setOpen(false)
                    if (!isSelected) {
                      router.push(`/dashboard/workspace/${ws.id}`)
                    }
                  }}
                  className={cn(
                    'flex items-center gap-2.5 rounded-xl p-2 text-left transition-colors',
                    isSelected
                      ? 'bg-primary/10 text-foreground'
                      : 'text-muted-foreground hover:bg-accent/50 hover:text-foreground'
                  )}
                >
                  <span
                    className={cn(
                      'flex size-8 shrink-0 items-center justify-center rounded-lg',
                      isSelected ? 'bg-primary text-primary-foreground' : 'bg-muted text-foreground'
                    )}
                  >
                    <Icon className="size-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs font-semibold text-foreground">{ws.name}</p>
                    <div className="flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{ws.documentCount} docs</span>
                      <span>•</span>
                      <span className="font-medium text-foreground">{ws.overallMastery}% mastery</span>
                    </div>
                  </div>
                  {isSelected && <Check className="size-4 text-primary shrink-0" />}
                </button>
              )
            })}
          </div>

          <div className="mt-2 border-t border-border pt-2">
            <button
              onClick={() => {
                setOpen(false)
                onCreateWorkspaceClick?.()
              }}
              className="flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
            >
              <Plus className="size-4" />
              <span>Create new workspace</span>
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
