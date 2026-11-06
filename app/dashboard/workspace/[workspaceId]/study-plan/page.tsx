'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'next/navigation'
import { AlertTriangle, CalendarCheck, CalendarX2, CheckCircle2, Flag, Loader2, Plus, TrendingUp } from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import type { StudyPlan, StudyTask, Workspace } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'
import { TargetDateEditor } from '@/components/workspace/target-date-editor'
import { StudyTaskRow } from '@/components/study-plan/study-task-row'
import { formatLongDate, relativeDayLabel } from '@/lib/dates'

type Tab = 'today' | 'this_week' | 'upcoming'
const TAB_LABEL: Record<Tab, string> = { today: 'Today', this_week: 'This week', upcoming: 'Later' }

function pct(part: number, whole: number): number {
  return whole > 0 ? Math.min(100, Math.round((part / whole) * 100)) : 0
}

export default function StudyPlanPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [plan, setPlan] = useState<StudyPlan | null>(null)
  const [loadError, setLoadError] = useState(false)
  const [activeTab, setActiveTab] = useState<Tab>('today')
  const [editingDate, setEditingDate] = useState(false)
  const [busyTask, setBusyTask] = useState<string | null>(null)
  const [planningMore, setPlanningMore] = useState(false)
  const [savingMinutes, setSavingMinutes] = useState(false)
  const [notice, setNotice] = useState<string | null>(null)

  const loadPlan = useCallback(async () => {
    const [ws, sp] = await Promise.all([
      workspaceService.getWorkspaceById(workspaceId),
      workspaceService.getStudyPlan(workspaceId),
    ])
    setWorkspace(ws)
    setPlan(sp)
    setLoadError(!sp)
  }, [workspaceId])

  useEffect(() => {
    if (workspaceId) loadPlan()
  }, [workspaceId, loadPlan])

  const flash = (msg: string) => {
    setNotice(msg)
    setTimeout(() => setNotice(null), 3500)
  }

  const byTab = useMemo(() => {
    const groups: Record<Tab, StudyTask[]> = { today: [], this_week: [], upcoming: [] }
    for (const t of plan?.tasks || []) groups[t.scheduledFor]?.push(t)
    return groups
  }, [plan])

  const handleToggle = async (task: StudyTask) => {
    setBusyTask(task.id)
    const updated = await workspaceService.toggleStudyTask(workspaceId, task.id)
    setBusyTask(null)
    if (updated) {
      setPlan(updated)
      if (!task.completed && task.scheduledFor !== 'today') flash('Nice, done ahead of plan. It now counts for today.')
    } else {
      flash('That task could not be updated. The plan was refreshed.')
      await loadPlan()
    }
  }

  const handlePlanMore = async () => {
    setPlanningMore(true)
    const updated = await workspaceService.planMoreForToday(workspaceId)
    setPlanningMore(false)
    if (updated) {
      setPlan(updated)
      setActiveTab('today')
      flash("Today's list was rebuilt from your latest results.")
    }
  }

  const useNeededMinutes = async () => {
    if (!plan) return
    setSavingMinutes(true)
    try {
      await tutorApiClient.updateWorkspace(workspaceId, { dailyTargetMinutes: plan.neededDailyMinutes })
      await loadPlan()
      flash(`Daily target set to ${plan.neededDailyMinutes} minutes.`)
    } catch (e: any) {
      flash(e?.message || 'Could not update the daily target.')
    } finally {
      setSavingMinutes(false)
    }
  }

  const onTargetSaved = async () => {
    setEditingDate(false)
    await loadPlan()
  }

  if (!plan) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8">
        <p className="text-xs text-muted-foreground">
          {loadError ? 'The study plan could not be loaded. Check your connection and refresh.' : 'Loading study plan...'}
        </p>
      </div>
    )
  }

  const today = byTab.today
  const todayOpen = today.filter((t) => !t.completed).length
  const cov = plan.coverage
  const tasks = byTab[activeTab]
  const dateGroups: { date: string; items: StudyTask[] }[] = []
  for (const t of tasks) {
    const last = dateGroups[dateGroups.length - 1]
    if (last && last.date === t.scheduledDate) last.items.push(t)
    else dateGroups.push({ date: t.scheduledDate, items: [t] })
  }

  return (
    <div className="mx-auto w-full max-w-[1360px] space-y-6 px-4 py-6 md:px-6 md:py-8">
      {notice ? (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-xs font-semibold text-foreground shadow-card animate-in fade-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 className="size-4 text-success" />
          {notice}
        </div>
      ) : null}

      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">Adaptive scheduler</span>
            <span className="text-muted-foreground">•</span>
            <span className="text-xs text-muted-foreground">{workspace?.name}</span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-foreground md:text-3xl">Study Plan</h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Every topic in your notes, planned day by day
            {plan.targetDate ? ` until ${formatLongDate(plan.targetDate)}` : ''}. It adapts to your quiz results.
          </p>
        </div>
        {!plan.targetPassed ? (
          <button
            type="button"
            onClick={handlePlanMore}
            disabled={planningMore}
            className="inline-flex items-center justify-center gap-1.5 rounded-xl border border-border bg-card px-4 py-2 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40 disabled:opacity-60"
          >
            {planningMore ? <Loader2 className="size-3.5 animate-spin" /> : <Plus className="size-3.5" />}
            {todayOpen === 0 && today.length > 0 ? 'Plan more for today' : "Refresh today's list"}
          </button>
        ) : null}
      </div>

      {plan.targetPassed ? (
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
                  <span className="font-semibold text-foreground">{formatLongDate(plan.targetDate)}</span>. Choose a new
                  target date and your plan is rebuilt from where you are now.
                </p>
              </div>
              <div className="max-w-md">
                <TargetDateEditor workspaceId={workspaceId} currentDate={plan.targetDate} onSaved={onTargetSaved} />
              </div>
            </div>
          </div>
        </div>
      ) : (
        <>
          {/* Pace */}
          {plan.coverage.totalConcepts > 0 ? (
            plan.onTrack ? (
              <div className="flex items-start gap-3 rounded-3xl border border-success/30 bg-success/5 p-4 text-xs">
                <TrendingUp className="mt-0.5 size-4 shrink-0 text-success" />
                <p className="text-muted-foreground">
                  <span className="font-semibold text-foreground">On track.</span>{' '}
                  {plan.expectedFinishDate
                    ? `All ${cov.totalConcepts} concepts are planned by ${formatLongDate(plan.expectedFinishDate)}`
                    : 'Every concept is covered'}
                  {plan.targetDate ? `, within your target of ${formatLongDate(plan.targetDate)}.` : '.'}
                </p>
              </div>
            ) : (
              <div className="flex flex-col gap-3 rounded-3xl border border-warning/40 bg-warning/5 p-4 text-xs sm:flex-row sm:items-center">
                <AlertTriangle className="size-4 shrink-0 text-warning" />
                <p className="flex-1 text-muted-foreground">
                  <span className="font-semibold text-foreground">You need more time per day.</span> To cover all{' '}
                  {cov.totalConcepts} concepts by {formatLongDate(plan.targetDate)}, plan about{' '}
                  <span className="font-semibold text-foreground">{plan.neededDailyMinutes} minutes a day</span> (your
                  target is {plan.dailyTargetMinutes}). The plan below already uses that pace.
                </p>
                <div className="flex shrink-0 gap-2">
                  <button
                    type="button"
                    onClick={useNeededMinutes}
                    disabled={savingMinutes}
                    className="rounded-xl bg-primary px-3 py-1.5 font-semibold text-primary-foreground hover:opacity-90 disabled:opacity-60"
                  >
                    Set {plan.neededDailyMinutes} min/day
                  </button>
                  <button
                    type="button"
                    onClick={() => setEditingDate(true)}
                    className="rounded-xl border border-border bg-card px-3 py-1.5 font-semibold text-foreground hover:bg-accent/40"
                  >
                    Move target date
                  </button>
                </div>
              </div>
            )
          ) : null}

          {/* Trackers */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground">Today</span>
                <Badge variant="default" size="sm">
                  {plan.todayCompletedMinutes} / {plan.dailyTargetMinutes} min
                </Badge>
              </div>
              <Progress value={pct(plan.todayCompletedMinutes, plan.dailyTargetMinutes)} className="mt-3 h-2" />
              <p className="mt-2 text-[11px] text-muted-foreground">
                {plan.todayCompletedMinutes >= plan.dailyTargetMinutes
                  ? 'Daily target reached. Great work!'
                  : `${plan.dailyTargetMinutes - plan.todayCompletedMinutes} min to go · ${todayOpen} task${todayOpen === 1 ? '' : 's'} left`}
              </p>
            </div>

            <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground">This week</span>
                <Badge variant="neutral" size="sm">
                  {plan.weekCompletedMinutes} / {plan.weeklyTargetMinutes} min
                </Badge>
              </div>
              <Progress value={pct(plan.weekCompletedMinutes, plan.weeklyTargetMinutes)} className="mt-3 h-2" />
              <p className="mt-2 text-[11px] text-muted-foreground">Monday to Sunday · resets every week</p>
            </div>

            <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-muted-foreground">Concepts</span>
                <Badge variant="success" size="sm">
                  {cov.mastered} / {cov.totalConcepts} mastered
                </Badge>
              </div>
              <div className="mt-3 flex h-2 overflow-hidden rounded-full bg-secondary" aria-hidden>
                <div className="bg-success" style={{ width: `${pct(cov.mastered, cov.totalConcepts)}%` }} />
                <div className="bg-warning" style={{ width: `${pct(cov.inProgress, cov.totalConcepts)}%` }} />
              </div>
              <p className="mt-2 text-[11px] text-muted-foreground">
                {cov.totalConcepts === 0
                  ? 'Appears once your notes are processed'
                  : `${cov.inProgress} in progress · ${cov.notStarted} not started`}
              </p>
            </div>

            <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
              <div className="flex items-center justify-between">
                <span className="flex items-center gap-1.5 text-xs font-semibold text-muted-foreground">
                  <Flag className="size-3.5 text-primary" />
                  Target
                </span>
                {plan.daysRemaining != null ? (
                  <Badge variant={plan.daysRemaining <= 7 ? 'warning' : 'success'} size="sm">
                    {plan.daysRemaining === 0
                      ? 'Due today'
                      : `${plan.daysRemaining} day${plan.daysRemaining === 1 ? '' : 's'} left`}
                  </Badge>
                ) : null}
              </div>
              <p className="mt-2 font-display text-lg font-semibold text-foreground">
                {plan.targetDate ? formatLongDate(plan.targetDate) : 'No target date set'}
              </p>
              {editingDate ? (
                <div className="mt-3">
                  <TargetDateEditor workspaceId={workspaceId} currentDate={plan.targetDate} onSaved={onTargetSaved} />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setEditingDate(true)}
                  className="mt-1 text-[11px] font-semibold text-primary hover:opacity-80"
                >
                  Change target date
                </button>
              )}
            </div>
          </div>

          {/* Tasks */}
          <div className="space-y-4 rounded-3xl border border-border bg-card p-4 shadow-soft md:p-6">
            <div className="flex flex-col gap-3 border-b border-border pb-3 sm:flex-row sm:items-center sm:justify-between">
              <h3 className="flex items-center gap-2 font-display text-sm font-semibold text-foreground">
                <CalendarCheck className="size-4 text-primary" />
                {activeTab === 'today' ? `Today · ${relativeDayLabel(plan.date) === 'Today' ? formatLongDate(plan.date) : relativeDayLabel(plan.date)}` : TAB_LABEL[activeTab]}
              </h3>
              <div className="flex rounded-2xl border border-border bg-background p-1" role="tablist">
                {(['today', 'this_week', 'upcoming'] as const).map((tab) => (
                  <button
                    key={tab}
                    role="tab"
                    aria-selected={activeTab === tab}
                    onClick={() => setActiveTab(tab)}
                    className={cn(
                      'rounded-xl px-3 py-1.5 text-xs font-semibold transition-all',
                      activeTab === tab ? 'bg-primary text-primary-foreground shadow-soft' : 'text-muted-foreground hover:text-foreground'
                    )}
                  >
                    {TAB_LABEL[tab]} <span className="opacity-70">({byTab[tab].length})</span>
                  </button>
                ))}
              </div>
            </div>

            {tasks.length === 0 ? (
              <p className="py-10 text-center text-xs text-muted-foreground">
                {activeTab === 'today'
                  ? 'Nothing planned for today.'
                  : plan.coverage.totalConcepts === 0
                    ? 'Your plan fills in once your notes are processed.'
                    : 'Nothing planned for this period. Everything is covered earlier.'}
              </p>
            ) : (
              <div className="space-y-5">
                {dateGroups.map((group) => (
                  <div key={group.date} className="space-y-2.5">
                    {activeTab !== 'today' ? (
                      <div className="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        <span>{relativeDayLabel(group.date)}</span>
                        <span>{group.items.reduce((acc, t) => acc + t.estimatedMinutes, 0)} min</span>
                      </div>
                    ) : null}
                    {group.items.map((task) => (
                      <StudyTaskRow key={task.id} task={task} onToggle={handleToggle} busy={busyTask === task.id} />
                    ))}
                  </div>
                ))}
              </div>
            )}
            {activeTab !== 'today' && tasks.length > 0 ? (
              <p className="text-center text-[11px] text-muted-foreground">
                Later days are re-planned after every quiz. Tick a task here to do it ahead of time.
              </p>
            ) : null}
          </div>
        </>
      )}
    </div>
  )
}
