'use client'

import { useState, useEffect, useMemo } from 'react'
import {
  X,
  Trash2,
  Search,
  AlertTriangle,
  FolderKanban,
  FileText,
  Target,
  ArrowRight,
  CheckCircle2,
  Loader2,
} from 'lucide-react'
import { Workspace } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

interface DeleteWorkspaceModalProps {
  isOpen: boolean
  workspaces: Workspace[]
  onClose: () => void
  onDeleteWorkspace: (workspaceId: string) => Promise<void>
}

export function DeleteWorkspaceModal({
  isOpen,
  workspaces,
  onClose,
  onDeleteWorkspace,
}: DeleteWorkspaceModalProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null)
  const [step, setStep] = useState<'select' | 'confirm'>('select')
  const [isDeleting, setIsDeleting] = useState(false)

  useEffect(() => {
    if (isOpen) {
      setSearchQuery('')
      setSelectedWorkspaceId(null)
      setStep('select')
      setIsDeleting(false)
    }
  }, [isOpen])

  // Handle ESC key
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape' && isOpen && !isDeleting) {
        onClose()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, isDeleting, onClose])

  const filteredWorkspaces = useMemo(() => {
    const q = searchQuery.trim().toLowerCase()
    if (!q) return workspaces
    return workspaces.filter(
      (w) =>
        w.name.toLowerCase().includes(q) ||
        w.goal.toLowerCase().includes(q) ||
        w.description.toLowerCase().includes(q)
    )
  }, [workspaces, searchQuery])

  const selectedWorkspace = workspaces.find((w) => w.id === selectedWorkspaceId)

  if (!isOpen) return null

  const handleConfirmDelete = async () => {
    if (!selectedWorkspaceId) return
    setIsDeleting(true)
    try {
      await onDeleteWorkspace(selectedWorkspaceId)
      setIsDeleting(false)
      onClose()
    } catch (err) {
      console.error('Failed to delete workspace:', err)
      setIsDeleting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-background/80 backdrop-blur-sm transition-opacity"
        onClick={() => !isDeleting && onClose()}
        aria-hidden
      />

      {/* Modal Card */}
      <div className="relative w-full max-w-lg rounded-3xl border border-border bg-card p-6 shadow-card animate-in fade-in zoom-in-95 duration-150 sm:p-8">
        <button
          onClick={onClose}
          disabled={isDeleting}
          className="absolute right-5 top-5 flex size-8 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
          aria-label="Close modal"
        >
          <X className="size-4" />
        </button>

        {step === 'select' ? (
          <div>
            {/* Header */}
            <div className="flex items-center gap-3">
              <span className="flex size-10 items-center justify-center rounded-xl bg-destructive/10 text-destructive">
                <Trash2 className="size-5" />
              </span>
              <div>
                <h2 className="font-display text-lg font-semibold text-foreground">Delete Workspace</h2>
                <p className="text-xs text-muted-foreground">
                  Select a workspace to remove from your learning hub.
                </p>
              </div>
            </div>

            {/* Search Bar */}
            <div className="relative mt-5">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search workspaces..."
                className="h-10 w-full rounded-xl border border-input bg-background pl-9 pr-8 text-xs text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors focus:border-ring focus:ring-2 focus:ring-ring/20"
                autoFocus
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={() => setSearchQuery('')}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                >
                  <X className="size-3.5" />
                </button>
              )}
            </div>

            {/* Workspaces Selectable List */}
            <div className="mt-4 max-h-64 space-y-2 overflow-y-auto pr-1">
              {filteredWorkspaces.length === 0 ? (
                <p className="py-8 text-center text-xs text-muted-foreground">
                  No workspaces found matching &ldquo;{searchQuery}&rdquo;.
                </p>
              ) : (
                filteredWorkspaces.map((ws) => {
                  const isSelected = selectedWorkspaceId === ws.id
                  return (
                    <div
                      key={ws.id}
                      onClick={() => setSelectedWorkspaceId(ws.id)}
                      className={cn(
                        'flex items-start gap-3 rounded-2xl border p-3.5 transition-all cursor-pointer select-none',
                        isSelected
                          ? 'border-destructive/60 bg-destructive/5 ring-1 ring-destructive/30'
                          : 'border-border bg-background/60 hover:border-border hover:bg-accent/40'
                      )}
                    >
                      {/* Radio Indicator */}
                      <div className="mt-0.5 shrink-0">
                        <span
                          className={cn(
                            'flex size-4 items-center justify-center rounded-full border transition-colors',
                            isSelected
                              ? 'border-destructive bg-destructive text-destructive-foreground'
                              : 'border-muted-foreground/40 bg-card'
                          )}
                        >
                          {isSelected && <span className="size-1.5 rounded-full bg-white" />}
                        </span>
                      </div>

                      {/* Details */}
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center justify-between gap-2">
                          <p className="truncate text-xs font-semibold text-foreground">{ws.name}</p>
                          <span className="text-[11px] font-bold tabular-nums text-foreground">
                            {ws.overallMastery}% mastery
                          </span>
                        </div>
                        <p className="mt-0.5 truncate text-[11px] text-muted-foreground">{ws.goal}</p>
                        <div className="mt-2 flex items-center gap-3 text-[10px] text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <FileText className="size-3 text-primary" /> {ws.documentCount} sources
                          </span>
                          <span>•</span>
                          <span>Last active {ws.lastActive}</span>
                        </div>
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Bottom Actions */}
            <div className="mt-6 flex items-center justify-end gap-2.5 border-t border-border/80 pt-4">
              <button
                type="button"
                onClick={onClose}
                className="h-10 rounded-xl border border-border bg-background px-4 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={!selectedWorkspaceId}
                onClick={() => setStep('confirm')}
                className="flex h-10 items-center justify-center gap-2 rounded-xl bg-destructive px-5 text-xs font-semibold text-destructive-foreground transition-opacity hover:opacity-90 disabled:opacity-40"
              >
                <span>Delete Workspace</span>
                <ArrowRight className="size-3.5" />
              </button>
            </div>
          </div>
        ) : (
          /* STEP 2: CONFIRMATION STATE */
          <div className="animate-in fade-in duration-150">
            <div className="flex items-center gap-3">
              <span className="flex size-11 items-center justify-center rounded-2xl bg-destructive/15 text-destructive">
                <AlertTriangle className="size-6" />
              </span>
              <div>
                <h2 className="font-display text-lg font-semibold text-foreground">
                  Delete &ldquo;{selectedWorkspace?.name}&rdquo;?
                </h2>
                <p className="text-xs text-muted-foreground">This action will remove all associated workspace data.</p>
              </div>
            </div>

            <div className="mt-5 rounded-2xl border border-destructive/20 bg-destructive/5 p-4 text-xs text-foreground space-y-2">
              <p className="font-semibold text-destructive">Data deletion summary:</p>
              <p className="text-muted-foreground leading-relaxed">
                This will permanently remove the workspace from your learning hub, including its associated demo sources ({selectedWorkspace?.documentCount} documents), quiz attempt history, flashcard decks, topic mastery scores, self-adapting roadmap, and activity audit logs.
              </p>
            </div>

            <div className="mt-6 flex items-center justify-end gap-2.5">
              <button
                type="button"
                disabled={isDeleting}
                onClick={() => setStep('select')}
                className="h-10 rounded-xl border border-border bg-background px-4 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40 disabled:opacity-50"
              >
                Back
              </button>
              <button
                type="button"
                disabled={isDeleting}
                onClick={handleConfirmDelete}
                className="flex h-10 items-center justify-center gap-2 rounded-xl bg-destructive px-5 text-xs font-semibold text-destructive-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
              >
                {isDeleting ? (
                  <>
                    <Loader2 className="size-3.5 animate-spin" /> Deleting Workspace...
                  </>
                ) : (
                  <>
                    <Trash2 className="size-3.5" /> Yes, Delete Workspace
                  </>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
