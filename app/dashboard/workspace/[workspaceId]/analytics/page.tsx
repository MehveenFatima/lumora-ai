'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import { TrendingUp, Target, Clock, CheckCircle2, Layers } from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import { tutorApiClient } from '@/lib/api/tutor-api-client'
import { Workspace, Topic } from '@/lib/types/domain'
import { Progress } from '@/components/ui/progress'
import { computeStudyStreak } from '@/lib/learning-stats'
import { MasteryTrendChart, type MasteryPoint } from '@/components/workspace/mastery-trend-chart'

interface RecentPerformance {
  quizzesCompleted: number
  totalAttempts: number
  accuracyPercentage: number
  averageResponseTimeSeconds: number
  assessedConcepts: number
  totalConcepts: number
}

function toRecentPerformance(profile: any): RecentPerformance {
  const recent = profile?.recent_performance || {}
  const overall = profile?.overall || {}
  return {
    quizzesCompleted: Number(recent.quizzes_completed) || 0,
    totalAttempts: Number(recent.total_attempts) || 0,
    accuracyPercentage: Number(recent.accuracy_percentage) || 0,
    averageResponseTimeSeconds: Number(recent.average_response_time_seconds) || 0,
    assessedConcepts: Number(overall.assessed_concepts_count) || 0,
    totalConcepts: Number(overall.total_concepts_count) || 0,
  }
}

function RecentPerformanceCard({ perf }: { perf: RecentPerformance | null }) {
  const hasAttempts = !!perf && perf.totalAttempts > 0
  const coverage =
    perf && perf.totalConcepts > 0 ? Math.round((perf.assessedConcepts / perf.totalConcepts) * 100) : 0

  const rows = [
    { icon: CheckCircle2, label: 'Quiz sessions completed', value: perf ? String(perf.quizzesCompleted) : '--' },
    { icon: Layers, label: 'Questions answered', value: perf ? String(perf.totalAttempts) : '--' },
    {
      icon: Target,
      label: 'Concepts assessed',
      value: perf && perf.totalConcepts > 0 ? `${perf.assessedConcepts} of ${perf.totalConcepts}` : '--',
    },
  ]

  return (
    <div className="rounded-3xl border border-border bg-card p-6 shadow-soft">
      <h3 className="font-display text-base font-semibold text-foreground">Recent Performance</h3>
      <p className="text-xs text-muted-foreground">Computed from your recorded adaptive quiz attempts</p>

      {!hasAttempts ? (
        <p className="py-12 text-center text-xs italic text-muted-foreground">
          No quiz attempts recorded yet. Take an adaptive quiz to start building your learner profile.
        </p>
      ) : (
        <div className="mt-6 space-y-6">
          <div>
            <div className="mb-1.5 flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground">Answer accuracy</span>
              <span className="font-bold tabular-nums text-foreground">{Math.round(perf!.accuracyPercentage)}%</span>
            </div>
            <Progress value={perf!.accuracyPercentage} className="h-2" />
          </div>
          <div>
            <div className="mb-1.5 flex items-center justify-between text-xs">
              <span className="font-semibold text-foreground">Concept coverage</span>
              <span className="font-bold tabular-nums text-foreground">{coverage}%</span>
            </div>
            <Progress value={coverage} className="h-2" />
          </div>
          <dl className="grid gap-3 sm:grid-cols-3">
            {rows.map((r) => (
              <div key={r.label} className="rounded-2xl border border-border/70 bg-background/40 p-4">
                <dt className="flex items-center gap-1.5 text-[11px] text-muted-foreground">
                  <r.icon className="size-3.5" />
                  {r.label}
                </dt>
                <dd className="mt-1 font-display text-lg font-semibold tabular-nums text-foreground">{r.value}</dd>
              </div>
            ))}
          </dl>
        </div>
      )}
    </div>
  )
}

export default function AnalyticsPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])
  const [perf, setPerf] = useState<RecentPerformance | null>(null)
  const [streakDays, setStreakDays] = useState(0)
  const [history, setHistory] = useState<MasteryPoint[] | null>(null)

  useEffect(() => {
    if (!workspaceId) return

    async function loadAnalytics() {
      const [ws, top, profile, acts, hist] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getTopics(workspaceId),
        tutorApiClient.getLearnerProfile(workspaceId).catch(() => null),
        workspaceService.getActivities(workspaceId).catch(() => []),
        tutorApiClient.getMasteryHistory(workspaceId, 30).catch(() => ({ points: [] })),
      ])
      setHistory(hist.points || [])
      setWorkspace(ws)
      setTopics(top)
      setPerf(profile ? toRecentPerformance(profile) : null)
      setStreakDays(computeStudyStreak(acts))
    }
    loadAnalytics()
  }, [workspaceId])

  return (
    <div className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6 md:py-8 space-y-6">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-primary">
            Learning Diagnostics
          </span>
          <span className="text-muted-foreground">•</span>
          <span className="text-xs text-muted-foreground">{workspace?.name}</span>
        </div>
        <h1 className="mt-1 font-display text-2xl font-semibold text-foreground md:text-3xl">
          Learning Analytics
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Mastery, accuracy and activity for this workspace, computed from your quiz attempts and study events.
        </p>
      </div>

      {/* Top Stat Grid */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Overall Mastery</span>
          <p className="mt-1 font-display text-2xl font-bold text-foreground">{workspace?.overallMastery || 0}%</p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
            <TrendingUp className="size-3" /> {(workspace?.masteryDelta || 0) >= 0 ? '+' : ''}
            {workspace?.masteryDelta || 0}% since last update
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Assessment Accuracy</span>
          <p className="mt-1 font-display text-2xl font-bold text-primary">
            {perf && perf.totalAttempts > 0 ? `${Math.round(perf.accuracyPercentage)}%` : '--'}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {perf && perf.totalAttempts > 0
              ? `Across ${perf.totalAttempts} answered question${perf.totalAttempts === 1 ? '' : 's'}`
              : 'No quiz attempts yet'}
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Avg Response Time</span>
          <p className="mt-1 font-display text-2xl font-bold text-foreground">
            {perf && perf.averageResponseTimeSeconds > 0 ? `${perf.averageResponseTimeSeconds.toFixed(1)}s` : '--'}
          </p>
          <p className="mt-2 flex items-center gap-1 text-[11px] text-muted-foreground">
            <Clock className="size-3" /> Per quiz question
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Study Streak</span>
          <p className="mt-1 font-display text-2xl font-bold text-foreground">
            {streakDays} {streakDays === 1 ? 'Day' : 'Days'}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {streakDays > 0 ? 'Consecutive days with recorded activity' : 'Start your streak today'}
          </p>
        </div>
      </div>

      <section className="rounded-3xl border border-border bg-card p-6 shadow-soft">
        <h3 className="font-display text-base font-semibold text-foreground">Mastery over time</h3>
        <p className="text-xs text-muted-foreground">
          Daily workspace mastery for the last 30 days, from Bayesian Knowledge Tracing snapshots
        </p>
        <div className="mt-4">{history === null ? null : <MasteryTrendChart points={history} />}</div>
      </section>

      {/* Center Charts: Recent Performance + Topic Breakdown */}
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <RecentPerformanceCard perf={perf} />
        </div>

        <div className="lg:col-span-5 rounded-3xl border border-border bg-card p-6 shadow-soft">
          <h3 className="font-display text-base font-semibold text-foreground">Topic Mastery Breakdown</h3>
          <p className="text-xs text-muted-foreground">Bayesian Knowledge Tracing estimates from adaptive quiz answers</p>

          <div className="mt-5 space-y-4">
            {topics.length === 0 ? (
              <p className="py-8 text-center text-xs text-muted-foreground italic">No topic mastery data available yet.</p>
            ) : (
              topics.map((t) => (
                <div key={t.id}>
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="font-semibold text-foreground">{t.name}</span>
                    <span className="font-bold tabular-nums text-foreground">{t.mastery}%</span>
                  </div>
                  <Progress value={t.mastery} className="h-2" />
                </div>
              ))
            )}
          </div>
        </div>
      </div>

    </div>
  )
}
