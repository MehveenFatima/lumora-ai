'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import {
  Sparkles,
  ArrowRight,
  HelpCircle,
  MessagesSquare,
  Zap,
  Layers,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Target,
  FileText,
  ChevronRight,
  TrendingUp,
  TrendingDown,
  Map,
  CalendarCheck,
  Check,
  Flame,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  Topic,
  KnowledgeGap,
  AIRecommendation,
  Roadmap,
  StudyPlan,
  LearningActivity,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { RoadmapDetailModal } from '@/components/workspace/roadmap-detail-modal'
import { cn } from '@/lib/utils'

export default function WorkspaceLandingPage() {
  const params = useParams()
  const workspaceId = (params?.workspaceId as string) || 'dsa'

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])
  const [knowledgeGaps, setKnowledgeGaps] = useState<KnowledgeGap[]>([])
  const [recommendation, setRecommendation] = useState<AIRecommendation | null>(null)
  const [roadmap, setRoadmap] = useState<Roadmap | null>(null)
  const [studyPlan, setStudyPlan] = useState<StudyPlan | null>(null)
  const [activities, setActivities] = useState<LearningActivity[]>([])
  const [loading, setLoading] = useState(true)

  // Modals & Accordions
  const [showRationale, setShowRationale] = useState(false)
  const [roadmapModalOpen, setRoadmapModalOpen] = useState(false)

  useEffect(() => {
    async function loadWorkspaceData() {
      setLoading(true)
      try {
        const [ws, top, gaps, rec, rd, sp, act] = await Promise.all([
          workspaceService.getWorkspaceById(workspaceId),
          workspaceService.getTopics(workspaceId),
          workspaceService.getKnowledgeGaps(workspaceId),
          workspaceService.getRecommendation(workspaceId),
          workspaceService.getRoadmap(workspaceId),
          workspaceService.getStudyPlan(workspaceId),
          workspaceService.getActivities(workspaceId),
        ])

        setWorkspace(ws)
        setTopics(top)
        setKnowledgeGaps(gaps)
        setRecommendation(rec)
        setRoadmap(rd)
        setStudyPlan(sp)
        setActivities(act)
      } catch (err) {
        console.error('Failed to load workspace command center:', err)
      } finally {
        setLoading(false)
      }
    }

    loadWorkspaceData()
  }, [workspaceId])

  if (loading) {
    return (
      <div className="flex h-full w-full items-center justify-center p-8">
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="size-10 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          <p className="text-xs text-muted-foreground font-medium">Loading workspace command center...</p>
        </div>
      </div>
    )
  }

  if (!workspace) {
    return (
      <div className="p-8 text-center">
        <p className="text-sm text-muted-foreground">Workspace not found.</p>
        <Link href="/dashboard" className="mt-4 inline-block text-xs font-semibold text-primary hover:underline">
          Return to Dashboard
        </Link>
      </div>
    )
  }

  const strongTopics = topics.filter((t) => t.status === 'strong')
  const developingTopics = topics.filter((t) => t.status === 'developing')
  const needsReviewTopics = topics.filter((t) => t.status === 'needs_review')
  const criticalGapTopics = topics.filter((t) => t.status === 'critical_gap')

  return (
    <div className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6 md:py-8 space-y-6">
      {/* 1. Workspace Identity & High-Level Telemetry */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              Workspace Command Center
            </span>
            <span className="text-muted-foreground">•</span>
            <span className="text-xs text-muted-foreground">{workspace.goal}</span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-foreground md:text-3xl">
            {workspace.name}
          </h1>
          <p className="mt-1 text-xs text-muted-foreground max-w-2xl">
            {workspace.description}
          </p>
        </div>

        {/* Quick Context Stats */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2.5 rounded-2xl border border-border bg-card px-3.5 py-2 shadow-soft">
            <Target className="size-4 text-primary" />
            <div>
              <div className="text-[10px] text-muted-foreground">Mastery</div>
              <div className="text-xs font-bold text-foreground">{workspace.overallMastery}%</div>
            </div>
            <Badge variant="success" size="sm" className="ml-1 text-[10px]">
              +{workspace.masteryDelta}%
            </Badge>
          </div>

          <Link
            href={`/dashboard/workspace/${workspace.id}/sources`}
            className="flex items-center gap-2.5 rounded-2xl border border-border bg-card px-3.5 py-2 shadow-soft transition-colors hover:border-primary/40 hover:bg-accent/40"
          >
            <FileText className="size-4 text-primary" />
            <div>
              <div className="text-[10px] text-muted-foreground">Sources</div>
              <div className="text-xs font-bold text-foreground">{workspace.documentCount} Docs</div>
            </div>
          </Link>

          <Link
            href={`/dashboard/workspace/${workspace.id}/flashcards`}
            className="flex items-center gap-2.5 rounded-2xl border border-border bg-card px-3.5 py-2 shadow-soft transition-colors hover:border-primary/40 hover:bg-accent/40"
          >
            <Layers className="size-4 text-warning" />
            <div>
              <div className="text-[10px] text-muted-foreground">Due Cards</div>
              <div className="text-xs font-bold text-foreground">{workspace.flashcardsDueCount} Ready</div>
            </div>
          </Link>
        </div>
      </div>

      {/* PRIORITY 1: "What should I do next?" → AI RECOMMENDATION */}
      {recommendation && (
        <section className="overflow-hidden rounded-3xl border border-primary/30 bg-gradient-to-br from-card via-card to-primary/5 p-5 shadow-card md:p-7">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/70 pb-4">
            <div className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-glow">
                <Sparkles className="size-4" />
              </span>
              <span className="text-xs font-bold uppercase tracking-wider text-primary">
                AI Recommendation — Next Best Action
              </span>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="destructive" size="sm" className="text-[10px] font-semibold uppercase">
                {recommendation.priority} Priority
              </Badge>
              <span className="flex items-center gap-1 text-xs text-muted-foreground">
                <Clock className="size-3.5" />
                {recommendation.estimatedMinutes} mins
              </span>
            </div>
          </div>

          <div className="mt-4 grid gap-6 lg:grid-cols-3">
            <div className="lg:col-span-2 space-y-2">
              <h2 className="font-display text-lg font-semibold text-foreground md:text-xl">
                {recommendation.title}
              </h2>
              <p className="text-xs leading-relaxed text-muted-foreground md:text-sm">
                &ldquo;{recommendation.rationale}&rdquo;
              </p>

              {/* Rationale toggle panel */}
              <div className="pt-2">
                <button
                  onClick={() => setShowRationale(!showRationale)}
                  className="inline-flex items-center gap-1.5 text-xs font-medium text-primary transition-opacity hover:opacity-80"
                >
                  <HelpCircle className="size-3.5" />
                  <span>{showRationale ? 'Hide diagnostic rationale' : 'Why am I seeing this?'}</span>
                </button>

                {showRationale && (
                  <div className="mt-2 rounded-2xl border border-border bg-background/80 p-3.5 text-xs animate-in fade-in duration-150">
                    <p className="font-semibold text-foreground">Diagnostic Criteria & Signals:</p>
                    <ul className="mt-1.5 space-y-1 text-muted-foreground list-disc pl-4 text-[11px]">
                      {recommendation.dataPoints.map((dp, i) => (
                        <li key={i}>{dp}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Direct Action Triggers */}
            <div className="flex flex-col justify-center gap-2.5 rounded-2xl border border-border/80 bg-background/50 p-4">
              <Link
                href={`/dashboard/workspace/${workspace.id}/tutor`}
                className="flex items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
              >
                <MessagesSquare className="size-4" />
                <span>Ask AI Tutor Grounded in Notes</span>
              </Link>
              <Link
                href={`/dashboard/workspace/${workspace.id}/quiz`}
                className="flex items-center justify-center gap-2 rounded-xl border border-border bg-card py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-accent/50"
              >
                <Zap className="size-4 text-warning" />
                <span>Take Adaptive Diagnostic Quiz</span>
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Main Command Center Grid: 2 Columns */}
      <div className="grid gap-6 lg:grid-cols-12">
        {/* Left Column: Knowledge Profile, Knowledge Gaps, Adaptive Roadmap */}
        <div className="space-y-6 lg:col-span-8">
          {/* PRIORITY 2: "How am I doing?" → KNOWLEDGE PROFILE */}
          <section className="rounded-3xl border border-border bg-card p-5 shadow-soft md:p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-display text-base font-semibold text-foreground">
                  Your Knowledge Profile
                </h3>
                <p className="text-xs text-muted-foreground">
                  Curriculum topic mastery and cognitive readiness
                </p>
              </div>
              <Link
                href={`/dashboard/workspace/${workspace.id}/topics`}
                className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                View all topics <ChevronRight className="size-3.5" />
              </Link>
            </div>

            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              {/* Strong */}
              <div className="rounded-2xl border border-border bg-background/50 p-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-success flex items-center gap-1.5">
                    <CheckCircle2 className="size-3.5" /> Strong
                  </span>
                  <span className="text-[11px] text-muted-foreground">{strongTopics.length} Topics</span>
                </div>
                <div className="mt-3 flex flex-col gap-2">
                  {strongTopics.map((t) => (
                    <div key={t.id} className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground truncate max-w-[140px]">{t.name}</span>
                      <div className="flex items-center gap-1.5">
                        <TrendingUp className="size-3 text-success" />
                        <span className="font-semibold tabular-nums text-foreground">{t.mastery}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Developing */}
              <div className="rounded-2xl border border-border bg-background/50 p-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-chart-2 flex items-center gap-1.5">
                    <Target className="size-3.5" /> Developing
                  </span>
                  <span className="text-[11px] text-muted-foreground">{developingTopics.length} Topics</span>
                </div>
                <div className="mt-3 flex flex-col gap-2">
                  {developingTopics.map((t) => (
                    <div key={t.id} className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground truncate max-w-[140px]">{t.name}</span>
                      <span className="font-semibold tabular-nums text-foreground">{t.mastery}%</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Needs Review */}
              <div className="rounded-2xl border border-border bg-background/50 p-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-warning flex items-center gap-1.5">
                    <AlertTriangle className="size-3.5" /> Needs Review
                  </span>
                  <span className="text-[11px] text-muted-foreground">{needsReviewTopics.length} Topics</span>
                </div>
                <div className="mt-3 flex flex-col gap-2">
                  {needsReviewTopics.map((t) => (
                    <div key={t.id} className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground truncate max-w-[140px]">{t.name}</span>
                      <div className="flex items-center gap-1.5">
                        <TrendingDown className="size-3 text-warning" />
                        <span className="font-semibold tabular-nums text-foreground">{t.mastery}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Critical Gap */}
              <div className="rounded-2xl border border-destructive/20 bg-destructive/5 p-4">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-semibold text-destructive flex items-center gap-1.5">
                    <AlertTriangle className="size-3.5" /> Critical Gap
                  </span>
                  <span className="text-[11px] text-muted-foreground">{criticalGapTopics.length} Topics</span>
                </div>
                <div className="mt-3 flex flex-col gap-2">
                  {criticalGapTopics.map((t) => (
                    <div key={t.id} className="flex items-center justify-between text-xs">
                      <span className="font-medium text-foreground truncate max-w-[140px]">{t.name}</span>
                      <span className="font-semibold tabular-nums text-destructive">{t.mastery}%</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>

          {/* PRIORITY 3: "What do I need to improve?" → KNOWLEDGE GAPS */}
          <section className="rounded-3xl border border-border bg-card p-5 shadow-soft md:p-6">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="font-display text-base font-semibold text-foreground">
                  Identified Knowledge Gaps
                </h3>
                <p className="text-xs text-muted-foreground">
                  Concepts diagnosed below passing threshold
                </p>
              </div>
              <Badge variant="warning" size="sm">
                {knowledgeGaps.length} Actionable Gaps
              </Badge>
            </div>

            <div className="mt-4 flex flex-col gap-3">
              {knowledgeGaps.slice(0, 3).map((gap) => (
                <div
                  key={gap.id}
                  className="rounded-2xl border border-border bg-background/50 p-4 transition-colors hover:border-primary/40"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="size-2 rounded-full bg-destructive" />
                      <h4 className="text-xs font-bold text-foreground">{gap.conceptName}</h4>
                      <Badge variant="neutral" size="sm" className="text-[10px]">
                        {gap.topicName}
                      </Badge>
                    </div>
                    <span className="text-xs font-semibold tabular-nums text-destructive">
                      {gap.mastery}% Mastery
                    </span>
                  </div>

                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">
                    {gap.reason}
                  </p>

                  <div className="mt-3.5 flex flex-wrap items-center gap-2 border-t border-border/70 pt-3">
                    <Link
                      href={`/dashboard/workspace/${workspace.id}/tutor`}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent/40"
                    >
                      <MessagesSquare className="size-3.5 text-primary" /> Ask Tutor
                    </Link>
                    <Link
                      href={`/dashboard/workspace/${workspace.id}/quiz`}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent/40"
                    >
                      <Zap className="size-3.5 text-warning" /> Take Quiz
                    </Link>
                    <Link
                      href={`/dashboard/workspace/${workspace.id}/flashcards`}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-card px-2.5 py-1 text-xs font-medium text-foreground transition-colors hover:bg-accent/40"
                    >
                      <Layers className="size-3.5 text-primary" /> Review Cards
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          </section>

          {/* PRIORITY 4: "Where am I going?" → ADAPTIVE ROADMAP */}
          {roadmap && (
            <section className="rounded-3xl border border-border bg-card p-5 shadow-soft md:p-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="flex size-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Map className="size-4" />
                  </span>
                  <div>
                    <h3 className="font-display text-base font-semibold text-foreground">
                      Adaptive Learning Roadmap
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Self-adjusting milestone sequence based on continuous diagnostics
                    </p>
                  </div>
                </div>

                <button
                  onClick={() => setRoadmapModalOpen(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl border border-border bg-background px-3 py-1.5 text-xs font-semibold text-primary transition-colors hover:bg-accent/40"
                >
                  View Full Roadmap <ArrowRight className="size-3.5" />
                </button>
              </div>

              {/* Dynamic Adaptation Callout */}
              {roadmap.adaptation?.hasAdaptation && (
                <div className="mt-4 rounded-2xl border border-primary/20 bg-primary/5 p-3.5 text-xs">
                  <div className="flex items-center gap-1.5 font-semibold text-primary">
                    <Sparkles className="size-3.5" />
                    <span>{roadmap.adaptation.title}</span>
                  </div>
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    {roadmap.adaptation.triggerReason}
                  </p>
                </div>
              )}

              {/* Compact Visual Path Preview */}
              <div className="mt-5 space-y-3">
                {roadmap.stages.slice(0, 2).map((stage) => (
                  <div key={stage.id} className="rounded-2xl border border-border/80 bg-background/50 p-4">
                    <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                      <span>{stage.name}</span>
                      <span className="text-[11px] font-normal text-muted-foreground">{stage.description}</span>
                    </div>

                    <div className="mt-3 flex flex-col gap-2">
                      {stage.nodes.slice(0, 3).map((node) => (
                        <div
                          key={node.id}
                          className="flex items-center justify-between rounded-xl border border-border/60 bg-card p-2.5 text-xs"
                        >
                          <div className="flex items-center gap-2.5 truncate">
                            {node.status === 'completed' ? (
                              <CheckCircle2 className="size-4 text-success shrink-0" />
                            ) : node.status === 'in_progress' ? (
                              <span className="size-2 rounded-full bg-primary animate-pulse shrink-0" />
                            ) : (
                              <span className="size-2 rounded-full bg-muted-foreground/40 shrink-0" />
                            )}
                            <span className="truncate font-medium text-foreground">{node.title}</span>
                          </div>
                          <span className="text-[11px] font-semibold tabular-nums text-foreground shrink-0">
                            {node.mastery}%
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* Right Column: Today's Plan & Recent Activity */}
        <div className="space-y-6 lg:col-span-4">
          {/* PRIORITY 5: "What should I do today?" → TODAY'S PLAN */}
          {studyPlan && (
            <section className="rounded-3xl border border-border bg-card p-5 shadow-soft">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-display text-base font-semibold text-foreground">Today&apos;s Plan</h3>
                  <p className="text-xs text-muted-foreground">
                    Target: {studyPlan.dailyTargetMinutes} mins
                  </p>
                </div>
                <Badge variant="default" size="sm">
                  {studyPlan.todayCompletedMinutes} / {studyPlan.dailyTargetMinutes} min
                </Badge>
              </div>

              <div className="mt-3">
                <Progress
                  value={(studyPlan.todayCompletedMinutes / studyPlan.dailyTargetMinutes) * 100}
                  className="h-2"
                />
              </div>

              <div className="mt-4 flex flex-col gap-2.5">
                {studyPlan.tasks.slice(0, 4).map((task) => (
                  <div
                    key={task.id}
                    className={cn(
                      'flex items-start gap-2.5 rounded-2xl border p-3 text-xs transition-colors',
                      task.completed ? 'border-border/60 bg-background/30 opacity-70' : 'border-border bg-background'
                    )}
                  >
                    <button
                      onClick={async () => {
                        await workspaceService.toggleStudyTask(workspace.id, task.id)
                        const updated = await workspaceService.getStudyPlan(workspace.id)
                        setStudyPlan(updated)
                      }}
                      className="mt-0.5"
                    >
                      {task.completed ? (
                        <CheckCircle2 className="size-4 text-success" />
                      ) : (
                        <div className="size-4 rounded-md border border-border bg-card" />
                      )}
                    </button>
                    <div className="min-w-0 flex-1">
                      <p className={cn('font-medium text-foreground', task.completed && 'line-through text-muted-foreground')}>
                        {task.title}
                      </p>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-muted-foreground">
                        <span>{task.estimatedMinutes} mins</span>
                        <span>•</span>
                        <span className="capitalize">{task.type}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4">
                <Link
                  href={`/dashboard/workspace/${workspace.id}/study-plan`}
                  className="flex w-full items-center justify-center gap-1.5 rounded-xl border border-border bg-background py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
                >
                  <span>Open Full Study Schedule</span>
                  <ChevronRight className="size-3.5" />
                </Link>
              </div>
            </section>
          )}

          {/* PRIORITY 6: "What have I done?" → RECENT ACTIVITY */}
          <section className="rounded-3xl border border-border bg-card p-5 shadow-soft">
            <div className="flex items-center justify-between border-b border-border pb-3">
              <h3 className="font-display text-sm font-semibold text-foreground">Recent Activity</h3>
              <Link
                href={`/dashboard/workspace/${workspace.id}/activity`}
                className="text-[11px] font-medium text-primary hover:underline"
              >
                All activity
              </Link>
            </div>

            <div className="mt-4 space-y-4">
              {activities.slice(0, 4).map((act) => (
                <div key={act.id} className="relative flex gap-3 text-xs">
                  <span className="mt-1 size-2 shrink-0 rounded-full bg-primary" />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-foreground truncate">{act.title}</p>
                    <p className="mt-0.5 text-[11px] text-muted-foreground line-clamp-2">{act.description}</p>
                    <span className="mt-1 block text-[10px] text-muted-foreground/70">{act.timestamp}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>

      {/* Full Roadmap Detail Modal */}
      {roadmap && (
        <RoadmapDetailModal
          isOpen={roadmapModalOpen}
          onClose={() => setRoadmapModalOpen(false)}
          roadmap={roadmap}
          workspaceName={workspace.name}
        />
      )}
    </div>
  )
}
