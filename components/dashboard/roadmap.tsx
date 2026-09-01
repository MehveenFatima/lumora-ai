import { CheckCircle2, Circle, Loader2, Layers, Lightbulb, Target, ArrowRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'

type Step = { title: string; meta: string; state: 'done' | 'active' | 'todo' }

const steps: Step[] = [
  { title: 'Core data structures', meta: '8 topics • completed', state: 'done' },
  { title: 'Algorithm patterns', meta: '6 topics • completed', state: 'done' },
  { title: 'Dynamic programming', meta: '5 of 9 topics', state: 'active' },
  { title: 'System design basics', meta: 'unlocks next week', state: 'todo' },
  { title: 'Mock interview sprint', meta: 'final milestone', state: 'todo' },
]

const recommendations = [
  { icon: Lightbulb, title: 'Review Graph traversal', reason: 'Mastery dropped 12% since last quiz', tone: 'warning' as const },
  { icon: Layers, title: '18 flashcards due today', reason: 'Spaced repetition keeps recall high', tone: 'default' as const },
  { icon: Target, title: 'Try a hard DP quiz', reason: "You're ready to level up", tone: 'success' as const },
]

function Roadmap() {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-soft">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-display text-[15px] font-semibold text-foreground">Personalized roadmap</h3>
          <p className="mt-0.5 text-[12px] text-muted-foreground">Placement Prep 2026</p>
        </div>
        <Badge variant="default" size="md">
          58% complete
        </Badge>
      </div>

      <ol className="mt-5 flex flex-col">
        {steps.map((s, i) => (
          <li key={s.title} className="relative flex gap-3 pb-5 last:pb-0">
            {i < steps.length - 1 ? (
              <span
                className={cn(
                  'absolute left-[11px] top-6 h-full w-px',
                  s.state === 'done' ? 'bg-primary/40' : 'bg-border',
                )}
              />
            ) : null}
            <span className="relative z-10 mt-0.5">
              {s.state === 'done' ? (
                <CheckCircle2 className="size-6 text-primary" />
              ) : s.state === 'active' ? (
                <span className="flex size-6 items-center justify-center rounded-full bg-primary/12">
                  <Loader2 className="size-4 animate-spin text-primary" />
                </span>
              ) : (
                <Circle className="size-6 text-muted-foreground/40" strokeWidth={1.5} />
              )}
            </span>
            <div className="flex-1">
              <p className={cn('text-sm font-medium', s.state === 'todo' ? 'text-muted-foreground' : 'text-foreground')}>
                {s.title}
              </p>
              <p className="text-[12px] text-muted-foreground">{s.meta}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  )
}

function Recommendations() {
  return (
    <section className="rounded-2xl border border-border bg-card p-5 shadow-soft">
      <h3 className="font-display text-[15px] font-semibold text-foreground">AI recommendations</h3>
      <p className="mt-0.5 text-[12px] text-muted-foreground">Next best actions for today</p>
      <div className="mt-4 flex flex-col gap-2">
        {recommendations.map((r) => (
          <button
            key={r.title}
            className="group flex items-center gap-3 rounded-xl border border-border bg-card/50 p-3 text-left transition-colors hover:bg-accent/40"
          >
            <span
              className={cn(
                'flex size-9 shrink-0 items-center justify-center rounded-lg',
                r.tone === 'warning' && 'bg-warning/15 text-warning',
                r.tone === 'default' && 'bg-primary/12 text-primary',
                r.tone === 'success' && 'bg-success/15 text-success',
              )}
            >
              <r.icon className="size-[18px]" />
            </span>
            <div className="flex-1">
              <p className="text-[13px] font-medium text-foreground">{r.title}</p>
              <p className="text-[12px] text-muted-foreground">{r.reason}</p>
            </div>
            <ArrowRight className="size-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
          </button>
        ))}
      </div>
    </section>
  )
}

export { Roadmap, Recommendations }
