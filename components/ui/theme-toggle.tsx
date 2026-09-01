'use client'

import { useState, useRef, useEffect } from 'react'
import { Sun, Moon, Laptop, ChevronDown } from 'lucide-react'
import { useTheme } from '@/lib/theme-provider'
import { cn } from '@/lib/utils'

interface ThemeToggleProps {
  className?: string
  showLabel?: boolean
}

export function ThemeToggle({ className, showLabel = false }: ThemeToggleProps) {
  const { theme, resolvedTheme, setTheme } = useTheme()
  const [open, setOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

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

  const options: Array<{ value: 'light' | 'dark' | 'system'; label: string; icon: typeof Sun }> = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Laptop },
  ]

  const ActiveIcon = resolvedTheme === 'dark' ? Moon : Sun

  return (
    <div className="relative inline-block text-left" ref={menuRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className={cn(
          'flex items-center gap-1.5 rounded-xl border border-border bg-card p-2 text-muted-foreground transition-colors hover:border-primary/40 hover:bg-accent/40 hover:text-foreground focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/20',
          className
        )}
        aria-label="Select theme"
        aria-expanded={open}
      >
        <ActiveIcon className="size-[18px] text-foreground" />
        {showLabel && (
          <span className="text-xs font-medium capitalize text-foreground">
            {theme}
          </span>
        )}
        <ChevronDown className={cn("size-3.5 transition-transform opacity-70", open && "rotate-180")} />
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-1.5 w-36 origin-top-right rounded-xl border border-border bg-card p-1 shadow-card animate-in fade-in zoom-in-95 duration-100">
          {options.map((opt) => {
            const Icon = opt.icon
            const isSelected = theme === opt.value
            return (
              <button
                key={opt.value}
                onClick={() => {
                  setTheme(opt.value)
                  setOpen(false)
                }}
                className={cn(
                  'flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors text-left',
                  isSelected
                    ? 'bg-primary/10 text-primary font-semibold'
                    : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground'
                )}
              >
                <Icon className="size-4 shrink-0" />
                <span className="flex-1">{opt.label}</span>
                {isSelected && (
                  <span className="size-1.5 rounded-full bg-primary" />
                )}
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}
