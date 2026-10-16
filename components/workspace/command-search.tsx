'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { BookOpen, Command, FileText, Layers, Loader2, Quote, Search } from 'lucide-react'
import { cn } from '@/lib/utils'

interface SearchResult {
  type: 'topic' | 'document' | 'flashcard' | 'passage'
  title: string
  snippet: string
  link: string
  meta?: string | null
}

const GROUPS: Record<SearchResult['type'], { label: string; icon: typeof Search }> = {
  topic: { label: 'Topics', icon: BookOpen },
  document: { label: 'Documents', icon: FileText },
  flashcard: { label: 'Flashcards', icon: Layers },
  passage: { label: 'In your notes', icon: Quote },
}

function highlight(text: string, query: string) {
  const terms = query
    .toLowerCase()
    .split(/\s+/)
    .filter((t) => t.length >= 2)
    .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  if (!terms.length || !text) return text
  const parts = text.split(new RegExp(`(${terms.join('|')})`, 'gi'))
  return parts.map((p, i) =>
    terms.some((t) => new RegExp(`^${t}$`, 'i').test(p)) ? (
      <mark key={i} className="rounded bg-primary/15 px-0.5 text-foreground">
        {p}
      </mark>
    ) : (
      <span key={i}>{p}</span>
    ),
  )
}

/** Header search for one workspace: Ctrl/Cmd + K to focus, arrow keys to move, Enter to open. */
export function CommandSearch({ workspaceId }: { workspaceId: string }) {
  const router = useRouter()
  const inputRef = useRef<HTMLInputElement>(null)
  const boxRef = useRef<HTMLDivElement>(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [isMac, setIsMac] = useState(false)

  useEffect(() => {
    setIsMac(/mac|iphone|ipad/i.test(navigator.platform || navigator.userAgent))
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        setOpen(true)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  // Debounced search; stale responses are ignored
  useEffect(() => {
    const q = query.trim()
    if (q.length < 2) {
      setResults([])
      setLoading(false)
      return
    }
    setLoading(true)
    const controller = new AbortController()
    const t = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/v1/workspaces/${encodeURIComponent(workspaceId)}/search?q=${encodeURIComponent(q)}`,
          { credentials: 'same-origin', signal: controller.signal },
        )
        const data = res.ok ? await res.json() : { results: [] }
        setResults(data.results || [])
        setActive(0)
      } catch (err: any) {
        if (err?.name !== 'AbortError') setResults([])
      } finally {
        if (!controller.signal.aborted) setLoading(false)
      }
    }, 220)
    return () => {
      clearTimeout(t)
      controller.abort()
    }
  }, [query, workspaceId])

  const grouped = useMemo(() => {
    const order: SearchResult['type'][] = ['topic', 'document', 'flashcard', 'passage']
    return order
      .map((type) => ({ type, items: results.filter((r) => r.type === type) }))
      .filter((g) => g.items.length > 0)
  }, [results])
  const flat = grouped.flatMap((g) => g.items)

  function go(r: SearchResult | undefined) {
    if (!r || !r.link.startsWith('/') || r.link.startsWith('//')) return
    setOpen(false)
    setQuery('')
    inputRef.current?.blur()
    router.push(r.link)
  }

  const showPanel = open && query.trim().length >= 2

  return (
    <div ref={boxRef} className="relative w-48 lg:w-72">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
      <input
        ref={inputRef}
        type="search"
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={(e) => {
          if (e.key === 'ArrowDown') {
            e.preventDefault()
            setActive((a) => Math.min(flat.length - 1, a + 1))
          } else if (e.key === 'ArrowUp') {
            e.preventDefault()
            setActive((a) => Math.max(0, a - 1))
          } else if (e.key === 'Enter') {
            e.preventDefault()
            go(flat[active])
          } else if (e.key === 'Escape') {
            setOpen(false)
            inputRef.current?.blur()
          }
        }}
        placeholder="Search topics, notes, cards…"
        aria-label="Search this workspace"
        role="combobox"
        aria-expanded={showPanel}
        aria-controls="workspace-search-results"
        aria-autocomplete="list"
        className="h-9 w-full rounded-xl border border-input bg-card pl-8 pr-12 text-xs text-foreground outline-none transition-colors placeholder:text-muted-foreground/70 focus:border-ring focus:ring-2 focus:ring-ring/20 [&::-webkit-search-cancel-button]:hidden"
      />
      <kbd className="pointer-events-none absolute right-2.5 top-1/2 hidden -translate-y-1/2 items-center gap-0.5 rounded border border-border bg-muted px-1 text-[9px] font-medium text-muted-foreground lg:flex">
        {isMac ? <Command className="size-2.5" /> : 'Ctrl'} K
      </kbd>

      {showPanel && (
        <div
          id="workspace-search-results"
          role="listbox"
          className="absolute left-0 z-50 mt-2 w-[min(28rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-border bg-card shadow-card animate-in fade-in zoom-in-95 duration-100"
        >
          <div className="max-h-[min(26rem,65vh)] overflow-y-auto p-2">
            {loading && flat.length === 0 ? (
              <div className="flex items-center justify-center gap-2 py-6 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" />
                Searching…
              </div>
            ) : flat.length === 0 ? (
              <p className="px-3 py-6 text-center text-xs text-muted-foreground">
                No matches for “{query.trim()}”. Try a topic name or a keyword from your notes.
              </p>
            ) : (
              grouped.map((g) => {
                const Icon = GROUPS[g.type].icon
                return (
                  <div key={g.type} className="mb-1 last:mb-0">
                    <p className="px-2.5 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      {GROUPS[g.type].label}
                    </p>
                    {g.items.map((r) => {
                      const index = flat.indexOf(r)
                      return (
                        <button
                          key={`${r.type}-${index}`}
                          type="button"
                          role="option"
                          aria-selected={index === active}
                          onMouseEnter={() => setActive(index)}
                          onClick={() => go(r)}
                          className={cn(
                            'flex w-full gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors',
                            index === active ? 'bg-accent/60' : 'hover:bg-accent/40',
                          )}
                        >
                          <Icon className="mt-0.5 size-3.5 shrink-0 text-primary" />
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-xs font-medium text-foreground">
                              {highlight(r.title, query)}
                            </span>
                            {r.snippet ? (
                              <span className="mt-0.5 line-clamp-2 block text-[11px] leading-relaxed text-muted-foreground">
                                {highlight(r.snippet, query)}
                              </span>
                            ) : null}
                            {r.meta ? <span className="mt-0.5 block text-[10px] text-muted-foreground/80">{r.meta}</span> : null}
                          </span>
                        </button>
                      )
                    })}
                  </div>
                )
              })
            )}
          </div>
          <div className="flex items-center justify-between border-t border-border px-3 py-1.5 text-[10px] text-muted-foreground">
            <span>↑ ↓ to move · Enter to open</span>
            <span>Esc to close</span>
          </div>
        </div>
      )}
    </div>
  )
}
