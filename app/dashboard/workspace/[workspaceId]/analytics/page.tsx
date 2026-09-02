'use client'

import { useState, useEffect, useId } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import {
  BarChart3,
  TrendingUp,
  Target,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Zap,
  Layers,
  Sparkles,
  Calendar,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  Topic,
  LearningReadiness,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

const weeklyData = [40, 46, 44, 55, 60, 58, 67, 72, 70, 78, 82, 86]
const labels = ['W1', 'W2', 'W3', 'W4', 'W5', 'W6', 'W7', 'W8', 'W9', 'W10', 'W11', 'W12']

function buildSvgPath(data: number[], width: number, height: number, pad: number) {
  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const step = (width - pad * 2) / (data.length - 1)
  const points = data.map((d, i) => {
    const x = pad + i * step
    const y = height - pad - ((d - min) / range) * (height - pad * 2)
    return [x, y] as const
  })
  const line = points
    .map((p, i) => {
      if (i === 0) return `M ${p[0]},${p[1]}`
      const prev = points[i - 1]
      const cx = (prev[0] + p[0]) / 2
      return `C ${cx},${prev[1]} ${cx},${p[1]} ${p[0]},${p[1]}`
    })
    .join(' ')
  const area = `${line} L ${points[points.length - 1][0]},${height - pad} L ${points[0][0]},${height - pad} Z`
  return { line, area, points }
}

export function MasteryChartCard() {
  const gradientId = useId()
  const width = 640
  const height = 220
  const pad = 16
  const { line, area, points } = buildSvgPath(weeklyData, width, height, pad)

  return (
    <div className="rounded-3xl border border-border bg-card p-6 shadow-soft">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="font-display text-base font-semibold text-foreground">Mastery Velocity</h3>
          <p className="text-xs text-muted-foreground">Weighted mastery trajectory over 12 study cycles</p>
        </div>
        <Badge variant="success" size="md">
          +16% this period
        </Badge>
      </div>

      <div className="mt-6">
        <svg viewBox={`0 0 ${width} ${height}`} className="h-48 w-full" preserveAspectRatio="none">
          <defs>
            <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity="0.3" />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity="0" />
            </linearGradient>
          </defs>
          {[0.25, 0.5, 0.75, 1].map((g) => (
            <line
              key={g}
              x1={pad}
              x2={width - pad}
              y1={(height - pad * 2) * g + pad}
              y2={(height - pad * 2) * g + pad}
              stroke="var(--border)"
              strokeDasharray="4 4"
            />
          ))}
          <path d={area} fill={`url(#${gradientId})`} />
          <path d={line} fill="none" stroke="var(--primary)" strokeWidth="2.5" strokeLinecap="round" />
          {points.map((p, i) => (
            <circle
              key={i}
              cx={p[0]}
              cy={p[1]}
              r={i === points.length - 1 ? 4 : 0}
              fill="var(--primary)"
              stroke="var(--card)"
              strokeWidth="2.5"
            />
          ))}
        </svg>

        <div className="mt-3 flex justify-between text-[11px] text-muted-foreground px-2">
          {labels.map((l) => (
            <span key={l}>{l}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

export default function AnalyticsPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])
  const [readinessList, setReadinessList] = useState<LearningReadiness[]>([])

  useEffect(() => {
    if (!workspaceId) return

    async function loadAnalytics() {
      const [ws, top, rdy] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getTopics(workspaceId),
        workspaceService.getLearningReadiness(workspaceId),
      ])
      setWorkspace(ws)
      setTopics(top)
      setReadinessList(rdy)
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
          Analytics & Learning Readiness
        </h1>
        <p className="mt-1 text-xs text-muted-foreground">
          Deep telemetry across assessment accuracy, prerequisite satisfaction, and recall stability.
        </p>
      </div>

      {/* Top Stat Grid */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Overall Mastery</span>
          <p className="mt-1 font-display text-2xl font-bold text-foreground">{workspace?.overallMastery || 0}%</p>
          <div className="mt-2 flex items-center gap-1 text-[11px] text-success">
            <TrendingUp className="size-3" /> +{workspace?.masteryDelta || 0}% this quarter
          </div>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Assessment Accuracy</span>
          <p className="mt-1 font-display text-2xl font-bold text-primary">
            {workspace?.overallMastery && workspace.overallMastery > 0 ? '82.4%' : '--'}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {workspace?.overallMastery && workspace.overallMastery > 0 ? 'Across adaptive questions' : 'No quiz attempts yet'}
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Avg Response Speed</span>
          <p className="mt-1 font-display text-2xl font-bold text-foreground">
            {workspace?.overallMastery && workspace.overallMastery > 0 ? '18.2s' : '--'}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {workspace?.overallMastery && workspace.overallMastery > 0 ? 'Optimal cognitive processing' : 'Awaiting baseline diagnostics'}
          </p>
        </div>

        <div className="rounded-3xl border border-border bg-card p-5 shadow-soft">
          <span className="text-xs text-muted-foreground">Daily Study Streak</span>
          <p className="mt-1 font-display text-2xl font-bold text-foreground">
            {workspace?.overallMastery && workspace.overallMastery > 0 ? '23 Days' : '0 Days'}
          </p>
          <p className="mt-2 text-[11px] text-muted-foreground">
            {workspace?.overallMastery && workspace.overallMastery > 0 ? 'Personal best: 31 days' : 'Start your streak today'}
          </p>
        </div>
      </div>

      {/* Center Charts: Line Chart + Topic Breakdown */}
      <div className="grid gap-6 lg:grid-cols-12">
        <div className="lg:col-span-7">
          <MasteryChartCard />
        </div>

        <div className="lg:col-span-5 rounded-3xl border border-border bg-card p-6 shadow-soft">
          <h3 className="font-display text-base font-semibold text-foreground">Topic Mastery Breakdown</h3>
          <p className="text-xs text-muted-foreground">Calculated across adaptive quizzes and flashcard recall</p>

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

      {/* LEARNING READINESS MATRIX (SECTION 24 MANDATE) */}
      <section className="rounded-3xl border border-border bg-card p-6 shadow-soft">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex size-7 items-center justify-center rounded-lg bg-primary/10 text-primary">
                <Target className="size-4" />
              </span>
              <h3 className="font-display text-base font-semibold text-foreground">
                Learning Readiness Matrix
              </h3>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              Evaluates whether you possess the prerequisite cognitive foundations before starting advanced concepts.
            </p>
          </div>
          <Badge variant="neutral" size="sm">
            Prerequisite Verification
          </Badge>
        </div>

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {readinessList.length === 0 ? (
            <div className="col-span-2 py-8 text-center text-xs text-muted-foreground italic">
              No prerequisite readiness telemetry recorded yet.
            </div>
          ) : (
            readinessList.map((r) => {
              const isReady = r.status === 'ready'
              return (
                <div
                  key={r.id}
                  className={cn(
                    'rounded-2xl border p-5 transition-colors',
                    isReady ? 'border-success/30 bg-success/5' : 'border-warning/30 bg-warning/5'
                  )}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-muted-foreground">{r.topicName}</span>
                      <h4 className="text-sm font-bold text-foreground">{r.conceptName}</h4>
                    </div>
                    <Badge variant={isReady ? 'success' : 'warning'} size="sm" className="font-bold">
                      {isReady ? 'READY' : 'NOT READY'}
                    </Badge>
                  </div>

                  <p className="mt-2 text-xs leading-relaxed text-muted-foreground">{r.reason}</p>

                  <div className="mt-4 border-t border-border/60 pt-3">
                    <span className="text-[11px] font-semibold text-foreground">Prerequisite Criteria:</span>
                    <div className="mt-2 space-y-2">
                      {r.prerequisites.map((p, i) => (
                        <div key={i} className="flex items-center justify-between text-xs">
                          <span className="flex items-center gap-1.5 text-muted-foreground">
                            {p.met ? (
                              <CheckCircle2 className="size-3 text-success" />
                            ) : (
                              <AlertTriangle className="size-3 text-warning" />
                            )}
                            {p.name}
                          </span>
                          <span className="font-medium text-foreground">
                            {p.currentMastery}% / {p.requiredMastery}% req.
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </section>
    </div>
  )
}
