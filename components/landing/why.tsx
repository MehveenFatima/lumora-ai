import { CheckCircle2, Gauge, ShieldCheck, Infinity as InfinityIcon } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'

const points = [
  {
    icon: Gauge,
    title: 'Dynamic Mastery & Knowledge Gap Modeling',
    desc: 'Every assessment pinpoints exactly which sub-concept is weak and why, adapting your learning trajectory.',
  },
  {
    icon: ShieldCheck,
    title: 'Grounded in Your Own Material',
    desc: 'No random hallucinated advice. The AI Tutor cites exact pages and slides from your uploaded documents.',
  },
  {
    icon: InfinityIcon,
    title: 'Dedicated Workspace Context',
    desc: 'Switching from Operating Systems to Machine Learning switches all sources, notes, and memories without cross-topic bleeding.',
  },
]

const bars = [
  { label: 'Data Structures & Algorithms', value: 74 },
  { label: 'Operating Systems', value: 64 },
  { label: 'Machine Learning', value: 57 },
  { label: 'AWS Solutions Architect', value: 48 },
]

export function Why() {
  return (
    <section id="why" className="relative border-y border-border bg-card/30">
      <div className="mx-auto grid w-full max-w-[1280px] items-center gap-12 px-4 py-16 md:px-6 md:py-24 lg:grid-cols-2 lg:gap-16">
        <div>
          <Badge variant="default" size="md" className="text-xs">
            Why LumoraAI
          </Badge>
          <h2 className="mt-4 text-balance font-display text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            Study with Precision. Understand Deeper.
          </h2>
          <p className="mt-4 text-pretty text-xs leading-relaxed text-muted-foreground md:text-sm">
            Traditional tools force you through static checklists. LumoraAI monitors your diagnostic performance,
            detects where prerequisite foundations are failing, and updates your roadmap in real time.
          </p>

          <ul className="mt-8 flex flex-col gap-5">
            {points.map((p) => {
              const Icon = p.icon
              return (
                <li key={p.title} className="flex gap-4">
                  <span className="flex size-10 shrink-0 items-center justify-center rounded-2xl bg-primary/10 text-primary shadow-soft">
                    <Icon className="size-5" />
                  </span>
                  <div>
                    <h3 className="font-display text-sm font-semibold text-foreground">
                      {p.title}
                    </h3>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {p.desc}
                    </p>
                  </div>
                </li>
              )
            })}
          </ul>
        </div>

        {/* Visual telemetry panel */}
        <div className="relative">
          <div className="rounded-3xl border border-border bg-card p-6 shadow-card md:p-8">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-xs text-muted-foreground">Aggregate Curriculum Mastery</p>
                <p className="font-display text-3xl font-bold tracking-tight text-foreground">
                  68%
                </p>
              </div>
              <Badge variant="success" size="md" className="gap-1 text-xs">
                <CheckCircle2 className="size-3.5" />
                +14% this quarter
              </Badge>
            </div>

            <div className="mt-6 flex flex-col gap-4">
              {bars.map((b) => (
                <div key={b.label}>
                  <div className="mb-1.5 flex items-center justify-between text-xs">
                    <span className="font-medium text-foreground">{b.label}</span>
                    <span className="font-bold tabular-nums text-foreground">{b.value}%</span>
                  </div>
                  <Progress value={b.value} className="h-1.5" />
                </div>
              ))}
            </div>

            <div className="mt-6 rounded-2xl border border-primary/20 bg-primary/5 p-4 text-xs">
              <p className="leading-relaxed text-foreground">
                <span className="font-bold text-primary">AI Insight:</span> Graph Traversal weakness detected in Placement Prep. Spaced review and remedial cycle detection drill scheduled for today.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
