'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  CalendarCheck,
  CheckCircle2,
  Clock,
  Zap,
  MessagesSquare,
  Layers,
  BookOpen,
  ArrowRight,
  Sparkles,
  Target,
  Plus,
  CalendarX2,
  Flag,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  StudyPlan,
  StudyTask,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'
import { TargetDateEditor } from '@/components/workspace/target-date-editor'
import { formatLongDate } from '@/lib/dates'

export default function StudyPlanPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [studyPlan, setStudyPlan] = useState<StudyPlan | null>(null)
  const [activeTab, setActiveTab] = useState<'today' | 'this_week' | 'upcoming'>('today')

  const [editingDate, setEditingDate] = useState(false)

  async function loadPlan() {
    const [ws, sp] = await Promise.all([
      workspaceService.getWorkspaceById(workspaceId),
      workspaceService.getStudyPlan(workspaceId),
    ])
    setWorkspace(ws)
    setStudyPlan(sp)
  }

  useEffect(() => {
    if (!workspaceId) return
    loadPlan()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspaceId])

  const onTargetSaved = async () => {
    setEditingDate(false)
    await loadPlan()
  }

  if (!studyPlan) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8">
        <p className="text-xs text-muted-foreground">Loading study plan...</p>
      </div>
    )
  }

  const tasks = studyPlan.tasks.filter((t) => t.scheduledFor === activeTab)

  const handleToggle = async (taskId: string) => {
    await workspaceService.toggleStudyTask(workspaceId, taskId)
    const updated = await workspaceService.getStudyPlan(workspaceId)
    setStudyPlan(updated)
  }

  return (
    <div className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6 md:py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              Adaptive Scheduler
            </span>
            <span className="text-muted-foreground">•</span>
            <span className="text-xs text-muted-foreground">{workspace?.name}</span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-foreground md:text-3xl">
            Personalized Study Plan
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Structured daily actions adapted to your retention half-life and knowledge gaps.
          </p>
        </div>

        {/* Schedule Tabs (hidden when there is no plan because the target date has passed) */}
        <div className={cn('flex rounded-2xl border border-border bg-card p-1', studyPlan.targetPassed && 'hidden')}>
          {(['today', 'this_week', 'upcoming'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={cn(
                'rounded-xl px-4 py-1.5 text-xs font-semibold capitalize transition-all',
                activeTab === tab
                  ? 'bg-primary text-primary-foreground shadow-soft'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              {tab.replace('_', ' ')}
            </button>
          ))}
        </div>
      </div>

      {studyPlan.targetPassed ? (
        <div className="rounded-3xl border border-warning/40 bg-warning/5 p-6 shadow-soft">
          <div className="flex items-start gap-3">
            <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-warning/15 text-warning">
              <CalendarX2 className="size-5" />
            </span>
            <div className="flex-1 space-y-3">
              <div>
                <h3 className="font-display text-base font-semibold text-foreground">Your target date has passed</h3>
                <p className="mt-1 text-sm text-muted-foreground">
                  The target completion date for this workspace was{' '}
                  <span className="font-semibold text-foreground">{formatLongDate(studyPlan.targetDate)}</span>, so no
                  study plan is created. Choose a new target date to get a fresh plan built from your weak topics.
                </p>
              </div>
              <div className="max-w-md">
                <TargetDateEditor workspaceId={workspaceId} currentDate={studyPlan.targetDate} onSaved={onTargetSaved} />
              </div>
            </div>
          </div>
        </div>
      ) : (
      <>
      {/* Target Tracker Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">Today&apos;s Target</span>
            <Badge variant="default" size="sm">
              {studyPlan.todayCompletedMinutes} / {studyPlan.dailyTargetMinutes} mins
            </Badge>
          </div>
          <div className="mt-3">
            <Progress
              value={(studyPlan.todayCompletedMinutes / studyPlan.dailyTargetMinutes) * 100}
              className="h-2"
            />
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {studyPlan.todayCompletedMinutes >= studyPlan.dailyTargetMinutes
              ? '🎉 Daily target completed!'
              : `${studyPlan.dailyTargetMinutes - studyPlan.todayCompletedMinutes} minutes remaining today`}
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-muted-foreground">Weekly Target</span>
            <Badge variant="neutral" size="sm">
              {studyPlan.weekCompletedMinutes} / {studyPlan.weeklyTargetMinutes} mins
            </Badge>
          </div>
          <div className="mt-3">
            <Progress
              value={(studyPlan.weekCompletedMinutes / studyPlan.weeklyTargetMinutes) * 100}
              className="h-2"
            />
          </div>
          <p className="mt-2 text-[11px] text-muted-foreground">Paced for target milestone completion</p>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft sm:col-span-2 lg:col-span-1">
          <div className="flex items-center justify-between">
            <span className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
              <Flag className="size-3.5 text-primary" />
              Target Completion
            </span>
            {studyPlan.daysRemaining != null ? (
              <Badge variant={studyPlan.daysRemaining <= 7 ? 'warning' : 'success'} size="sm">
                {studyPlan.daysRemaining === 0
                  ? 'Due today'
                  : `${studyPlan.daysRemaining} day${studyPlan.daysRemaining === 1 ? '' : 's'} left`}
              </Badge>
            ) : null}
          </div>
          <p className="mt-2 font-display text-lg font-semibold text-foreground">
            {studyPlan.targetDate ? formatLongDate(studyPlan.targetDate) : 'No target date set'}
          </p>
          {editingDate ? (
            <div className="mt-3">
              <TargetDateEditor workspaceId={workspaceId} currentDate={studyPlan.targetDate} onSaved={onTargetSaved} />
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setEditingDate(true)}
              className="mt-2 text-[11px] font-semibold text-primary hover:opacity-80"
            >
              Change target date
            </button>
          )}
        </div>
      </div>

      {/* Task List */}
      <div className="rounded-3xl border border-border bg-card p-6 shadow-soft space-y-4">
        <div className="flex items-center justify-between border-b border-border pb-3">
          <h3 className="font-display text-sm font-semibold text-foreground">
            Scheduled Tasks ({tasks.length})
          </h3>
          <span className="text-xs text-muted-foreground">Click task to toggle completion</span>
        </div>

        <div className="flex flex-col gap-3">
          {tasks.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">No tasks scheduled for this period.</p>
          ) : (
            tasks.map((task) => (
              <div
                key={task.id}
                className={cn(
                  'flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border p-4 transition-all',
                  task.completed
                    ? 'border-border/60 bg-background/30 opacity-70'
                    : 'border-border bg-background hover:border-primary/40'
                )}
              >
                <div className="flex items-start gap-3">
                  <button
                    onClick={() => handleToggle(task.id)}
                    className="mt-0.5 shrink-0"
                    aria-label="Toggle task completion"
                  >
                    {task.completed ? (
                      <CheckCircle2 className="size-5 text-success" />
                    ) : (
                      <div className="size-5 rounded-lg border border-border bg-card" />
                    )}
                  </button>
                  <div>
                    <p
                      className={cn(
                        'text-xs md:text-sm font-medium text-foreground',
                        task.completed && 'line-through text-muted-foreground'
                      )}
                    >
                      {task.title}
                    </p>
                    <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                      <span>{task.topicName}</span>
                      <span>•</span>
                      <span>{task.estimatedMinutes} mins</span>
                      <span>•</span>
                      <Badge
                        variant={task.priority === 'high' ? 'destructive' : 'neutral'}
                        size="sm"
                        className="text-[9px] uppercase font-bold"
                      >
                        {task.priority} Priority
                      </Badge>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  <Link
                    href={`/dashboard/workspace/${workspaceId}/${
                      task.type === 'quiz' ? 'quiz' : task.type === 'flashcard' ? 'flashcards' : 'tutor'
                    }`}
                    className="inline-flex items-center gap-1 rounded-xl bg-primary/10 px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/20"
                  >
                    <span>Launch</span>
                    <ArrowRight className="size-3" />
                  </Link>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
      </>
      )}
    </div>
  )
}
