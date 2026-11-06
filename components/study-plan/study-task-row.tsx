'use client'

import Link from 'next/link'
import {
  ArrowRight,
  BookOpen,
  CheckCircle2,
  Flag,
  Layers,
  Loader2,
  RotateCcw,
  Sparkles,
  Target,
  Upload,
} from 'lucide-react'
import type { StudyTask, StudyTaskKind } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const KIND_STYLE: Record<StudyTaskKind, { icon: typeof BookOpen; className: string; label: string }> = {
  learn: { icon: BookOpen, className: 'bg-primary/12 text-primary', label: 'Learn' },
  practice: { icon: Target, className: 'bg-success/15 text-success', label: 'Practice' },
  review: { icon: RotateCcw, className: 'bg-destructive/12 text-destructive', label: 'Weak spot' },
  flashcards: { icon: Layers, className: 'bg-warning/15 text-warning', label: 'Flashcards' },
  final: { icon: Flag, className: 'bg-primary/12 text-primary', label: 'Final check' },
  setup: { icon: Sparkles, className: 'bg-secondary text-secondary-foreground', label: 'Get started' },
}

const ACTION_LABEL: Record<StudyTask['type'], string> = {
  tutor: 'Open tutor',
  quiz: 'Start quiz',
  flashcard: 'Review cards',
  reading: 'Upload',
  study: 'Open',
}

export function StudyTaskRow({
  task,
  onToggle,
  busy,
  compact,
  workspaceLabel,
}: {
  task: StudyTask
  onToggle?: (task: StudyTask) => void
  busy?: boolean
  compact?: boolean
  /** Shown on the dashboard, where tasks from several workspaces are listed together */
  workspaceLabel?: string
}) {
  const style = KIND_STYLE[task.kind] || KIND_STYLE.learn
  const Icon = task.type === 'reading' ? Upload : style.icon

  return (
    <div
      className={cn(
        'flex items-start gap-3 rounded-2xl border transition-all',
        compact ? 'p-3' : 'p-4',
        task.completed ? 'border-border/60 bg-background/30' : 'border-border bg-background hover:border-primary/40'
      )}
    >
      {onToggle ? (
        <button
          type="button"
          onClick={() => onToggle(task)}
          disabled={busy}
          className="mt-0.5 shrink-0 rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50"
          aria-label={task.completed ? `Mark "${task.title}" as not done` : `Mark "${task.title}" as done`}
          aria-pressed={task.completed}
        >
          {busy ? (
            <Loader2 className="size-5 animate-spin text-muted-foreground" />
          ) : task.completed ? (
            <CheckCircle2 className="size-5 text-success" />
          ) : (
            <span className="block size-5 rounded-lg border-2 border-border bg-card hover:border-primary" />
          )}
        </button>
      ) : null}

      <span
        className={cn(
          'hidden shrink-0 items-center justify-center rounded-xl sm:flex',
          compact ? 'size-8' : 'size-9',
          style.className,
          task.completed && 'opacity-60'
        )}
      >
        <Icon className="size-4" />
      </span>

      <div className="min-w-0 flex-1">
        <p
          className={cn(
            'font-medium text-foreground',
            compact ? 'text-xs' : 'text-sm',
            task.completed && 'text-muted-foreground line-through'
          )}
        >
          {task.title}
        </p>
        {!compact && task.description ? (
          <p className={cn('mt-0.5 text-xs text-muted-foreground', task.completed && 'opacity-70')}>
            {task.description}
          </p>
        ) : null}
        <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
          {workspaceLabel ? <span className="font-semibold text-foreground/80">{workspaceLabel}</span> : null}
          {workspaceLabel ? <span aria-hidden>•</span> : null}
          <span>{style.label}</span>
          {task.topic ? (
            <>
              <span aria-hidden>•</span>
              <span className="truncate">{task.topic}</span>
            </>
          ) : null}
          <span aria-hidden>•</span>
          <span>{task.estimatedMinutes} min</span>
          {task.priority === 'high' && !task.completed ? (
            <Badge variant="destructive" size="sm" className="text-[9px] font-bold uppercase">
              High priority
            </Badge>
          ) : null}
          {task.carriedOver && !task.completed ? (
            <Badge variant="warning" size="sm" className="text-[9px] font-bold uppercase">
              Carried over
            </Badge>
          ) : null}
          {task.doneAhead ? (
            <Badge variant="success" size="sm" className="text-[9px] font-bold uppercase">
              Done ahead
            </Badge>
          ) : null}
        </div>
      </div>

      {!task.completed ? (
        <Link
          href={task.href}
          className="inline-flex shrink-0 items-center gap-1 self-center rounded-xl bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/20"
        >
          <span className={cn(compact && 'sr-only sm:not-sr-only')}>{ACTION_LABEL[task.type] || 'Open'}</span>
          <ArrowRight className="size-3" />
        </Link>
      ) : null}
    </div>
  )
}
