'use client'

import { useState, useEffect, useCallback, useMemo } from 'react'
import Link from 'next/link'
import {
  FolderKanban,
  FileText,
  Flame,
  Target,
  Plus,
  Trash2,
  ArrowRight,
  Sparkles,
  Zap,
  Layers,
  Clock,
  TrendingUp,
  GraduationCap,
  Bell,
  Search,
  Command,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import { Workspace, LearningActivity, NotificationItem, AIRecommendation } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ThemeToggle } from '@/components/ui/theme-toggle'
import { CreateWorkspaceModal } from '@/components/workspace/create-workspace-modal'
import { DeleteWorkspaceModal } from '@/components/workspace/delete-workspace-modal'
import { cn } from '@/lib/utils'
import { computeStudyStreak } from '@/lib/learning-stats'
import { UserMenu } from '@/components/auth/user-menu'
import { NotificationBell } from '@/components/notifications/notification-bell'
import { firstNameOf, useCurrentUser } from '@/lib/api/auth-client'

export default function GlobalDashboardPage() {
  const currentUser = useCurrentUser()
  const [workspaces, setWorkspaces] = useState<Workspace[]>([])
  const [activities, setActivities] = useState<LearningActivity[]>([])
  const [notifications, setNotifications] = useState<NotificationItem[]>([])
  const [topRecommendation, setTopRecommendation] = useState<AIRecommendation | null>(null)
  const [createModalOpen, setCreateModalOpen] = useState(false)
  const [deleteModalOpen, setDeleteModalOpen] = useState(false)
  const [toastMessage, setToastMessage] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [backendError, setBackendError] = useState<string | null>(null)

  const loadDashboard = useCallback(async () => {
    setLoading(true)
    setBackendError(null)
    try {
      const health = await tutorApiClient.getHealth().catch(() => null)
      const isBackendHealthy =
        health &&
        (health.status === 'ok' || health.status === 'healthy' || health.backend === 'healthy')
      if (!isBackendHealthy) {
        setBackendError('FastAPI backend service is unreachable.')
      }
      const [ws, acts, notifs] = await Promise.all([
        workspaceService.getWorkspaces(),
        workspaceService.getActivities(),
        workspaceService.getNotifications(),
      ])
      setWorkspaces(ws)
      setActivities(acts)
      setNotifications(notifs)
      // Next-step banner: the BKT-based recommendation for the most recent workspace, if any
      setTopRecommendation(
        ws.length > 0 ? await workspaceService.getRecommendation(ws[0].id).catch(() => null) : null
      )
    } catch (err: any) {
      console.error(err)
      setBackendError(err.message || 'Failed to connect to backend service')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
  }, [loadDashboard])

  const showToast = (msg: string) => {
    setToastMessage(msg)
    setTimeout(() => {
      setToastMessage(null)
    }, 3000)
  }

  const handleDeleteWorkspace = async (workspaceId: string) => {
    await workspaceService.deleteWorkspace(workspaceId)
    const [updatedWs, updatedActs] = await Promise.all([
      workspaceService.getWorkspaces(),
      workspaceService.getActivities(),
    ])
    setWorkspaces(updatedWs)
    setActivities(updatedActs)
    showToast('Workspace deleted.')
  }

  const totalDocs = workspaces.reduce((acc, w) => acc + w.documentCount, 0)
  const avgMastery =
    workspaces.length > 0
      ? Math.round(workspaces.reduce((acc, w) => acc + w.overallMastery, 0) / workspaces.length)
      : 0
  const avgMasteryDelta =
    workspaces.length > 0
      ? Math.round(workspaces.reduce((acc, w) => acc + (w.masteryDelta || 0), 0) / workspaces.length)
      : 0

  // Learning streak computed from real persisted activity events
  const streakDays = useMemo(() => computeStudyStreak(activities || []), [activities])

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-3 text-xs font-semibold text-foreground shadow-card animate-in fade-in slide-in-from-bottom-3 duration-200">
          <CheckCircle2 className="size-4 text-success" />
          <span>{toastMessage}</span>
        </div>
      )}

      {/* Global Header */}
      <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border bg-background/85 px-4 backdrop-blur-xl md:px-8">
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-glow">
              <GraduationCap className="size-5" strokeWidth={2.25} />
            </span>
            <span className="font-display text-base font-semibold tracking-tight text-foreground">
              Lumora<span className="text-primary">AI</span>
            </span>
          </Link>
          <span className="hidden sm:inline-block text-xs font-semibold text-muted-foreground uppercase tracking-wider pl-2 border-l border-border">
            Global Learning Hub
          </span>
        </div>

        <div className="flex items-center gap-2 md:gap-2.5">
          {workspaces.length > 0 && (
            <Link
              href={`/dashboard/workspace/${workspaces[0].id}/quiz`}
              className="hidden sm:inline-flex items-center gap-1.5 rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
            >
              <Zap className="size-3.5 text-warning" />
              <span>Diagnostic Quiz</span>
            </Link>
          )}

          <button
            onClick={() => setCreateModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3.5 py-1.5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
          >
            <Plus className="size-3.5" />
            <span>New Workspace</span>
          </button>

          <button
            onClick={() => setDeleteModalOpen(true)}
            className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-card px-3 py-1.5 text-xs font-semibold text-muted-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
            aria-label="Delete workspace"
          >
            <Trash2 className="size-3.5" />
            <span className="hidden sm:inline">Delete Workspace</span>
          </button>

          <ThemeToggle />

          <NotificationBell />

          <UserMenu />
        </div>
      </header>

      {/* Main Container */}
      <main className="mx-auto w-full max-w-[1360px] px-4 py-8 md:px-8 space-y-8">
        {/* Welcome & Global Stats */}
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground">
              <span>Adaptive RAG Learning System</span>
              <span>•</span>
              <span className="text-success flex items-center gap-1">
                <span className="size-1.5 rounded-full bg-success animate-pulse" /> All Workspaces Synced
              </span>
            </div>
            <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
              Welcome back, {firstNameOf(currentUser?.name)}
            </h1>
            <p className="mt-1 text-xs text-muted-foreground">
              {streakDays > 0
                ? `You are currently maintaining a ${streakDays}-day learning streak. Select a workspace below to enter its grounded AI environment.`
                : 'Select a workspace below to enter its grounded AI environment and begin your adaptive learning journey.'}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setCreateModalOpen(true)}
              className="inline-flex items-center gap-2 rounded-2xl border border-primary/30 bg-primary/10 px-4 py-2.5 text-xs font-semibold text-primary transition-colors hover:bg-primary/20"
            >
              <Plus className="size-4" /> Create Learning Workspace
            </button>
            <button
              onClick={() => setDeleteModalOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-2xl border border-border bg-card px-3.5 py-2.5 text-xs font-semibold text-muted-foreground transition-colors hover:border-destructive/40 hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2 className="size-3.5" /> Delete Workspace
            </button>
          </div>
        </div>

        {/* Backend Connection Warning Banner */}
        {backendError && (
          <div className="flex items-center justify-between gap-4 rounded-2xl border border-destructive/40 bg-destructive/10 p-4 text-xs text-destructive">
            <div className="flex items-center gap-2.5">
              <AlertTriangle className="size-5 shrink-0" />
              <div>
                <span className="font-semibold">Backend Connection Issue:</span> {backendError}
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  Ensure the FastAPI backend service is running and accessible via the <code>/api/v1</code> proxy.
                </p>
              </div>
            </div>
            <button
              onClick={() => loadDashboard()}
              className="shrink-0 rounded-xl bg-destructive px-3.5 py-1.5 text-xs font-semibold text-destructive-foreground shadow-sm hover:opacity-90"
            >
              Retry Connection
            </button>
          </div>
        )}


        {/* Aggregate Stats Cards */}
        <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
          <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs">Active Workspaces</span>
              <FolderKanban className="size-4 text-primary" />
            </div>
            <p className="mt-2 font-display text-2xl font-bold text-foreground">{workspaces.length}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">Independent memories</p>
          </div>

          <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs">Documents Indexed</span>
              <FileText className="size-4 text-primary" />
            </div>
            <p className="mt-2 font-display text-2xl font-bold text-foreground">{totalDocs}</p>
            <p className="mt-1 text-[11px] text-muted-foreground">RAG knowledge vectors</p>
          </div>

          <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs">Learning Streak</span>
              <Flame className="size-4 text-warning" />
            </div>
            <p className="mt-2 font-display text-2xl font-bold text-foreground">
              {streakDays} {streakDays === 1 ? 'Day' : 'Days'}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              {streakDays > 0 ? `${streakDays} day active streak` : 'Start an activity to begin streak'}
            </p>
          </div>

          <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <div className="flex items-center justify-between text-muted-foreground">
              <span className="text-xs">Aggregate Mastery</span>
              <Target className="size-4 text-primary" />
            </div>
            <p className="mt-2 font-display text-2xl font-bold text-foreground">{avgMastery}%</p>
            <p className="mt-1 text-[11px] text-success">
              {avgMasteryDelta > 0
                ? `+${avgMasteryDelta}% across all subjects`
                : avgMasteryDelta < 0
                ? `${avgMasteryDelta}% across all subjects`
                : 'Baseline mastery established'}
            </p>
          </div>
        </div>

        {/* Continue Learning Banner */}
        {workspaces.length > 0 && (
          <section className="rounded-3xl border border-primary/25 bg-gradient-to-r from-card via-card to-primary/10 p-6 shadow-card">
            <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="flex size-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
                    <Sparkles className="size-3.5" />
                  </span>
                  <span className="text-xs font-bold uppercase tracking-wider text-primary">
                    Top Recommended Next Step
                  </span>
                </div>
                <h2 className="font-display text-lg font-semibold text-foreground">
                  {workspaces[0]?.name}
                  {topRecommendation ? `: ${topRecommendation.title}` : ''}
                </h2>
                <p className="text-xs text-muted-foreground max-w-2xl">
                  {topRecommendation
                    ? topRecommendation.rationale
                    : 'Ask the AI tutor about your sources or take an adaptive quiz to start building your mastery profile.'}
                </p>
              </div>

              <Link
                href={`/dashboard/workspace/${workspaces[0]?.id}`}
                className="inline-flex shrink-0 items-center justify-center gap-2 rounded-2xl bg-primary px-6 py-3 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
              >
                <span>Enter Workspace</span>
                <ArrowRight className="size-4" />
              </Link>
            </div>
          </section>
        )}

        {/* Workspaces Grid */}
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="font-display text-lg font-semibold text-foreground">Your Workspaces</h2>
              <p className="text-xs text-muted-foreground">
                Each workspace is an independent learning environment with isolated sources, tutor memory, and roadmaps.
              </p>
            </div>
          </div>

          <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {workspaces.map((ws) => (
              <Link
                key={ws.id}
                href={`/dashboard/workspace/${ws.id}`}
                className="group flex flex-col justify-between rounded-3xl border border-border bg-card p-5 shadow-soft transition-all duration-200 hover:-translate-y-1 hover:border-primary/50 hover:shadow-card"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <span className="flex size-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
                      <FolderKanban className="size-5" />
                    </span>
                    <Badge variant={ws.status === 'on_track' ? 'success' : ws.status === 'active' ? 'default' : 'warning'} size="sm">
                      {ws.status.replace('_', ' ')}
                    </Badge>
                  </div>

                  <h3 className="mt-4 font-display text-base font-semibold text-foreground group-hover:text-primary transition-colors">
                    {ws.name}
                  </h3>
                  <p className="mt-1 text-xs text-muted-foreground line-clamp-2">{ws.description}</p>
                </div>

                <div className="mt-5 space-y-3">
                  <div>
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="text-muted-foreground">Mastery</span>
                      <span className="font-semibold tabular-nums text-foreground">{ws.overallMastery}%</span>
                    </div>
                    <Progress value={ws.overallMastery} className="h-1.5" />
                  </div>

                  <div className="flex items-center justify-between border-t border-border/70 pt-3 text-[11px] text-muted-foreground">
                    <span>{ws.documentCount} sources</span>
                    <span className="font-semibold text-primary flex items-center gap-1 group-hover:translate-x-0.5 transition-transform">
                      Enter <ArrowRight className="size-3" />
                    </span>
                  </div>
                </div>
              </Link>
            ))}

            {/* Create Workspace Tile */}
            <button
              onClick={() => setCreateModalOpen(true)}
              className="flex min-h-[220px] flex-col items-center justify-center gap-3 rounded-3xl border border-dashed border-border bg-card/40 p-6 text-center transition-all hover:border-primary/60 hover:bg-accent/30"
            >
              <span className="flex size-12 items-center justify-center rounded-2xl border border-border bg-card text-primary shadow-soft">
                <Plus className="size-5" />
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">Create Workspace</p>
                <p className="mt-1 max-w-[180px] text-xs text-muted-foreground">
                  Upload learning materials to launch a new adaptive journey.
                </p>
              </div>
            </button>
          </div>
        </section>

        {/* Global Recent Activity */}
        <section className="rounded-3xl border border-border bg-card p-6 shadow-soft space-y-4">
          <div className="flex items-center justify-between border-b border-border pb-3">
            <div>
              <h3 className="font-display text-base font-semibold text-foreground">
                Recent Global Learning Events
              </h3>
              <p className="text-xs text-muted-foreground">Continuous audit across all your workspace sessions</p>
            </div>
          </div>

          <div className="space-y-3">
            {(activities || []).length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">No recent activities.</p>
            ) : (
              (activities || []).slice(0, 5).map((act) => (
                <div
                  key={act.id}
                  className="flex items-center justify-between gap-3 rounded-2xl border border-border bg-background/50 p-3.5 text-xs"
                >
                  <div className="flex items-center gap-3 truncate">
                    <span className="size-2 rounded-full bg-primary shrink-0" />
                    <div>
                      <span className="font-semibold text-foreground">{act.title}</span>
                      <p className="text-[11px] text-muted-foreground truncate">{act.description}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    {act.workspaceName && (
                      <Badge variant="neutral" size="sm">
                        {act.workspaceName}
                      </Badge>
                    )}
                    <span className="text-[11px] text-muted-foreground">{act.timestamp}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </main>

      {/* Modals */}
      <CreateWorkspaceModal
        isOpen={createModalOpen}
        onClose={() => setCreateModalOpen(false)}
      />

      <DeleteWorkspaceModal
        isOpen={deleteModalOpen}
        workspaces={workspaces}
        onClose={() => setDeleteModalOpen(false)}
        onDeleteWorkspace={handleDeleteWorkspace}
      />
    </div>
  )
}
