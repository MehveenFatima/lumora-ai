'use client'

import { useState, useEffect } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  BookOpen,
  Search,
  CheckCircle2,
  AlertTriangle,
  Target,
  TrendingUp,
  TrendingDown,
  Calendar,
  Clock,
  MessagesSquare,
  Zap,
  Layers,
  ChevronRight,
  X,
  Sparkles,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  Topic,
  Concept,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

export default function TopicsPage() {
  const params = useParams()
  const workspaceId = params?.workspaceId as string
  const wantedTopic = (useSearchParams().get('topic') || '').toLowerCase()

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [topics, setTopics] = useState<Topic[]>([])
  const [selectedTopic, setSelectedTopic] = useState<Topic | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')

  useEffect(() => {
    if (!workspaceId) return

    async function loadTopics() {
      const [ws, top] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getTopics(workspaceId),
      ])
      setWorkspace(ws)
      setTopics(top)
      if (top.length > 0) {
        // Opened from search: preselect the topic named in ?topic=
        const wanted = wantedTopic
        const match = wanted
          ? top.find(
              (t) =>
                t.name.toLowerCase() === wanted ||
                t.concepts?.some((c) => c.name.toLowerCase() === wanted),
            )
          : undefined
        setSelectedTopic(match || top[0])
      }
    }
    loadTopics()
  }, [workspaceId, wantedTopic])

  const filteredTopics = topics.filter((t) => {
    const matchesSearch = t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      t.description.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesStatus = statusFilter === 'all' || t.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <div className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6 md:py-8">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              Curriculum Mastery
            </span>
            <span className="text-muted-foreground">•</span>
            <span className="text-xs text-muted-foreground">{workspace?.name}</span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-foreground md:text-3xl">
            Topics & Concepts
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Track concept-level mastery scores, retention trends, and prerequisite dependencies.
          </p>
        </div>

        {/* Filter / Search Bar */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 size-3.5 text-muted-foreground" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search topics..."
              className="h-9 w-48 rounded-xl border border-input bg-card pl-8 pr-3 text-xs text-foreground placeholder:text-muted-foreground/60 outline-none focus:border-ring focus:ring-2 focus:ring-ring/20"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="h-9 rounded-xl border border-input bg-card px-3 text-xs text-foreground outline-none"
          >
            <option value="all">All Statuses</option>
            <option value="strong">Strong (&gt; 80%)</option>
            <option value="developing">Developing (60-80%)</option>
            <option value="needs_review">Needs Review (&lt; 60%)</option>
            <option value="critical_gap">Critical Gap (&lt; 40%)</option>
          </select>
        </div>
      </div>

      {/* Main 2-Column Layout: Topic Cards & Selected Topic Detail Drawer */}
      {topics.length === 0 ? (
        <div className="mt-8 rounded-3xl border border-dashed border-border bg-card/40 p-12 text-center">
          <BookOpen className="mx-auto size-10 text-muted-foreground/60" />
          <h3 className="mt-3 font-display text-base font-semibold text-foreground">No Topics Indexed Yet</h3>
          <p className="mt-1 text-xs text-muted-foreground max-w-md mx-auto">
            Upload your syllabus, lecture slides, or textbook notes in the Sources tab to automatically extract curriculum topics and concepts.
          </p>
          <div className="mt-5 flex justify-center">
            <Link
              href={`/dashboard/workspace/${workspaceId}/sources`}
              className="inline-flex items-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-xs font-semibold text-primary-foreground shadow-glow"
            >
              <span>Manage Learning Sources</span>
              <ChevronRight className="size-3.5" />
            </Link>
          </div>
        </div>
      ) : (
        <div className="mt-6 grid gap-6 lg:grid-cols-12">
          {/* Left Column: Topics Grid */}
          <div className="space-y-4 lg:col-span-7">
            {filteredTopics.map((topic) => {
            const isSelected = selectedTopic?.id === topic.id
            const isStrong = topic.status === 'strong'
            const isDeveloping = topic.status === 'developing'
            const isNeedsReview = topic.status === 'needs_review'
            const isCriticalGap = topic.status === 'critical_gap'

            return (
              <div
                key={topic.id}
                onClick={() => setSelectedTopic(topic)}
                className={cn(
                  'rounded-3xl border p-5 transition-all cursor-pointer shadow-soft hover:shadow-card',
                  isSelected
                    ? 'border-primary bg-card ring-1 ring-primary/40'
                    : 'border-border bg-card hover:border-primary/30'
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="font-display text-base font-semibold text-foreground">
                        {topic.name}
                      </h3>
                      <Badge
                        variant={
                          isStrong
                            ? 'success'
                            : isDeveloping
                            ? 'default'
                            : isNeedsReview
                            ? 'warning'
                            : 'destructive'
                        }
                        size="sm"
                        className="text-[10px] capitalize"
                      >
                        {topic.status.replace('_', ' ')}
                      </Badge>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{topic.description}</p>
                  </div>

                  <div className="text-right shrink-0">
                    <div className="flex items-center gap-1 font-display text-xl font-bold tabular-nums text-foreground">
                      {topic.trend === 'up' ? (
                        <TrendingUp className="size-4 text-success" />
                      ) : topic.trend === 'down' ? (
                        <TrendingDown className="size-4 text-warning" />
                      ) : null}
                      <span>{topic.mastery}%</span>
                    </div>
                    <span className="text-[10px] text-muted-foreground">{topic.conceptsCount} concepts</span>
                  </div>
                </div>

                <div className="mt-4">
                  <Progress value={topic.mastery} className="h-2" />
                </div>

                <div className="mt-4 flex items-center justify-between border-t border-border/70 pt-3 text-[11px] text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Calendar className="size-3 text-primary" /> Next Review: {topic.nextReviewDate}
                  </span>
                  <span className="font-medium text-primary flex items-center gap-1">
                    Explore Details <ChevronRight className="size-3" />
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Right Column: Selected Topic Detail Panel */}
        <div className="lg:col-span-5">
          {selectedTopic ? (
            <aside className="sticky top-20 rounded-3xl border border-border bg-card p-6 shadow-card space-y-6">
              <div className="border-b border-border pb-4">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-primary">
                    Topic Breakdown
                  </span>
                  <Badge variant="neutral" size="sm">
                    {selectedTopic.conceptsCount} Concepts
                  </Badge>
                </div>
                <h2 className="mt-1.5 font-display text-lg font-semibold text-foreground">
                  {selectedTopic.name}
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">{selectedTopic.description}</p>
              </div>

              {/* Concepts breakdown */}
              <div>
                <h4 className="text-xs font-semibold text-foreground">Underlying Concepts</h4>
                <div className="mt-3 flex flex-col gap-2 max-h-56 overflow-y-auto">
                  {selectedTopic.concepts.map((c) => (
                    <div
                      key={c.id}
                      className="rounded-xl border border-border bg-background p-3 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-foreground">{c.name}</span>
                        <span className="font-bold tabular-nums text-foreground">{c.mastery}%</span>
                      </div>
                      {c.whyWeak && (
                        <p className="mt-1.5 text-[11px] text-destructive leading-relaxed">
                          ⚠️ {c.whyWeak}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Recommended Actions */}
              <div className="border-t border-border pt-4">
                <h4 className="text-xs font-semibold text-foreground">Targeted Learning Actions</h4>
                <div className="mt-3 flex flex-col gap-2">
                  <Link
                    href={`/dashboard/workspace/${workspaceId}/tutor`}
                    className="flex items-center justify-center gap-2 rounded-xl bg-primary py-2.5 text-xs font-semibold text-primary-foreground shadow-glow transition-opacity hover:opacity-90"
                  >
                    <MessagesSquare className="size-3.5" />
                    <span>Ask Tutor About {selectedTopic.name}</span>
                  </Link>

                  <Link
                    href={`/dashboard/workspace/${workspaceId}/quiz`}
                    className="flex items-center justify-center gap-2 rounded-xl border border-border bg-background py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
                  >
                    <Zap className="size-3.5 text-warning" />
                    <span>Launch Adaptive Diagnostic Quiz</span>
                  </Link>

                  <Link
                    href={`/dashboard/workspace/${workspaceId}/flashcards`}
                    className="flex items-center justify-center gap-2 rounded-xl border border-border bg-background py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-accent/40"
                  >
                    <Layers className="size-3.5 text-primary" />
                    <span>Review Topic Flashcards</span>
                  </Link>
                </div>
              </div>
            </aside>
          ) : (
            <div className="rounded-3xl border border-border bg-card p-8 text-center text-xs text-muted-foreground">
              Select a topic on the left to inspect concept diagnostics.
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  )
}
