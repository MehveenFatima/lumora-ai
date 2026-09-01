'use client'

import { useState } from 'react'
import { Zap, CheckCircle2, Clock } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const options = [
  { key: 'A', text: 'A page fault occurs on every memory access' },
  { key: 'B', text: 'The working set exceeds available frames' },
  { key: 'C', text: 'The CPU stays idle waiting for I/O' },
  { key: 'D', text: 'Pages are replaced using FIFO order' },
]

export function QuizCard() {
  const [selected, setSelected] = useState<string | null>(null)
  const correct = 'B'

  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <span className="flex size-8 items-center justify-center rounded-lg bg-warning/15 text-warning">
            <Zap className="size-4" />
          </span>
          <div>
            <h3 className="font-display text-[15px] font-semibold text-foreground">Adaptive quiz</h3>
            <p className="text-[12px] text-muted-foreground">Difficulty tuned to your mastery</p>
          </div>
        </div>
        <Badge variant="warning" size="md">
          Medium
        </Badge>
      </div>

      <div className="mt-4 flex items-center gap-3 text-[12px] text-muted-foreground">
        <span className="inline-flex items-center gap-1">
          <Clock className="size-3.5" /> 00:42
        </span>
        <span>Question 4 of 10</span>
        <div className="ml-auto flex gap-1">
          {Array.from({ length: 10 }).map((_, i) => (
            <span key={i} className={cn('h-1.5 w-3 rounded-full', i < 4 ? 'bg-primary' : 'bg-muted')} />
          ))}
        </div>
      </div>

      <p className="mt-4 text-sm font-medium leading-relaxed text-foreground">
        In demand paging, thrashing most directly occurs when:
      </p>

      <div className="mt-3 flex flex-col gap-2">
        {options.map((o) => {
          const isSelected = selected === o.key
          const isCorrect = selected && o.key === correct
          const isWrong = isSelected && o.key !== correct
          return (
            <button
              key={o.key}
              onClick={() => setSelected(o.key)}
              disabled={!!selected}
              className={cn(
                'flex items-center gap-3 rounded-xl border px-3.5 py-3 text-left text-[13px] transition-all',
                !selected && 'border-border hover:border-primary/40 hover:bg-accent/40',
                isCorrect && 'border-success/50 bg-success/10',
                isWrong && 'border-destructive/50 bg-destructive/10',
                selected && !isCorrect && !isWrong && 'border-border opacity-60',
              )}
            >
              <span
                className={cn(
                  'flex size-6 shrink-0 items-center justify-center rounded-md border text-[11px] font-semibold',
                  isCorrect
                    ? 'border-success bg-success text-success-foreground'
                    : isWrong
                      ? 'border-destructive bg-destructive text-destructive-foreground'
                      : 'border-border bg-muted text-muted-foreground',
                )}
              >
                {isCorrect ? <CheckCircle2 className="size-3.5" /> : o.key}
              </span>
              <span className="text-foreground">{o.text}</span>
            </button>
          )
        })}
      </div>

      {selected ? (
        <div className="mt-3 rounded-xl border border-border bg-muted/50 p-3 text-[12px] leading-relaxed text-muted-foreground">
          <span className="font-medium text-success">Correct.</span> Thrashing happens when the working set of active
          pages exceeds the frames allocated, forcing constant page swaps.
        </div>
      ) : null}
    </section>
  )
}
