'use client'

import { useState } from 'react'
import {
  X,
  Map,
  CheckCircle2,
  Circle,
  Loader2,
  Sparkles,
  ArrowRight,
  Clock,
  Target,
  AlertTriangle,
  Info,
} from 'lucide-react'
import { Roadmap, RoadmapNode } from '@/lib/types/domain'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { cn } from '@/lib/utils'

interface RoadmapDetailModalProps {
  isOpen: boolean
  onClose: () => void
  roadmap: Roadmap
  workspaceName: string
}

export function RoadmapDetailModal({
  isOpen,
  onClose,
  roadmap,
  workspaceName,
}: RoadmapDetailModalProps) {
  const [showAdaptationExplanation, setShowAdaptationExplanation] = useState(false)

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} aria-hidden />

      <div className="relative flex max-h-[90vh] w-full max-w-3xl flex-col rounded-3xl border border-border bg-card shadow-card animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border p-6">
          <div className="flex items-center gap-3">
            <span className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Map className="size-5" />
            </span>
            <div>
              <h2 className="font-display text-lg font-semibold text-foreground">
                Adaptive Learning Roadmap
              </h2>
              <p className="text-xs text-muted-foreground">{workspaceName} — Dynamic Path</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Badge variant="success" size="md">
              {roadmap.overallProgress}% Completed
            </Badge>
            <button
              onClick={onClose}
              className="flex size-8 items-center justify-center rounded-xl border border-border bg-background text-muted-foreground transition-colors hover:text-foreground"
              aria-label="Close modal"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        {/* Modal Body */}
        <div className="flex-1 space-y-6 overflow-y-auto p-6">
          {/* Adaptation Banner */}
          {roadmap.adaptation?.hasAdaptation && (
            <div className="rounded-2xl border border-primary/20 bg-primary/5 p-4 text-xs">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-semibold text-primary">
                  <Sparkles className="size-4" />
                  <span>{roadmap.adaptation.title}</span>
                </div>
                <button
                  onClick={() => setShowAdaptationExplanation(!showAdaptationExplanation)}
                  className="inline-flex items-center gap-1 font-semibold text-primary hover:underline"
                >
                  {showAdaptationExplanation ? 'Hide rationale' : 'Why did my roadmap change?'}
                </button>
              </div>

              <p className="mt-1 text-muted-foreground">{roadmap.adaptation.triggerReason}</p>

              {showAdaptationExplanation && (
                <div className="mt-3 rounded-xl border border-border bg-card p-3 animate-in fade-in duration-100">
                  <p className="font-semibold text-foreground">Adaptation Breakdown:</p>
                  <div className="mt-2 grid grid-cols-2 gap-3 text-[11px]">
                    <div className="rounded-lg bg-background p-2 border border-border">
                      <span className="font-semibold text-muted-foreground">Original Sequence:</span>
                      <ul className="mt-1 list-disc pl-4 space-y-0.5 text-muted-foreground">
                        {roadmap.adaptation.beforePath.map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="rounded-lg bg-primary/10 p-2 border border-primary/20">
                      <span className="font-semibold text-primary">Adapted Progression (Now):</span>
                      <ul className="mt-1 list-disc pl-4 space-y-0.5 text-foreground font-medium">
                        {roadmap.adaptation.nowPath.map((n, i) => (
                          <li key={i}>{n}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <p className="mt-2.5 text-[11px] leading-relaxed text-muted-foreground">
                    {roadmap.adaptation.detailedExplanation}
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Stages List */}
          <div className="space-y-6">
            {roadmap.stages.map((stage, stageIdx) => (
              <div key={stage.id} className="rounded-2xl border border-border bg-card/60 p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-display text-sm font-semibold uppercase tracking-wider text-foreground">
                      Stage {stageIdx + 1}: {stage.name}
                    </h3>
                    <p className="text-xs text-muted-foreground">{stage.description}</p>
                  </div>
                </div>

                <div className="mt-4 flex flex-col gap-3">
                  {stage.nodes.map((node) => {
                    const isDone = node.status === 'completed'
                    const isInProgress = node.status === 'in_progress'

                    return (
                      <div
                        key={node.id}
                        className={cn(
                          'flex items-center gap-3.5 rounded-xl border p-3.5 transition-colors',
                          isDone && 'border-border bg-background/50',
                          isInProgress && 'border-primary/40 bg-primary/5',
                          !isDone && !isInProgress && 'border-border/60 bg-background/20 opacity-75'
                        )}
                      >
                        <div className="shrink-0">
                          {isDone ? (
                            <CheckCircle2 className="size-5 text-success" />
                          ) : isInProgress ? (
                            <span className="flex size-5 items-center justify-center rounded-full bg-primary/20">
                              <Loader2 className="size-3.5 animate-spin text-primary" />
                            </span>
                          ) : (
                            <Circle className="size-5 text-muted-foreground/40" />
                          )}
                        </div>

                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="truncate text-xs font-semibold text-foreground">{node.title}</p>
                            {node.isAdaptiveAddition && (
                              <Badge variant="warning" size="sm" className="text-[10px]">
                                AI Spliced
                              </Badge>
                            )}
                          </div>
                          <p className="truncate text-[11px] text-muted-foreground">{node.description}</p>
                        </div>

                        <div className="flex items-center gap-4 shrink-0 text-right">
                          <div>
                            <span className="text-[11px] font-semibold tabular-nums text-foreground">
                              {node.mastery}%
                            </span>
                            <p className="text-[10px] text-muted-foreground">{node.estimatedHours}h est.</p>
                          </div>
                          <div className="w-16">
                            <Progress value={node.mastery} className="h-1.5" />
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
