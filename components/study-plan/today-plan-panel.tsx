'use client'

import { useState } from 'react'
import Link from 'next/link'
import { AlertTriangle, CalendarCheck, CheckCircle2, ChevronDown, ChevronUp } from 'lucide-react'
import type { TodayPlan, TodayPlanTask } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { StudyTaskRow } from '@/components/study-plan/study-task-row'
import { formatLongDate } from '@/lib/dates'

const COLLAPSED_COUNT = 6

/** Dashboard section: today's tasks from every workspace, with tick-off. */
export function TodayPlanPanel({
  plan,
  onToggle,
  busyTask,
}: {
  plan: TodayPlan | null
  onToggle: (task: TodayPlanTask) => void
  busyTask: string | null
}) {
  const [expanded, setExpanded] = useState(false)

  if (!plan) {
    return (
      <section className="rounded-3xl border border-border bg-card p-6 shadow-soft">
        <h2 className="font-display text-lg font-semibold text-foreground">Today&apos;s Plan</h2>
        <p className="mt-2 text-xs text-muted-foreground">Loading today&apos;s plan...</p>
      </section>
    )
  }

  const target = plan.dailyTargetMinutes
  const progress = target > 0 ? Math.min(100, Math.round((plan.completedMinutes / target) * 100)) : 0
  const visible = expanded ? plan.tasks : plan.tasks.slice(0, COLLAPSED_COUNT)
  const allDone = plan.tasks.length > 0 && plan.openTasks === 0

  return (
    <section className="space-y-4 rounded-3xl border border-border bg-card p-5 shadow-soft md:p-6" aria-labelledby="today-plan-title">
      <div className="flex flex-col justify-between gap-3 md:flex-row md:items-end">
        <div>
          <h2 id="today-plan-title" className="flex items-center gap-2 font-display text-lg font-semibold text-foreground">
            <CalendarCheck className="size-5 text-primary" />
            Today&apos;s Plan
            <span className="text-sm font-normal text-muted-foreground">· {formatLongDate(plan.date)}</span>
          </h2>
          <p className="text-xs text-muted-foreground">
            Tasks from all your workspaces, planned around each target date and your latest quiz results.
          </p>
        </div>
        <div className="w-full max-w-xs">
          <div className="mb-1 flex items-center justify-between text-xs">
            <span className="text-muted-foreground">
              {plan.openTasks} task{plan.openTasks === 1 ? '' : 's'} left
            </span>
            <span className="font-semibold tabular-nums text-foreground">
              {plan.completedMinutes} / {target} min
            </span>
          </div>
          <Progress value={progress} className="h-2" />
        </div>
      </div>

      {plan.workspaces.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {plan.workspaces.map((w) => (
            <Link
              key={w.workspaceId}
              href={`/dashboard/workspace/${w.workspaceId}/study-plan`}
              className="inline-flex items-center gap-2 rounded-xl border border-border bg-background px-3 py-1.5 text-[11px] transition-colors hover:border-primary/40"
            >
              <span className="font-semibold text-foreground">{w.workspaceName}</span>
              {w.targetPassed ? (
                <Badge variant="warning" size="sm">Target passed</Badge>
              ) : (
                <>
                  <span className="text-muted-foreground">
                    {w.todayCompletedMinutes}/{w.dailyTargetMinutes} min
                    {w.daysRemaining != null ? ` · ${w.daysRemaining === 0 ? 'due today' : `${w.daysRemaining}d left`}` : ''}
                  </span>
                  {!w.onTrack ? (
                    <span className="inline-flex items-center gap-1 font-semibold text-warning" title={`About ${w.neededDailyMinutes} min a day are needed to finish on time`}>
                      <AlertTriangle className="size-3" /> Behind
                    </span>
                  ) : null}
                </>
              )}
            </Link>
          ))}
        </div>
      ) : null}

      {plan.tasks.length === 0 ? (
        <p className="py-6 text-center text-xs text-muted-foreground">
          Nothing planned for today. Open a workspace and upload your notes to get a plan.
        </p>
      ) : (
        <div className="space-y-2.5">
          {allDone ? (
            <div className="flex items-center gap-2 rounded-2xl border border-success/30 bg-success/5 p-3 text-xs font-semibold text-foreground">
              <CheckCircle2 className="size-4 text-success" />
              All done for today. Great work!
            </div>
          ) : null}
          {visible.map((task) => (
            <StudyTaskRow
              key={`${task.workspaceId}:${task.id}`}
              task={task}
              compact
              workspaceLabel={plan.workspaces.length > 1 ? task.workspaceName : undefined}
              onToggle={(t) => onToggle(t as TodayPlanTask)}
              busy={busyTask === `${task.workspaceId}:${task.id}`}
            />
          ))}
          {plan.tasks.length > COLLAPSED_COUNT ? (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="flex w-full items-center justify-center gap-1 rounded-xl py-2 text-xs font-semibold text-primary hover:bg-primary/5"
            >
              {expanded ? (
                <>
                  Show less <ChevronUp className="size-3.5" />
                </>
              ) : (
                <>
                  Show all {plan.tasks.length} tasks <ChevronDown className="size-3.5" />
                </>
              )}
            </button>
          ) : null}
        </div>
      )}
    </section>
  )
}
