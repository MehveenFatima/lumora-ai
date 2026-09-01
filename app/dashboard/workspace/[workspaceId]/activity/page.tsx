'use client'

import { useState, useEffect } from 'react'
import { useParams } from 'next/navigation'
import {
  Clock,
  Zap,
  Layers,
  TrendingUp,
  Map,
  FileText,
  MessagesSquare,
  Filter,
} from 'lucide-react'
import { workspaceService } from '@/lib/services/workspace-service'
import {
  Workspace,
  LearningActivity,
  ActivityType,
} from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

export default function ActivityPage() {
  const params = useParams()
  const workspaceId = (params?.workspaceId as string) || 'dsa'

  const [workspace, setWorkspace] = useState<Workspace | null>(null)
  const [activities, setActivities] = useState<LearningActivity[]>([])
  const [filterType, setFilterType] = useState<string>('all')

  useEffect(() => {
    async function loadActivity() {
      const [ws, acts] = await Promise.all([
        workspaceService.getWorkspaceById(workspaceId),
        workspaceService.getActivities(workspaceId),
      ])
      setWorkspace(ws)
      setActivities(acts)
    }
    loadActivity()
  }, [workspaceId])

  const filteredActivities = activities.filter((act) => {
    if (filterType === 'all') return true
    return act.type === filterType
  })

  const getIcon = (type: ActivityType) => {
    switch (type) {
      case 'quiz_completed':
        return <Zap className="size-4 text-warning" />
      case 'flashcard_review':
        return <Layers className="size-4 text-primary" />
      case 'mastery_change':
        return <TrendingUp className="size-4 text-success" />
      case 'roadmap_adapted':
        return <Map className="size-4 text-primary" />
      case 'source_added':
        return <FileText className="size-4 text-chart-2" />
      case 'tutor_session':
        return <MessagesSquare className="size-4 text-primary" />
    }
  }

  return (
    <div className="mx-auto w-full max-w-[1360px] px-4 py-6 md:px-6 md:py-8 space-y-6">
      {/* Header */}
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-end">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold uppercase tracking-wider text-primary">
              Audit Timeline
            </span>
            <span className="text-muted-foreground">•</span>
            <span className="text-xs text-muted-foreground">{workspace?.name}</span>
          </div>
          <h1 className="mt-1 font-display text-2xl font-semibold text-foreground md:text-3xl">
            Learning Activity Log
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            Complete chronological record of assessment attempts, spaced repetition sessions, and roadmap adaptations.
          </p>
        </div>

        {/* Filter */}
        <div className="flex items-center gap-2">
          <Filter className="size-4 text-muted-foreground" />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="h-9 rounded-xl border border-input bg-card px-3 text-xs text-foreground outline-none"
          >
            <option value="all">All Activities</option>
            <option value="quiz_completed">Quizzes</option>
            <option value="flashcard_review">Flashcards</option>
            <option value="mastery_change">Mastery Updates</option>
            <option value="roadmap_adapted">Roadmap Adaptations</option>
            <option value="source_added">Document Indexing</option>
            <option value="tutor_session">Tutor Sessions</option>
          </select>
        </div>
      </div>

      {/* Activity Timeline Card */}
      <div className="rounded-3xl border border-border bg-card p-6 md:p-8 shadow-soft">
        <div className="relative space-y-6 before:absolute before:left-5 before:top-2 before:h-full before:w-px before:bg-border">
          {filteredActivities.length === 0 ? (
            <p className="py-8 text-center text-xs text-muted-foreground">No activities recorded for this filter.</p>
          ) : (
            filteredActivities.map((act) => (
              <div key={act.id} className="relative flex items-start gap-4">
                <span className="relative z-10 flex size-10 shrink-0 items-center justify-center rounded-xl border border-border bg-background shadow-soft">
                  {getIcon(act.type)}
                </span>
                <div className="flex-1 rounded-2xl border border-border bg-background/50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <h3 className="text-xs md:text-sm font-semibold text-foreground">{act.title}</h3>
                    <div className="flex items-center gap-2">
                      {act.scoreBadge && (
                        <Badge variant="success" size="sm">
                          {act.scoreBadge}
                        </Badge>
                      )}
                      <span className="text-[11px] text-muted-foreground">{act.timestamp}</span>
                    </div>
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground leading-relaxed">{act.description}</p>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
